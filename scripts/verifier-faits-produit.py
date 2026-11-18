#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# verifier-faits-produit.py — les chiffres et les libellés d'écran que les pages du
# site recopient du code de CoproFirst et de ses apps sont-ils encore ceux du code ?
#
# Une page statique recopie : « sous 30 jours au plus », « après 60 jours », le
# libellé d'un bouton. Le jour où le code change, la page ment sans que rien ne le
# dise — et ces pages sont celles que citent les magasins (Google Play exige l'adresse
# de supprimer-compte.html, coprofirst-site#104 ; les notifications de
# confidentialite.html, coprofirst-site#108).
#
# FAITS est la table : pour chaque fait, le fichier source (dépôt public, branche
# main, lu sans jeton), le motif qui en extrait la valeur — il doit trouver UNE
# valeur, ni zéro ni deux —, la page, la section (par son aria-labelledby) et la
# phrase qui doit y figurer, valeur comprise. La valeur se lit dans le code, elle
# n'est jamais recopiée ici : seule la phrase autour l'est.
#
# Ce qu'il ne couvre pas (standards/04 §12) : le sens des phrases. Ce qui est effacé
# et gardé (CONSEQUENCES, CONTENUS_GARDES de CoproFirst), et ce qui sonne sur un
# téléphone (porte.TYPE_POUSSE, l'alerte d'une actualité ⚡), se relisent à la main
# quand ces sources changent : le commentaire de tête de supprimer-compte.html les
# nomme. L'app iOS a son propre contrôle (verifier-app-ios.py).
#
# En CI seulement, à chaque poussée et chaque jour (.github/workflows/comptes-demo.yml) :
# la dérive naît dans l'autre dépôt, comme pour verifier-comptes-demo.py.
#
# Verdicts (standards/04 §1) : 0 = conforme, 1 = écart, 2 = INCONNU — source
# injoignable, motif introuvable ou ambigu, section absente. Jamais un vert faute
# d'avoir pu lire.
#
# Usage : python3 scripts/verifier-faits-produit.py
#         python3 scripts/verifier-faits-produit.py --racine DOSSIER   (sources locales)
#         python3 scripts/verifier-faits-produit.py --selftest
import argparse
import html
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from lecture_distante import Illisible, lire

RACINE = Path(__file__).resolve().parent.parent
BRUT = "https://raw.githubusercontent.com/philippe-tressard/{depot}/main/"
OK, ECART, INCONNU = 0, 1, 2


@dataclass(frozen=True)
class Fait:
    nom: str
    depot: str  # dépôt public de philippe-tressard
    source: str  # chemin dans ce dépôt
    motif: str  # une expression régulière à UN groupe : la valeur
    page: str  # sous site/
    section: str  # aria-labelledby de la <section>
    phrase: str  # ce que la section doit dire, « {} » étant la valeur


SERVEUR, IOS, ANDROID = "coprofirst", "coprofirst-ios", "coprofirst-android"
SUPPR, CONFID = "supprimer-compte.html", "confidentialite.html"
FRONT_SUPPR = "front/src/lib/components/SuppressionCompte.svelte"
IOS_SUPPR = "CoproFirst/Fonctions/Profil/SuppressionCompte/SectionSuppressionCompte.swift"
ANDROID_CHAINES = "app/src/main/res/values/strings_profil.xml"
REGLES = "api/app/utils/purge_comptes/regles.py"

