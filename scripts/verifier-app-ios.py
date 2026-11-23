#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# verifier-app-ios.py — ce que site/confidentialite.html dit de l'application
# iPhone (section #t-application, coprofirst-site#43) est-il encore vrai ?
#
# Depuis coprofirst-site#110, la section est commune à l'iPhone et à Android, écarts
# déclarés : verifier-app-android.py la confronte à l'autre app, et ce qui leur est
# commun (section, mots, tiers, permissions, selftest) vit dans section_apps.py.
#
# La page est l'adresse de confidentialité que cite la fiche App Store. Deux de ses
# affirmations se lisent dans le dépôt de l'app (philippe-tressard/coprofirst-ios,
# public, branche main) et deviendraient fausses sans que rien d'autre ne le dise :
#
#   1. « aucun code d'un tiers autre qu'Apple » : chaque paquet de la section
#      « Embarquées dans l'application » de DEPENDANCES.md est un apple/…, ou un
#      tiers DÉCLARÉ dans TIERS_ADMIS — et alors la section le nomme, avec ses
#      licences, qui sont exactement celles de DEPENDANCES.md. Un tiers non déclaré
#      est un écart tant que la page ne le décrit pas ; un tiers déclaré qui n'est
#      plus embarqué aussi (une exception qui ne sert plus se retire) ;
#   2. les permissions de l'iPhone qu'elle demande : les clés NS…UsageDescription de
#      project.yml sont EXACTEMENT celles de PERMISSIONS, et la section nomme chacune.
#      Une permission ajoutée (localisation, contacts, photos…) est un écart tant
#      que la page ne la décrit pas ; une permission retirée aussi, pour que la
#      page et cette liste ne gardent pas une ligne qui ne sert plus ;
#   3. la durée de la consultation hors ligne : la section dit « N jours », N étant
#      `LectureGardee.joursMax` de HorsLigne.swift (coprofirst-site#92). Le
#      chiffre se lit dans le code, il n'est pas recopié ici ;
#   4. les appareils : chaque plateforme de project.yml autre que l'iPhone (watchOS,
#      tvOS) est nommée par la section (« Apple Watch », « Apple TV ») ; et la
#      liaison iPhone ↔ Apple Watch : tant que `LiaisonMontre.active` (MessageLiaison.swift)
#      est éteint, le bloc « Apple Watch » dit « pas encore en service » ; allumé, il ne le
#      dit plus — comme Wear OS côté Android (coprofirst-site#124).
#
# Ce qu'il ne couvre pas (standards/04 §12) : les notifications push, qui ont leur
# section #t-notifications, décrite par la spécification de CoproFirst
# (specs/architecture/notifications-push.md §5, §11, §12) et dont le texte fixe et la
# durée se relisent par verifier-faits-produit.py ; le comportement du code au-delà de ces deux déclarations —
# qu'un tiers admis ne soit que des dessins, sans code ni connexion, se relit dans le
# dépôt de l'app (REUSE.toml, le catalogue d'images) avant de l'ajouter à TIERS_ADMIS ;
# le reste de ce que l'app garde sur l'iPhone, tenu ligne à ligne par la fiche de
# coprofirst-ios (confidentialite.md §3, verifier-confidentialite.py) : le recopier ici
# en ferait une seconde liste.
#
# En CI seulement, à chaque poussée et chaque jour (.github/workflows/comptes-demo.yml) :
# la dérive naît dans l'autre dépôt, comme pour verifier-comptes-demo.py.
#
# Verdicts (standards/04 §1) : 0 = conforme, 1 = écart, 2 = INCONNU — source
# injoignable, section ou clés introuvables (forme changée). Jamais un vert faute
# d'avoir pu lire.
#
# Usage : python3 scripts/verifier-app-ios.py
#         python3 scripts/verifier-app-ios.py --dependances X --projet Y --page Z --lecture W --liaison V
#         python3 scripts/verifier-app-ios.py --selftest
import argparse
import re
import sys

from lecture_distante import Illisible, lire
from section_apps import (ECART, INCONNU, OK, PAGE, conclure, ecarts_de_liaison, ecarts_des_permissions,
                          ecarts_des_tiers, nomme, rejouer, section_application)

