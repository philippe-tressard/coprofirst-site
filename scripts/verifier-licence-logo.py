#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
"""verifier-licence-logo.py — LICENSES/LicenseRef-CoproFirst-Logo.txt est-il le texte de
CoproFirst ?

Un identifiant SPDX désigne UN texte. Celui du logo vit dans coprofirst (branche main) ;
le site en garde une copie, que la page des mentions légales donne à lire. Elle était
restée à sa version du 13/10/2026 quand le produit et les deux apps passaient à la
suivante (coprofirst-site#125). REUSE ne compare pas les dépôts : ce contrôle le fait.

Une seule différence est admise, déclarée : le paragraphe qui commence par
« Ce texte couvre » (PARAGRAPHE_LOCAL), qui nomme les fichiers de CE dépôt. Tout le reste
est identique au produit, à l'espacement près (les retours à la ligne ne comptent pas).
Le texte d'une licence ne se retouche pas ici : il change dans coprofirst, puis se recopie.

Verdicts (standards/04 §1) : 0 conforme, 1 écart, 2 INCONNU (source injoignable, ou
paragraphe local absent ou en double). En CI seulement (.github/workflows/comptes-demo.yml).

  python3 scripts/verifier-licence-logo.py
  python3 scripts/verifier-licence-logo.py --source FICHIER
  python3 scripts/verifier-licence-logo.py --selftest
"""
import argparse
import re
import sys
from pathlib import Path

from lecture_distante import Illisible, lire

RACINE = Path(__file__).resolve().parent.parent
COPIE = RACINE / "LICENSES" / "LicenseRef-CoproFirst-Logo.txt"
SOURCE = "https://raw.githubusercontent.com/philippe-tressard/coprofirst/main/LICENSES/LicenseRef-CoproFirst-Logo.txt"
PARAGRAPHE_LOCAL = "Ce texte couvre"
OK, ECART, INCONNU = 0, 1, 2


def paragraphes(texte: str, quoi: str) -> list[str]:
    """Les paragraphes, espaces ramenés à un, sans le paragraphe local (exactement un)."""
    tous = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", texte) if p.strip()]
    locaux = [p for p in tous if p.startswith(PARAGRAPHE_LOCAL)]
    if len(locaux) != 1:
        raise Illisible(f"{quoi} : {len(locaux)} paragraphe(s) « {PARAGRAPHE_LOCAL} », un attendu")
    return [p for p in tous if not p.startswith(PARAGRAPHE_LOCAL)]


def verifier(source: str, copie: str) -> tuple[int, list[str]]:
    produit, site = paragraphes(source, "texte de coprofirst"), paragraphes(copie, "copie du site")
    if produit == site:
        return OK, []
    ecarts = [f"absent de la copie : « {p[:90]}… »" for p in produit if p not in site]
    ecarts += [f"absent du produit : « {p[:90]}… »" for p in site if p not in produit]
    return ECART, ecarts or ["mêmes paragraphes, dans un autre ordre"]


def selftest() -> int:
    source = "Titre\n\nCe texte couvre a.\n\nPermission 1 ;\n  2.\n\nGarantie.\n"
    copie = "Titre\n\nCe texte couvre\nb et c.\n\nPermission 1 ; 2.\n\nGarantie.\n"
    cas = [
        ("conforme (paragraphe local et retours à la ligne différents)", source, copie, OK),
        ("permission ajoutée au produit", source.replace("2.", "2 ; 3."), copie, ECART),
        ("clause retouchée sur le site", source, copie.replace("Garantie.", "Garantie limitée."), ECART),
        ("paragraphe ajouté au site", source, copie + "\nAutre.\n", ECART),
        ("ordre changé", source, "Titre\n\nCe texte couvre b.\n\nGarantie.\n\nPermission 1 ; 2.\n", ECART),
        ("paragraphe local absent du site", source, copie.replace("Ce texte couvre", "Il couvre"), INCONNU),
        ("paragraphe local en double", source + "\nCe texte couvre z.\n", copie, INCONNU),
    ]
    echecs = 0
    for nom, src, cop, attendu in cas:
        try:
            obtenu = verifier(src, cop)[0]
        except Illisible:
            obtenu = INCONNU
        if obtenu != attendu:
            echecs += 1
            print(f"selftest ÉCHEC : {nom} — attendu {attendu}, obtenu {obtenu}")
    try:
        paragraphes(COPIE.read_text(encoding="utf-8"), "copie du site")
    except (OSError, Illisible) as e:
        echecs += 1
        print(f"selftest ÉCHEC : la copie du dépôt — {e}")
    print(f"verifier-licence-logo --selftest : {len(cas) + 1 - echecs}/{len(cas) + 1} cas")
    return 1 if echecs else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=SOURCE)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    try:
        verdict, ecarts = verifier(lire(args.source), COPIE.read_text(encoding="utf-8"))
    except (OSError, Illisible) as e:
        print(f"INCONNU : {e}")
        return INCONNU
    for e in ecarts:
        print("ÉCART : " + e)
    print("verifier-licence-logo : " + ("conforme au texte de coprofirst" if verdict == OK else f"{len(ecarts)} écart(s)"))
    return verdict


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
