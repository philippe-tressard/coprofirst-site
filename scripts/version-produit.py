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
# s'écrit dans le dépôt par --ecrire, jamais à la main : --ecrire avance aussi le
# lastmod de l'accueil dans sitemap.xml (verifier-referencement.py l'exige), pour
# que le dépôt reste cohérent en un seul geste.
#
# CoproFirst publie une dizaine de releases par jour (coprofirst-site#51) : ni une
# mise à jour à la main ni un contrôle sur chaque PR ne tiennent ce rythme. Le
# workflow planifié .github/workflows/version-produit.yml lance --ecrire et ouvre
# ou met à jour la PR « version » ; ce contrôle ne tourne plus sur les PR des
# autres sujets.
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
SITEMAP = PAGE.parent / "sitemap.xml"
ACCUEIL = "https://coprofirst.fr/"
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


def avancer_lastmod(sitemap: str, jour: str) -> str:
    """Fonction PURE : le sitemap dont le lastmod de l'accueil vaut au moins `jour`
    (AAAA-MM-JJ). Jamais reculé : un lastmod plus récent reste tel quel."""
    motif = re.compile(r"(<loc>" + re.escape(ACCUEIL) + r"</loc>\s*<lastmod>)(\d{4}-\d{2}-\d{2})(</lastmod>)")
    trouves = motif.findall(sitemap)
    if len(trouves) != 1:
        raise Illisible(f"sitemap : {len(trouves)} lastmod pour {ACCUEIL}, 1 attendu")
    return motif.sub(lambda m: m[1] + max(m[2], jour) + m[3], sitemap)


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
    carte = f"<url><loc>{ACCUEIL}</loc><lastmod>2026-10-01</lastmod></url>"
    for nom, entree, voulu in [
        ("lastmod avancé", carte, "2026-11-05"),
        ("lastmod plus récent gardé", carte.replace("10-01", "12-01"), "2026-12-01"),
        ("sitemap sans l'accueil", carte.replace(ACCUEIL, ACCUEIL + "demo.html"), "INCONNU"),
        ("accueil en double", carte + carte, "INCONNU"),
    ]:
        try:
            obtenu = re.search(r"<lastmod>(.*?)</lastmod>", avancer_lastmod(entree, "2026-11-05"))[1]
        except Illisible:
            obtenu = "INCONNU"
        echecs += obtenu != voulu
        print(f"  {'ok   ' if obtenu == voulu else 'ÉCHEC'}   {nom} : {obtenu}")
    try:
        juger(PAGE.read_text(encoding="utf-8"), attendu)
        avancer_lastmod(SITEMAP.read_text(encoding="utf-8"), "2026-01-01")
        print("  ok      index.html et sitemap.xml réels : un élément, un lastmod d'accueil")
    except Illisible as e:
        echecs += 1
        print(f"  ÉCHEC   index.html ou sitemap.xml réels : {e}")
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
        if ecart and options.ecrire:  # lu et jugé avant toute écriture : tout ou rien
            jour = datetime.now(ZoneInfo("Europe/Paris")).strftime("%Y-%m-%d")
            carte = avancer_lastmod(SITEMAP.read_text(encoding="utf-8"), jour)
    except (Illisible, OSError) as e:
        print(f"INCONNU : {e} — rien n'a été comparé")
        return INCONNU
    if ecart and options.ecrire:
        PAGE.write_text(corrigee, encoding="utf-8", newline="\n")
        SITEMAP.write_text(carte, encoding="utf-8", newline="\n")
        print(f"version-produit : index.html mise à jour → {attendu} (lastmod de l'accueil au {jour})")
        return OK
    if ecart:
        print(f"version-produit : {ecart}\n  → python3 scripts/version-produit.py --ecrire")
        return ECART
    print(f"version-produit : OK ({attendu})")
    return OK


if __name__ == "__main__":
    sys.exit(main())