DEPOT = "https://raw.githubusercontent.com/philippe-tressard/coprofirst-ios/main/"

# Chaque permission que l'app demande, et le mot qui la nomme dans la section.
PERMISSIONS = {
    "NSCameraUsageDescription": "caméra",  # QR code de la fiche d'arrivée (05/11/2026)
    "NSFaceIDUsageDescription": "Face ID",  # session gardée au Trousseau (05/11/2026)
}

# Ce que l'app embarque qui ne vient pas d'Apple : son nom (le premier mot de la
# colonne Paquet) et ses licences. La section doit nommer l'un et les autres.
TIERS_ADMIS = {
    # Pictogrammes du fil d'activité : 14 dessins (SVG d'un catalogue d'images, tracés
    # repris du site de CoproFirst), ni code ni connexion ; licences affichées dans
    # l'app, Plus › À propos › Composants tiers (relu dans coprofirst-ios le 11/11/2026).
    "Lucide": {"ISC", "MIT"},
}

# Chaque plateforme de project.yml autre que l'iPhone, et le mot du <h3> qui la décrit.
APPAREILS = {"watchOS": "Apple Watch", "tvOS": "Apple TV"}


def licences(cellule: str) -> set[str]:
    """« ISC, MIT (part issue de Feather) » → {ISC, MIT} : parenthèses ôtées."""
    return {l.strip() for l in re.split(r",|\bet\b|\bAND\b", re.sub(r"\([^)]*\)", "", cellule)) if l.strip()}


def paquets_embarques(texte: str) -> list[tuple[str, str]]:
    """Le tableau « Embarquées dans l'application » : (paquet, cellule Licence)."""
    bloc = re.search(r"^## Embarquées dans l'application\n(.*?)(?=^## |\Z)", texte, re.M | re.S)
    if not bloc:
        raise Illisible("DEPENDANCES.md : section « Embarquées dans l'application » introuvable")
    lignes = [l for l in bloc.group(1).splitlines() if l.startswith("|")]
    cellules = [[c.strip() for c in l.split("|")[1:-1]] for l in lignes]
    if len(cellules) < 3:  # en-tête, séparateur, au moins un paquet
        raise Illisible("DEPENDANCES.md : tableau des paquets embarqués vide ou illisible")
    if "Licence" not in cellules[0]:
        raise Illisible("DEPENDANCES.md : colonne « Licence » introuvable (forme changée ?)")
    rang = cellules[0].index("Licence")
    if any(len(c) <= rang for c in cellules[2:]):
        raise Illisible("DEPENDANCES.md : une ligne du tableau n'a pas de cellule Licence")
    return [(c[0], c[rang]) for c in cellules[2:]]


def tiers(paquets: list[tuple[str, str]]) -> list[tuple[str, set[str]]]:
    """Hors d'Apple : (premier mot du paquet, licences). La page dit « aucun code d'un
    tiers autre qu'Apple » : tout autre paquet est un écart tant qu'il n'est pas déclaré."""
    return [(p.split(" ", 1)[0], licences(c)) for p, c in paquets if not p.startswith("apple/")]


def permissions(texte: str) -> set[str]:
    cles = set(re.findall(r"^\s*(NS\w+UsageDescription)\s*:", texte, re.M))
    if not cles:
        raise Illisible("project.yml : aucune clé NS…UsageDescription (forme changée ?)")
    return cles


def jours_max(texte: str) -> int:
    """`static let joursMax = 7` → 7 : la durée de la lecture gardée hors ligne."""
    trouve = re.findall(r"^\s*static let joursMax\s*=\s*(\d+)\s*$", texte, re.M)
    if len(trouve) != 1:
        raise Illisible("HorsLigne.swift : `static let joursMax = N` introuvable ou en double (forme changée ?)")
    return int(trouve[0])


def plateformes(texte: str) -> set[str]:
    return set(re.findall(r"^\s*platform:\s*(\w+)\s*$", texte, re.M))