FAITS = (
    # Supprimer votre compte (coprofirst-site#104)
    Fait("délai de traitement d'une demande", SERVEUR, "api/app/utils/delais_rgpd.py",
         r"^DELAI_TRAITEMENT_DEMANDE_JOURS = (\d+)$", SUPPR, "t-ensuite", "sous {} jours au plus"),
    Fait("inactivité avant l'avertissement", SERVEUR, REGLES,
         r"^INACTIVITE_ANS = (\d+)$", SUPPR, "t-inactif", "{} ans sans connexion"),
    Fait("délai entre l'avertissement et la suppression", SERVEUR, REGLES,
         r"^DELAI_AVANT_SUPPRESSION_JOURS = (\d+)$", SUPPR, "t-inactif", "{} jours plus tard"),
    Fait("conservation de l'historique des courriels", SERVEUR, "api/app/seed/contenus_legaux.py",
         r"Historique des envois de courriels\\xa0: conservé <strong>(\d+)\\xa0jours", SUPPR, "t-garde",
         "gardé {} jours"),
    Fait("site : titre du bloc", SERVEUR, FRONT_SUPPR,
         r'<h3 class="titre-suppression">([^<]+)</h3>', SUPPR, "t-demander", "« {} »"),
    Fait("site : bouton qui ouvre la demande", SERVEUR, FRONT_SUPPR,
         r"\(formulaire = true\)\}>\s*([^<]+?)\s*</button>", SUPPR, "t-demander", "« {} »"),
    Fait("site : bouton qui confirme", SERVEUR, FRONT_SUPPR,
         r'type="submit"[^>]*>\s*([^<]+?)\s*</button>', SUPPR, "t-demander", "« {} »"),
    Fait("site : bouton qui retire la demande", SERVEUR, FRONT_SUPPR,
         r"on:click=\{retirer\}>\s*([^<]+?)\s*</button>", SUPPR, "t-ensuite", "« {} »"),
    Fait("iOS : titre de l'écran", IOS, IOS_SUPPR,
         r'\.navigationTitle\("([^"]+)"\)', SUPPR, "t-demander", "« {} »"),
    Fait("iOS : bouton qui ouvre la demande", IOS, IOS_SUPPR,
         r'Label\("([^"]+)", systemImage: "person\.crop\.circle\.badge\.xmark"\)', SUPPR, "t-demander", "« {} »"),
    Fait("Android : titre de la rubrique", ANDROID, ANDROID_CHAINES,
         r'name="profil_supprimer_compte">([^<]+)<', SUPPR, "t-demander", "« {} »"),
    Fait("Android : bouton qui ouvre la demande", ANDROID, ANDROID_CHAINES,
         r'name="profil_demander_suppression">([^<]+)<', SUPPR, "t-demander", "« {} »"),
    # Les notifications sur le téléphone (coprofirst-site#108)
    Fait("texte fixe de la notification", SERVEUR, "api/app/utils/push/envoi.py",
         r'^CORPS = "([^"]+)"$', CONFID, "t-notifications", "« {} »"),
    Fait("abandon de l'identifiant d'un appareil", SERVEUR, "api/app/utils/push/appareils.py",
         r"^ABANDON_JOURS = (\d+)$", CONFID, "t-notifications", "après {} jours"),
)


def normaliser(texte: str) -> str:
    """Le texte lu comme un lecteur le lit : entités résolues, espaces insécables et
    retours à la ligne ramenés à une espace."""
    return re.sub(r"\s+", " ", html.unescape(texte).replace("\xa0", " "))


def valeur(fait: Fait, source: str) -> str:
    trouvees = re.findall(fait.motif, source, re.M)
    if len(trouvees) != 1:
        raise Illisible(f"{fait.depot}/{fait.source} : {len(trouvees)} valeur(s) pour « {fait.nom} » "
                        "(une attendue — la forme du code a changé)")
    return normaliser(trouvees[0]).strip()


def section(page: str, ancre: str, nom_page: str) -> str:
    bloc = re.search(rf'<section aria-labelledby="{re.escape(ancre)}">(.*?)</section>', page, re.S)
    if not bloc:
        raise Illisible(f"{nom_page} : section #{ancre} introuvable")
    return normaliser(re.sub(r"<[^>]+>", "", bloc.group(1)))


def verifier(faits, lire_source, lire_page) -> tuple[int, list[str], list[str]]:
    """(verdict, inconnus, écarts). lire_source(depot, chemin) et lire_page(nom) rendent
    du texte ou lèvent Illisible."""
    ecarts, inconnus = [], []
    for fait in faits:
        try:
            v = valeur(fait, lire_source(fait.depot, fait.source))
            texte = section(lire_page(fait.page), fait.section, fait.page)
        except Illisible as e:
            inconnus.append(str(e))
            continue
        attendu = fait.phrase.format(v)
        if attendu not in texte:
            ecarts.append(f"{fait.page}#{fait.section} ne dit pas « {attendu} » ({fait.nom}, "
                          f"lu dans {fait.depot}/{fait.source})")
    verdict = INCONNU if inconnus else ECART if ecarts else OK
    return verdict, inconnus, ecarts


