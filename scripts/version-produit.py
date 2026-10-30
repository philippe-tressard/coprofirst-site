#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# version-produit.py — la version de CoproFirst affichée par l'accueil est-elle la
# dernière version publiée ?
#
# Le héros porte « Version X · JJ/MM/AAAA » : la dernière RELEASE GitHub de
# CoproFirst — celle que le canal Urgence installe aussitôt (les autres vagues la
# reçoivent plus tard, coprofirst#2210), pas le dernier commit de main. Elle
# s'écrit dans le dépôt par --ecrire, jamais à la main, et ce contrôle signale
# l'écart chaque jour en CI (.github/workflows/comptes-demo.yml) : une release
# publiée côté CoproFirst laisse
# sinon le site en retard sans que rien ne le dise.
#
# Verdicts (standards/04 §1) : 0 = conforme, 1 = écart, 2 = INCONNU — API
# injoignable ou illisible, page sans l'élément [data-version-produit].
#
# Usage : python3 scripts/version-produit.py            contrôle
#         python3 scripts/version-produit.py --ecrire   met la page à jour
#         python3 scripts/version-produit.py --source FICHIER_JSON
#         python3 scripts/version-produit.py --selftest
import argparse
import json
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from lecture_distante import Illisible, lire

API = "https://api.github.com/repos/philippe-tressard/coprofirst/releases/latest"
DEPOT = "https://github.com/philippe-tressard/coprofirst"
PAGE = Path(__file__).resolve().parent.parent / "site" / "index.html"
OK, ECART, INCONNU = 0, 1, 2
ELEMENT = re.compile(r"(<li data-version-produit>)(.*?)(</li>)", re.S)
ETIQUETTE = re.compile(r"^v(\d+\.\d+\.\d+)$")


def version_publiee(texte_json: str) -> tuple[str, str, str]:
    """Fonction PURE : (étiquette, version, date JJ/MM/AAAA à Paris) d'une release."""
    try:
        donnees = json.loads(texte_json)
        etiquette, publiee = donnees["tag_name"], donnees["published_at"]
        quand = datetime.fromisoformat(publiee.replace("Z", "+00:00"))
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        raise Illisible(f"réponse de l'API illisible ({e})")
    m = ETIQUETTE.match(etiquette) if isinstance(etiquette, str) else None
    if not m:
        raise Illisible(f"étiquette de version inattendue « {etiquette} »")
    return etiquette, m[1], quand.astimezone(ZoneInfo("Europe/Paris")).strftime("%d/%m/%Y")


def contenu_attendu(etiquette: str, version: str, date: str) -> str:
    return f'<a href="{DEPOT}/releases/tag/{etiquette}"><b>Version {version}</b> · {date}</a>'


def juger(page: str, attendu: str) -> tuple[str | None, str]:
    """Fonction PURE : (écart ou None, page corrigée)."""
    trouves = ELEMENT.findall(page)
    if len(trouves) != 1:
        raise Illisible(f"page : {len(trouves)} élément(s) <li data-version-produit>, 1 attendu")
    actuel = trouves[0][1]
    corrigee = ELEMENT.sub(lambda m: m[1] + attendu + m[3], page)
    return (None if actuel == attendu else f"la page affiche « {actuel} », attendu « {attendu} »"), corrigee


def selftest() -> int:
    rel = json.dumps({"tag_name": "v3.1.0", "published_at": "2026-10-18T22:30:00Z"})
    attendu = contenu_attendu("v3.1.0", "3.1.0", "19/10/2026")  # 22 h 30 UTC = le 19 à Paris
    page = f"<ul><li data-version-produit>{attendu}</li></ul>"
    cas = [
        ("conforme", rel, page, "OK"),
        ("version en retard", rel, page.replace("3.1.0", "3.0.0"), "ECART"),
        ("date à l'heure de Paris", rel, page.replace("19/10", "18/10"), "ECART"),
        ("page sans élément (cas zéro)", rel, "<ul></ul>", "INCONNU"),
        ("page à deux éléments", rel, page + page, "INCONNU"),
        ("réponse sans tag_name", '{"published_at": "2026-10-18T10:00:00Z"}', page, "INCONNU"),
        ("étiquette inattendue", rel.replace("v3.1.0", "latest"), page, "INCONNU"),
        ("réponse non JSON", "<html>limite atteinte</html>", page, "INCONNU"),
    ]
    echecs = 0
    for nom, source, html, voulu in cas:
        try:
            ecart, _ = juger(html, contenu_attendu(*version_publiee(source)))
            obtenu = "ECART" if ecart else "OK"
        except Illisible:
            obtenu = "INCONNU"
        echecs += obtenu != voulu
        print(f"  {'ok   ' if obtenu == voulu else 'ÉCHEC'}   {nom} : {obtenu}")
    # --ecrire corrige la page, puis le contrôle passe ; la page réelle se lit
    with tempfile.TemporaryDirectory() as t:
        f = Path(t, "index.html")
        f.write_text(page.replace("3.1.0", "2.0.0"), encoding="utf-8")
        _, corrigee = juger(f.read_text(encoding="utf-8"), attendu)
        ok = juger(corrigee, attendu)[0] is None and corrigee.count("data-version-produit") == 1
        echecs += not ok
        print(f"  {'ok   ' if ok else 'ÉCHEC'}   --ecrire corrige, puis le contrôle passe")
    try:
        juger(PAGE.read_text(encoding="utf-8"), attendu)
        print("  ok      index.html réelle : un seul élément [data-version-produit]")
    except Illisible as e:
        echecs += 1
        print(f"  ÉCHEC   index.html réelle : {e}")
    print("selftest : OK" if echecs == 0 else f"selftest : {echecs} ÉCHEC(S)")
    return OK if echecs == 0 else ECART


def main() -> int:
    for flux in (sys.stdout, sys.stderr):
        flux.reconfigure(encoding="utf-8")
    parseur = argparse.ArgumentParser(description="La version affichée est-elle la dernière publiée ?")
    parseur.add_argument("--selftest", action="store_true")
    parseur.add_argument("--ecrire", action="store_true")
    parseur.add_argument("--source", default=API, help="fichier ou URL https de la release")
    options = parseur.parse_args()
    if options.selftest:
        return selftest()
    try:
        attendu = contenu_attendu(*version_publiee(lire(options.source)))
        ecart, corrigee = juger(PAGE.read_text(encoding="utf-8"), attendu)
    except (Illisible, OSError) as e:
        print(f"INCONNU : {e} — rien n'a été comparé")
        return INCONNU
    if ecart and options.ecrire:
        PAGE.write_text(corrigee, encoding="utf-8", newline="\n")
        print(f"version-produit : index.html mise à jour → {attendu}")
        return OK
    if ecart:
        print(f"version-produit : {ecart}\n  → python3 scripts/version-produit.py --ecrire")
        return ECART
    print(f"version-produit : OK ({attendu})")
    return OK


if __name__ == "__main__":
    sys.exit(main())