def liaison_active(texte: str) -> bool:
    trouve = re.findall(r"^\s*static let active = (true|false)\s*$", texte, re.M)
    if len(trouve) != 1:
        raise Illisible("MessageLiaison.swift : `static let active = …` introuvable ou en double (forme changée ?)")
    return trouve[0] == "true"


def verifier(dependances: str, projet: str, page: str, lecture: str, liaison: str) -> tuple[int, list[str]]:
    try:
        paquets = paquets_embarques(lire(dependances))
        texte_projet = lire(projet)
        cles = permissions(texte_projet)
        jours = jours_max(lire(lecture))
        active = liaison_active(lire(liaison))
        section = section_application(lire(page))
    except Illisible as e:
        return INCONNU, [str(e)]
    cibles = plateformes(texte_projet)
    ecarts = ecarts_des_tiers(tiers(paquets), TIERS_ADMIS, section, "TIERS_ADMIS (verifier-app-ios.py)")
    ecarts += ecarts_des_permissions(cles, PERMISSIONS, section)
    if not nomme(section, f"{jours} jours"):
        ecarts.append(f"la section #t-application ne dit pas « {jours} jours » : c'est la durée de la "
                      "lecture gardée hors ligne dans l'app (LectureGardee.joursMax, HorsLigne.swift)")
    ecarts += [f"project.yml construit pour {p} : la section #t-application ne nomme pas « {mot} »"
               for p, mot in APPAREILS.items() if p in cibles and not nomme(section, mot)]
    if "watchOS" in cibles:
        ecarts += ecarts_de_liaison(section, "Apple Watch", active, "LiaisonMontre.active")
    ecarts += [f"plateforme {p} de project.yml, absente de APPAREILS (verifier-app-ios.py) et de la page"
               for p in sorted(cibles - APPAREILS.keys() - {"iOS"})]
    return (ECART if ecarts else OK), ecarts


