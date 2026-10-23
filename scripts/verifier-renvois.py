#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# verifier-renvois.py — chaque renvoi à un ticket de ce dépôt mène-t-il encore
# quelque part ?
#
# Un commentaire cite son ticket pour dire d'où vient une décision. Le 24/10/2026,
# les 32 tickets terminés ont été supprimés de GitHub : une soixantaine de renvois
# du dépôt, CLAUDE.md compris, ne menaient plus nulle part. Deux règles :
#   1. HORS LIGNE (pre-commit, CI) : un renvoi s'écrit qualifié, coprofirst-site#N.
#      Un renvoi nu (un dièse suivi d'un ou deux chiffres) est refusé : il ne se
#      vérifie pas, et se confond avec coprofirst#N, le dépôt de l'application.
#   2. EN LIGNE (--en-ligne, CI à chaque poussée et chaque jour) : chaque
#      coprofirst-site#N existe sur GitHub. Un ticket supprimé répond 410, un numéro
#      inconnu 404 ; une limite de débit ou une panne rend INCONNU.
# Limite : un renvoi nu de trois chiffres ou plus ressemble à une couleur (#000) et
# n'est pas reconnu ; le dépôt compte moins de cent tickets (24/10/2026).
# maquettes/ est hors du contrôle : ce sont des archives, on ne les corrige pas.
#
# Verdicts (standards/04 §1) : 0 = conforme, 1 = écart, 2 = INCONNU (aucun fichier
# lu, fichier illisible, GitHub injoignable).
#
# Usage : python3 scripts/verifier-renvois.py              renvois nus
#         python3 scripts/verifier-renvois.py --en-ligne   et existence des tickets
#         python3 scripts/verifier-renvois.py --selftest
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from lecture_distante import Illisible, statut

RACINE = Path(__file__).resolve().parent.parent
DEPOT = "philippe-tressard/coprofirst-site"
API = f"https://api.github.com/repos/{DEPOT}/issues/"
OK, ECART, INCONNU = 0, 1, 2
EXCLUS = ("maquettes/",)
BINAIRES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff2"}
# Ni lettre, chiffre, &, /, $, # ou tiret devant : coprofirst#2174, &#39; ou ${#t[@]}
# ne sont pas des renvois nus. Ni lettre ni chiffre derrière : #1a1a1a est une couleur.
NU = re.compile(r"(?<![\w&/$#-])#(\d{1,2})(?!\w)")
QUALIFIE = re.compile(
    rf"coprofirst-site#(\d+)\b|github\.com/{re.escape(DEPOT)}/(?:issues|pull)/(\d+)\b")


def renvois_nus(texte: str) -> list[tuple[int, str]]:
    """Fonction PURE : [(numéro de ligne, renvoi)] des renvois nus."""
    return [(n, m[0]) for n, ligne in enumerate(texte.splitlines(), 1) for m in NU.finditer(ligne)]


def renvois_qualifies(texte: str) -> set[int]:
    """Fonction PURE : les numéros de tickets de ce dépôt cités en toutes lettres."""
    return {int(m[1] or m[2]) for m in QUALIFIE.finditer(texte)}


def juger_statut(code: int) -> int:
    """Fonction PURE : 200 le ticket existe ; 404 ou 410 il ne mène nulle part ;
    le reste (limite de débit, panne) ne dit rien du ticket."""
    if code == 200:
        return OK
    return ECART if code in (404, 410) else INCONNU


