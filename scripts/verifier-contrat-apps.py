#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
"""verifier-contrat-apps.py — CONTRAT_APP (contenu-accueil.py) protège-t-il exactement
les `id` de contenu.json dont dépendent les DEUX apps ?

contenu.json est lu par l'app iOS ET par l'app Android (coprofirst-site#126). Chacune
déclare les `id` qu'elle exige — `ContenuVitrine.idsRequis` : les sections `heros`,
`fonctions`, `demo`, ses rangées et ses rôles. CONTRAT_APP en est une recopie, que
contenu-accueil.py fait tenir par la page ; ce contrôle compare la recopie aux deux
sources (branche main, lues sans jeton) :
  - un id qu'une app exige et que CONTRAT_APP ne protège pas : le site pourrait le
    retirer et l'app garderait sa dernière lecture sans un mot ;
  - un id protégé qu'aucune app n'exige plus : une contrainte morte, à retirer.
Ce qu'il ne couvre pas (standards/04 §12) : le nombre de `textes` lus par section.

Verdicts (standards/04 §1) : 0 conforme, 1 écart, 2 INCONNU (source injoignable, ou
forme du code changée : un id introuvable n'est jamais lu comme « aucun »).
En CI seulement (.github/workflows/comptes-demo.yml), comme les autres contrôles en ligne.

  python3 scripts/verifier-contrat-apps.py
  python3 scripts/verifier-contrat-apps.py --selftest
"""
import importlib.util
import re
import sys
from pathlib import Path

from lecture_distante import Illisible, lire

ICI = Path(__file__).resolve().parent
BRUT = "https://raw.githubusercontent.com/philippe-tressard/{depot}/main/{chemin}"
OK, ECART, INCONNU = 0, 1, 2
IOS = ("coprofirst-ios", "CoproFirst/Entree/Contenu/ContenuVitrine.swift")
ANDROID = ("coprofirst-android", "app/src/main/java/fr/coprofirst/app/entree/vitrine/PagesVitrine.kt")


def _un(motif: str, texte: str, quoi: str) -> str:
    trouves = re.findall(motif, texte, re.M)
    if len(trouves) != 1:
        raise Illisible(f"{quoi} : {len(trouves)} valeur(s), une attendue (forme du code changée ?)")
    return trouves[0]


def _ids(sections: tuple[str, str, str], rangees: list[str], roles: list[str], quoi: str) -> set[str]:
    if not rangees or not roles:
        raise Illisible(f"{quoi} : rangées ou rôles introuvables (forme du code changée ?)")
    heros, fonctions, demo = sections
    return {heros, fonctions, demo} | {f"{fonctions}/{r}" for r in rangees} | {f"{demo}/{r}" for r in roles}


def ids_ios(source: str) -> set[str]:
    sections = tuple(_un(rf'^\s*static let {n} = "([^"]+)"$', source, f"iOS {n}") for n in ("heros", "fonctions", "demo"))
    return _ids(sections, re.findall(r'Accroche\(id: "([^"]+)"', source),
                re.findall(r'RoleDemo\(id: "([^"]+)"', source), "iOS")


def ids_android(source: str) -> set[str]:
    sections = tuple(_un(rf'^\s*const val {n} = "([^"]+)"$', source, f"Android {n}") for n in ("HEROS", "FONCTIONS", "DEMO"))
    rangees = re.findall(r'"([^"]+)"', _un(r"^\s*val rangees = listOf\(([^)]*)\)", source, "Android rangées"))
    return _ids(sections, rangees, re.findall(r'RoleDemo\("([^"]+)", "', source), "Android")


def ids_contrat(contrat: dict) -> set[str]:
    return set(contrat) | {f"{s}/{e}" for s, regle in contrat.items() for e in regle["elements"]}