def selftest() -> int:
    lucide = "| Lucide (tracés, via `icones-svg.json`) | plancher | ISC, MIT (part issue de Feather) |\n"
    deps = ("# Dépendances\n\n## Embarquées dans l'application\n\n| Paquet | Version | Licence |\n|---|---|---|\n"
            "| apple/swift-openapi-runtime | 1 | Apache-2.0 |\n| apple/swift-http-types | t | Apache-2.0 |\n"
            + lucide + "\n## Outils\n\n| Outil |\n|---|\n| mattpolzin/OpenAPIKit |\n")
    projet = ("    platform: iOS\n    info:\n      properties:\n        NSCameraUsageDescription: \"x\"\n"
              "        NSFaceIDUsageDescription: \"y\"\n    platform: watchOS\n    platform: tvOS\n")
    eteinte = "enum LiaisonMontre {\n    static let active = false\n}\n"
    lecture = "enum LectureGardee {\n    static let joursMax = 7\n    static var dureeMax: TimeInterval { 1 }\n}\n"
    page = ('<section aria-labelledby="t-application"><li>La caméra</li><li>Face&nbsp;ID</li>'
            '<li>les pictogrammes de Lucide (licences ISC et MIT)</li><li>effacée au bout de 7&nbsp;jours</li>'
            '<h3>La montre Wear&nbsp;OS</h3><p>Ailleurs.</p><h3>L\'Apple&nbsp;Watch</h3><p>Lien&nbsp;: pas encore en service.</p>'
            '<p>L\'Apple&nbsp;TV n\'est pas publiée.</p></section>'
            '<section aria-labelledby="t-droits"></section>')
    cas = [
        ("conforme (un outil de build tiers ne compte pas)", deps, projet, page, OK),
        ("paquet tiers non déclaré", deps.replace("| apple/swift-http-types", "| firebase/firebase-ios-sdk"), projet, page, ECART),
        ("tiers admis que la page ne nomme pas", deps, projet, page.replace("de Lucide", "libres"), ECART),
        ("licence d'un tiers admis que la page ne nomme pas", deps, projet, page.replace(" et MIT", ""), ECART),
        ("licence d'un tiers admis changée dans l'app", deps.replace("ISC, MIT", "ISC, CC-BY-4.0"), projet, page, ECART),
        ("tiers admis qui n'est plus embarqué", deps.replace(lucide, ""), projet, page, ECART),
        ("un mot plus long ne nomme pas une licence", deps, projet, page.replace(" et MIT", " sans LIMITE"), ECART),
        ("colonne Licence absente", deps.replace("| Licence |", "| Droits |"), projet, page, INCONNU),
        ("permission ajoutée", deps, projet + "        NSLocationWhenInUseUsageDescription: \"z\"\n", page, ECART),
        ("permission retirée", deps, projet.replace("        NSCameraUsageDescription: \"x\"\n", ""), page, ECART),
        ("page qui ne nomme plus la caméra", deps, projet, page.replace("La caméra", "Le QR"), ECART),
        ("section des paquets absente", deps.replace("## Embarquées dans l'application", "## Autre"), projet, page, INCONNU),
        ("tableau des paquets vide", "## Embarquées dans l'application\n\n| Paquet | Licence |\n|---|---|\n", projet, page, INCONNU),
        ("aucune clé de permission", deps, "    info: {}\n", page, INCONNU),
        ("page sans la section", deps, projet, '<section aria-labelledby="t-droits"></section>', INCONNU),
        # La durée de la lecture gardée hors ligne (coprofirst-site#92) : 6e champ, la source.
        ("durée changée dans l'app", deps, projet, page, ECART, lecture.replace("= 7", "= 14")),
        ("page qui ne dit plus la durée", deps, projet, page.replace("7&nbsp;jours", "une semaine"), ECART),
        ("« 17 jours » ne dit pas « 7 jours »", deps, projet, page.replace("7&nbsp;jours", "17&nbsp;jours"), ECART),
        ("durée introuvable dans le code", deps, projet, page, INCONNU, lecture.replace("joursMax", "dureeJours")),
        ("durée écrite deux fois dans le code", deps, projet, page, INCONNU, lecture + "    static let joursMax = 7\n"),
        # La montre et l'Apple TV (coprofirst-site#124) : 7e champ, le drapeau de la liaison.
        ("liaison allumée, bloc qui dit « pas encore »", deps, projet, page, ECART, lecture, eteinte.replace("false", "true")),
        ("liaison éteinte, bloc qui ne le dit plus", deps, projet, page.replace("pas encore en service", "reliée"), ECART),
        ("liaison allumée et bloc à jour", deps, projet, page.replace("pas encore en service", "reliée"), OK,
         lecture, eteinte.replace("false", "true")),
        ("« pas encore » dit pour Wear OS seulement", deps, projet,
         page.replace("pas encore en service", "reliée").replace("Ailleurs", "Lien : pas encore en service"), ECART),
        ("montre embarquée, page sans bloc Apple Watch", deps, projet, page.replace("Apple&nbsp;Watch", "montre"), ECART),
        ("Apple TV construite, page qui ne la nomme pas", deps, projet, page.replace("Apple&nbsp;TV", "télé"), ECART),
        ("plateforme inconnue (visionOS)", deps, projet + "    platform: visionOS\n", page, ECART),
        ("sans cible watchOS, le drapeau ne juge rien", deps, projet.replace("    platform: watchOS\n", ""),
         page.replace("pas encore en service", "reliée"), OK),
        ("drapeau introuvable", deps, projet, page, INCONNU, lecture, "enum LiaisonMontre {}"),
    ]
    return rejouer("verifier-app-ios", [(nom, attendu, d, p, h, *(list(sources) + [lecture, eteinte][len(sources):]))
                                        for nom, d, p, h, attendu, *sources in cas], verifier)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dependances", default=DEPOT + "DEPENDANCES.md")
    parser.add_argument("--projet", default=DEPOT + "project.yml")
    parser.add_argument("--lecture", default=DEPOT + "CoproFirst/Session/LectureGardee/HorsLigne.swift")
    parser.add_argument("--liaison", default=DEPOT + "CoproFirst/Fonctions/Notifications/Montre/MessageLiaison.swift")
    parser.add_argument("--page", default=str(PAGE))
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    return conclure("verifier-app-ios", *verifier(args.dependances, args.projet, args.page, args.lecture, args.liaison))

if __name__ == "__main__":
    sys.exit(main())