def fichiers() -> list[Path]:
    """Les fichiers versionnés, hors archives et binaires. Illisible sans git."""
    try:
        sortie = subprocess.run(["git", "-C", str(RACINE), "ls-files", "-z"],
                                capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        raise Illisible(f"git ls-files : {e}")
    noms = [n for n in sortie.decode("utf-8").split("\0") if n]
    return [RACINE / n for n in noms
            if not n.startswith(EXCLUS) and Path(n).suffix.lower() not in BINAIRES]


def parcourir(chemins: list[Path]) -> tuple[list[str], set[int]]:
    """Les renvois nus (« chemin:ligne renvoi ») et les numéros qualifiés. Un
    fichier illisible, ou aucun fichier, est Illisible : rien n'a été contrôlé."""
    if not chemins:
        raise Illisible("aucun fichier à lire")
    nus, qualifies = [], set()
    for chemin in chemins:
        try:
            texte = chemin.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            raise Illisible(f"{chemin} : {e}")
        nom = chemin.relative_to(RACINE).as_posix() if chemin.is_relative_to(RACINE) else str(chemin)
        nus += [f"{nom}:{n} {r}" for n, r in renvois_nus(texte)]
        qualifies |= renvois_qualifies(texte)
    return nus, qualifies


def en_ligne(numeros: set[int]) -> int:
    jeton = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    pire = OK
    for n in sorted(numeros):
        try:
            code = statut(f"{API}{n}", jeton)
        except Illisible as e:
            print(f"INCONNU : {e}")
            pire = max(pire, INCONNU)
            continue
        verdict = juger_statut(code)
        if verdict == ECART:
            print(f"ÉCART : coprofirst-site#{n} ne mène nulle part (HTTP {code}) — "
                  "réécrire le renvoi sans lui, ou citer ce qui le remplace")
        elif verdict == INCONNU:
            print(f"INCONNU : coprofirst-site#{n} — HTTP {code}")
        pire = max(pire, verdict)
    return pire


def selftest() -> int:
    d = "#"  # jamais de renvoi nu écrit ici : ce fichier passe lui-même au contrôle
    nus = [
        ("renvoi nu entre parenthèses", f"Survol ({d}36).", [(1, f"{d}36")]),
        ("renvoi nu en début de ligne", f"{d}6 est fermé", [(1, f"{d}6")]),
        ("deux renvois, deuxième ligne", f"a\n({d}14), ({d}22)", [(2, f"{d}14"), (2, f"{d}22")]),
        ("renvoi qualifié", f"(coprofirst-site{d}6)", []),
        ("autre dépôt", f"coprofirst{d}2174", []),
        ("couleur à chiffres", f"color: {d}000; {d}1a1a1a", []),
        ("entité HTML", f"l&{d}39;avis", []),
        ("longueur bash", f"${{{d}t[@]}} et ${d}", []),
        ("ancre", f'href="{d}ia"', []),
        ("cas zéro", "", []),
    ]
    qualifies = [
        ("forme courte", f"(coprofirst-site{d}6, coprofirst-site{d}37)", {6, 37}),
        ("adresse", f"https://github.com/{DEPOT}/issues/12 et /pull/2".replace(
            "/pull/2", f" https://github.com/{DEPOT}/pull/2"), {12, 2}),
        ("autre dépôt", f"coprofirst{d}2174 github.com/philippe-tressard/coprofirst/issues/9", set()),
    ]
    statuts = [(200, OK), (404, ECART), (410, ECART), (403, INCONNU), (429, INCONNU), (500, INCONNU)]
    echecs = 0
    for nom, texte, attendu in nus:
        lu = renvois_nus(texte)
        echecs += lu != attendu
        print(f"  {'ok    ' if lu == attendu else 'ÉCHEC '}  nu, {nom} : {lu}")
    for nom, texte, attendu in qualifies:
        lu = renvois_qualifies(texte)
        echecs += lu != attendu
        print(f"  {'ok    ' if lu == attendu else 'ÉCHEC '}  qualifié, {nom} : {sorted(lu)}")
    for code, attendu in statuts:
        lu = juger_statut(code)
        echecs += lu != attendu
        print(f"  {'ok    ' if lu == attendu else 'ÉCHEC '}  HTTP {code} : {lu}")
    try:
        parcourir([])
        echecs += 1
        print("  ÉCHEC   aucun fichier : lu sans erreur, attendu INCONNU")
    except Illisible:
        print("  ok      aucun fichier : INCONNU")
    print("selftest : OK" if echecs == 0 else f"selftest : {echecs} ÉCHEC(S)")
    return OK if echecs == 0 else ECART


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--en-ligne", action="store_true",
                         help="vérifier aussi sur GitHub que chaque ticket cité existe")
    parseur.add_argument("--selftest", action="store_true")
    options = parseur.parse_args()
    if options.selftest:
        return selftest()
    try:
        nus, qualifies = parcourir(fichiers())
    except Illisible as e:
        print(f"INCONNU : {e} — rien n'a été contrôlé")
        return INCONNU
    for ligne in nus:
        print(f"ÉCART : renvoi nu {ligne} — l'écrire coprofirst-site#N")
    verdict = ECART if nus else OK
    if options.en_ligne:
        verdict = max(verdict, en_ligne(qualifies))
    elif qualifies:
        print(f"{len(qualifies)} ticket(s) cité(s), leur existence se vérifie par --en-ligne")
    if verdict == OK:
        print(f"renvois : conformes ({len(qualifies)} ticket(s) cité(s))")
    return verdict


if __name__ == "__main__":
    sys.exit(main())