def verifier(contrat: dict, source_ios: str, source_android: str) -> tuple[int, list[str]]:
    exiges = {"iOS": ids_ios(source_ios), "Android": ids_android(source_android)}
    proteges = ids_contrat(contrat)
    ecarts = [f"{app} exige « {i} », que CONTRAT_APP ne protège pas" for app, ids in exiges.items()
              for i in sorted(ids - proteges)]
    ecarts += [f"CONTRAT_APP protège « {i} », qu'aucune app n'exige plus" for i in sorted(proteges - set().union(*exiges.values()))]
    return (ECART if ecarts else OK), ecarts


def contrat_du_site() -> dict:
    spec = importlib.util.spec_from_file_location("contenu_accueil", ICI / "contenu-accueil.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CONTRAT_APP


IOS_TEST = '''    static let heros = "heros"
    static let fonctions = "fonctions"
    static let demo = "demo"
        Accroche(id: "demande", symbole: "a"),
        RoleDemo(id: "locataire", code: "user-loc", symbole: "k"),
'''
ANDROID_TEST = '''    const val HEROS = "heros"
    const val FONCTIONS = "fonctions"
    const val DEMO = "demo"
    val rangees = listOf("demande")
        RoleDemo("locataire", "user-loc"),
'''
CONTRAT_TEST = {"heros": {"elements": ()}, "fonctions": {"elements": ("demande",)}, "demo": {"elements": ("locataire",)}}


def selftest() -> int:
    cas = [
        ("contrat tenu par les deux apps", CONTRAT_TEST, IOS_TEST, ANDROID_TEST, OK),
        ("rangée ajoutée par l'iOS seule", CONTRAT_TEST, IOS_TEST + '        Accroche(id: "badges", symbole: "b"),\n', ANDROID_TEST, ECART),
        ("rôle ajouté par l'Android seul", CONTRAT_TEST, IOS_TEST, ANDROID_TEST + '        RoleDemo("syndic", "user-s"),\n', ECART),
        ("id protégé qu'aucune app n'exige", {**CONTRAT_TEST, "pied": {"elements": ()}}, IOS_TEST, ANDROID_TEST, ECART),
        ("section renommée côté Android", CONTRAT_TEST, IOS_TEST, ANDROID_TEST.replace('DEMO = "demo"', 'DEMO = "essai"'), ECART),
        ("rangées Android illisibles", CONTRAT_TEST, IOS_TEST, ANDROID_TEST.replace("val rangees", "val lignes"), INCONNU),
        ("rôles iOS introuvables", CONTRAT_TEST, IOS_TEST.replace("RoleDemo(", "Role("), ANDROID_TEST, INCONNU),
    ]
    echecs = 0
    for nom, contrat, ios, android, attendu in cas:
        try:
            obtenu = verifier(contrat, ios, android)[0]
        except Illisible:
            obtenu = INCONNU
        if obtenu != attendu:
            echecs += 1
            print(f"selftest ÉCHEC : {nom} — attendu {attendu}, obtenu {obtenu}")
    try:
        ids_contrat(contrat_du_site())
    except Exception as e:  # la vraie table doit se lire
        echecs += 1
        print(f"selftest ÉCHEC : CONTRAT_APP illisible — {e}")
    print(f"verifier-contrat-apps --selftest : {len(cas) + 1 - echecs}/{len(cas) + 1} cas")
    return 1 if echecs else 0


def main() -> int:
    if sys.argv[1:] == ["--selftest"]:
        return selftest()
    try:
        verdict, ecarts = verifier(contrat_du_site(), lire(BRUT.format(depot=IOS[0], chemin=IOS[1])),
                                   lire(BRUT.format(depot=ANDROID[0], chemin=ANDROID[1])))
    except Illisible as e:
        print(f"INCONNU : {e}")
        return INCONNU
    for e in ecarts:
        print("ÉCART : " + e)
    print("verifier-contrat-apps : " + ("conforme (iOS et Android)" if verdict == OK else f"{len(ecarts)} écart(s)"))
    return verdict


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