def selftest() -> int:
    exemple = (Fait("délai", "d", "s.py", r"^DELAI = (\d+)$", "p.html", "t-a", "sous {} jours au plus"),
               Fait("bouton", "d", "b.svelte", r"\(ouvrir\)\}>\s*([^<]+?)\s*</button>", "p.html", "t-a", "« {} »"))
    sources = {"s.py": "DELAI = 30\n", "b.svelte": "<button on:click={(ouvrir)}>\n  Demander ceci\n</button>"}
    page = ('<section aria-labelledby="t-a"><p>Traitée sous 30&nbsp;jours\n au plus.</p>'
            '<li>Touchez «&nbsp;Demander <b>ceci</b>&nbsp;».</li></section>')
    cas = [
        ("conforme (insécables, balises et retours à la ligne)", sources, page, OK),
        ("délai changé dans le code", {**sources, "s.py": "DELAI = 45\n"}, page, ECART),
        ("libellé changé dans le code", {**sources, "b.svelte": "{(ouvrir)}>Supprimer</button>"}, page, ECART),
        ("page qui ne dit plus le délai", sources, page.replace("30&nbsp;jours", "un mois"), ECART),
        ("« 130 jours » ne dit pas « 30 jours »", sources, page.replace("sous 30", "sous 130"), ECART),
        ("valeur introuvable", {**sources, "s.py": "DELAI_JOURS = 30\n"}, page, INCONNU),
        ("valeur écrite deux fois", {**sources, "s.py": "DELAI = 30\nDELAI = 30\n"}, page, INCONNU),
        ("section absente", sources, page.replace('"t-a"', '"t-b"'), INCONNU),
        ("source illisible", {"b.svelte": sources["b.svelte"]}, page, INCONNU),
    ]
    echecs = 0
    for nom, srcs, pg, attendu in cas:
        def lire_source(_depot, chemin, srcs=srcs):
            if chemin not in srcs:
                raise Illisible(f"{chemin} : introuvable")
            return srcs[chemin]
        obtenu, _, _ = verifier(exemple, lire_source, lambda _nom, pg=pg: pg)
        if obtenu != attendu:
            echecs += 1
            print(f"selftest ÉCHEC : {nom} — attendu {attendu}, obtenu {obtenu}")
    # La table réelle : chaque motif a un groupe, chaque phrase une place pour la valeur,
    # chaque page et chaque section existent dans le dépôt (sans réseau).
    for fait in FAITS:
        if re.compile(fait.motif).groups != 1 or fait.phrase.count("{}") != 1:
            echecs += 1
            print(f"selftest ÉCHEC : FAITS « {fait.nom} » — un groupe et un « {{}} » exigés")
        try:
            section((RACINE / "site" / fait.page).read_text(encoding="utf-8"), fait.section, fait.page)
        except (OSError, Illisible) as e:
            echecs += 1
            print(f"selftest ÉCHEC : FAITS « {fait.nom} » — {e}")
    total = len(cas) + len(FAITS)
    print(f"verifier-faits-produit --selftest : {total - echecs}/{total} cas")
    return 1 if echecs else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--racine", help="dossier local qui contient les dépôts (au lieu de GitHub)")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()

    def lire_source(depot: str, chemin: str) -> str:
        if args.racine:
            return lire(str(Path(args.racine) / depot / chemin))
        return lire(BRUT.format(depot=depot) + chemin)

    def lire_page(nom: str) -> str:
        return lire(str(RACINE / "site" / nom))

    verdict, inconnus, ecarts = verifier(FAITS, lire_source, lire_page)
    for m in inconnus:
        print("INCONNU : " + m)
    for m in ecarts:
        print("ÉCART : " + m)
    print("verifier-faits-produit : " + {OK: f"conforme ({len(FAITS)} faits)",
                                         ECART: f"{len(ecarts)} écart(s)", INCONNU: "INCONNU"}[verdict])
    return verdict


if __name__ == "__main__":
    sys.exit(main())
