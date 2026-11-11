#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# verifier-app-ios.py — ce que site/confidentialite.html dit de l'application
# iPhone (section #t-application, coprofirst-site#43) est-il encore vrai ?
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
#      page et cette liste ne gardent pas une ligne qui ne sert plus.
#
# Ce qu'il ne couvre pas (standards/04 §12) : les notifications push, décrites par
# la spécification de CoproFirst (specs/architecture/notifications-push.md §5) et
# pas encore dans l'app ; le comportement du code au-delà de ces deux déclarations —
# qu'un tiers admis ne soit que des dessins, sans code ni connexion, se relit dans le
# dépôt de l'app (REUSE.toml, le catalogue d'images) avant de l'ajouter à TIERS_ADMIS.
#
# En CI seulement, à chaque poussée et chaque jour (.github/workflows/comptes-demo.yml) :
# la dérive naît dans l'autre dépôt, comme pour verifier-comptes-demo.py.
#
# Verdicts (standards/04 §1) : 0 = conforme, 1 = écart, 2 = INCONNU — source
# injoignable, section ou clés introuvables (forme changée). Jamais un vert faute
# d'avoir pu lire.
#
# Usage : python3 scripts/verifier-app-ios.py
#         python3 scripts/verifier-app-ios.py --dependances X --projet Y --page Z
#         python3 scripts/verifier-app-ios.py --selftest
import argparse
import html
import re
import sys
import tempfile
from pathlib import Path

from lecture_distante import Illisible, lire

DEPOT = "https://raw.githubusercontent.com/philippe-tressard/coprofirst-ios/main/"
RACINE = Path(__file__).resolve().parent.parent
PAGE = RACINE / "site" / "confidentialite.html"
OK, ECART, INCONNU = 0, 1, 2

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


def nomme(section: str, mot: str) -> bool:
    """Le mot entier figure dans la section (« MIT » n'est pas dans « LIMITE »)."""
    return re.search(rf"(?<!\w){re.escape(mot)}(?!\w)", section) is not None


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


def ecarts_des_tiers(paquets: list[tuple[str, str]], section: str) -> list[str]:
    ecarts, vus = [], set()
    for paquet, cellule in paquets:
        if paquet.startswith("apple/"):
            continue
        nom = paquet.split(" ", 1)[0]
        if nom not in TIERS_ADMIS:
            ecarts.append(f"paquet embarqué hors d'Apple, non déclaré : {paquet} — le décrire dans "
                          "#t-application (la page dit « aucun code d'un tiers autre qu'Apple »), puis dans TIERS_ADMIS")
            continue
        vus.add(nom)
        if licences(cellule) != TIERS_ADMIS[nom]:
            ecarts.append(f"licences de {nom} : DEPENDANCES.md dit « {cellule} », TIERS_ADMIS et la page "
                          f"disent {', '.join(sorted(TIERS_ADMIS[nom]))}")
        ecarts += [f"la section #t-application ne nomme pas « {mot} » ({nom}, embarqué par l'app)"
                   for mot in [nom, *sorted(TIERS_ADMIS[nom])] if not nomme(section, mot)]
    ecarts += [f"{nom} n'est plus embarqué par l'app : le retirer de TIERS_ADMIS et de la page"
               for nom in sorted(TIERS_ADMIS.keys() - vus)]
    return ecarts


def permissions(texte: str) -> set[str]:
    cles = set(re.findall(r"^\s*(NS\w+UsageDescription)\s*:", texte, re.M))
    if not cles:
        raise Illisible("project.yml : aucune clé NS…UsageDescription (forme changée ?)")
    return cles


def section_application(texte: str) -> str:
    bloc = re.search(r'<section aria-labelledby="t-application">(.*?)</section>', texte, re.S)
    if not bloc:
        raise Illisible("confidentialite.html : section #t-application introuvable")
    return html.unescape(bloc.group(1)).replace("\xa0", " ")


def verifier(dependances: str, projet: str, page: str) -> tuple[int, list[str]]:
    try:
        paquets = paquets_embarques(lire(dependances))
        cles = permissions(lire(projet))
        section = section_application(lire(page))
    except Illisible as e:
        return INCONNU, [str(e)]
    ecarts = ecarts_des_tiers(paquets, section)
    ecarts += [f"permission {c} demandée par l'app, absente de PERMISSIONS et de la page"
               for c in sorted(cles - PERMISSIONS.keys())]
    ecarts += [f"permission {c} retirée de l'app : la retirer de PERMISSIONS et de la page"
               for c in sorted(PERMISSIONS.keys() - cles)]
    ecarts += [f"la section #t-application ne nomme pas « {mot} » ({c})"
               for c, mot in PERMISSIONS.items() if c in cles and not nomme(section, mot)]
    return (ECART if ecarts else OK), ecarts


def selftest() -> int:
    lucide = "| Lucide (tracés, via `icones-svg.json`) | plancher | ISC, MIT (part issue de Feather) |\n"
    deps = ("# Dépendances\n\n## Embarquées dans l'application\n\n| Paquet | Version | Licence |\n|---|---|---|\n"
            "| apple/swift-openapi-runtime | 1 | Apache-2.0 |\n| apple/swift-http-types | t | Apache-2.0 |\n"
            + lucide + "\n## Outils\n\n| Outil |\n|---|\n| mattpolzin/OpenAPIKit |\n")
    projet = "    info:\n      properties:\n        NSCameraUsageDescription: \"x\"\n        NSFaceIDUsageDescription: \"y\"\n"
    page = ('<section aria-labelledby="t-application"><li>La caméra</li><li>Face&nbsp;ID</li>'
            '<li>les pictogrammes de Lucide (licences ISC et MIT)</li></section>'
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
    ]
    echecs = 0
    with tempfile.TemporaryDirectory() as dossier:
        for nom, d, p, h, attendu in cas:
            chemins = []
            for i, contenu in enumerate((d, p, h)):
                f = Path(dossier) / f"{i}.txt"
                f.write_text(contenu, encoding="utf-8")
                chemins.append(str(f))
            obtenu, _ = verifier(*chemins)
            if obtenu != attendu:
                echecs += 1
                print(f"selftest ÉCHEC : {nom} — attendu {attendu}, obtenu {obtenu}")
        obtenu, _ = verifier(str(Path(dossier) / "absent"), chemins[1], chemins[2])
        if obtenu != INCONNU:
            echecs += 1
            print(f"selftest ÉCHEC : source illisible — attendu {INCONNU}, obtenu {obtenu}")
    print(f"verifier-app-ios --selftest : {len(cas) + 1 - echecs}/{len(cas) + 1} cas")
    return 1 if echecs else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dependances", default=DEPOT + "DEPENDANCES.md")
    parser.add_argument("--projet", default=DEPOT + "project.yml")
    parser.add_argument("--page", default=str(PAGE))
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    verdict, messages = verifier(args.dependances, args.projet, args.page)
    for m in messages:
        print(("INCONNU : " if verdict == INCONNU else "ÉCART : ") + m)
    print("verifier-app-ios : " + {OK: "conforme", ECART: f"{len(messages)} écart(s)", INCONNU: "INCONNU"}[verdict])
    return verdict


if __name__ == "__main__":
    sys.exit(main())
