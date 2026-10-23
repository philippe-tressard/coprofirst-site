#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
"""verifier-avis.py — site/avis.json, l'export des avis de l'application, avant qu'il ne parte.

Le fichier n'est PAS versionné : c'est l'export de l'application, déposé sur le poste
et envoyé par deploiement/deployer.sh, qui lance ce contrôle avant d'envoyer et sur ce
que le serveur sert. Il publie le prénom et l'initiale de
personnes réelles. Ce contrôle refuse ce qui ne doit pas paraître :
  - un JSON illisible, ou une forme qui n'est pas { "genere_le", "avis": [...] } ;
  - une clé que l'export ne produit pas — liste BLANCHE (standards/03 §2) : une
    donnée ajoutée côté application ne part pas sur le site sans qu'on l'ait décidé ;
  - un avis sous 4 étoiles (l'application ne les rend pas publiables), un champ vide,
    une date qui n'en est pas une ;
  - un auteur nommé en entier : la forme publique est « Prénom N. » ;
  - l'avis de l'éditeur : il paraît en « mot du créateur », jamais parmi les avis
    d'utilisateurs (pratique commerciale trompeuse sinon) ;
  - un avis de plus de DUREE_MAX_ANS ans : la durée maximale de publication annoncée
    par confidentialite.html#t-avis (article D111-17 du Code de la consommation) ;
  - une adresse de courriel ou un numéro de téléphone dans un titre ou un texte.

Un nom de résidence dans le texte est admis (choix de Philippe, 20/10/2026). Ce
qu'il ne voit pas : le nom complet d'une personne écrit dans le texte. Cela se
relit, avant de retenir l'avis dans l'application.

Les règles de forme et la durée sont aussi celles de site/accueil.js (avisValide),
qui écarte à l'affichage ce que ce contrôle refuse : l'un ne change pas sans l'autre.

Sortie : 0 conforme, 1 écart, 2 INCONNU (fichier absent ou illisible).
Usage : python3 scripts/verifier-avis.py [--fichier CHEMIN] | --selftest
"""
import json
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

NOTE_PUBLIABLE, NOTE_MAX = 4, 5
CLES_RACINE = {"genere_le", "avis"}
CLES_AVIS = {"titre", "texte", "note", "auteur", "role", "date"}
COURRIEL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
TELEPHONE = re.compile(r"(?:\+33\s?|\b0)[1-9](?:[\s.-]?\d{2}){4}\b")
# « Alain G. », « Jean-Baptiste F. », ou un prénom seul ; jamais « Alain Girard ».
AUTEUR = re.compile(r"^(?:\S+(?: \S+)* \w\.|\S+)$")
# L'éditeur du site (mentions légales), tel que l'application le signe.
EDITEUR = "Philippe T."
DUREE_MAX_ANS = 2


def perime(jour: str, aujourdhui: date) -> bool:
    """L'avis a-t-il dépassé la durée maximale de publication ? (29 février → 28)"""
    d = date.fromisoformat(jour)
    try:
        fin = d.replace(year=d.year + DUREE_MAX_ANS)
    except ValueError:
        fin = d.replace(year=d.year + DUREE_MAX_ANS, day=28)
    return aujourdhui >= fin


class Inconnu(Exception):
    """Le fichier n'a pas pu être lu : le contrôle ne conclut pas."""


def est_jour(v) -> bool:
    if not isinstance(v, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return False
    try:
        date.fromisoformat(v)
        return True
    except ValueError:
        return False


def rempli(v) -> bool:
    return isinstance(v, str) and v.strip() != ""


def juger_avis(i: int, a, aujourdhui: date) -> list[str]:
    """Fonction PURE : les écarts d'un avis, un par ligne."""
    ou = f"avis[{i}]"
    if not isinstance(a, dict):
        return [f"FORME    {ou} n'est pas un objet"]
    ecarts = []
    for cle in sorted(set(a) - CLES_AVIS):
        ecarts.append(f"CLÉ      {ou} : « {cle} » n'est pas une clé de l'export (liste blanche)")
    for cle in ("titre", "texte", "auteur"):
        if not rempli(a.get(cle)):
            ecarts.append(f"VIDE     {ou} : « {cle} » absent ou vide")
    if a.get("role") is not None and not isinstance(a.get("role"), str):
        ecarts.append(f"FORME    {ou} : « role » n'est ni un texte ni null")
    note = a.get("note")
    if isinstance(note, bool) or not isinstance(note, int) or not NOTE_PUBLIABLE <= note <= NOTE_MAX:
        ecarts.append(f"NOTE     {ou} : {note!r} (attendu un entier de {NOTE_PUBLIABLE} à {NOTE_MAX})")
    if not est_jour(a.get("date")):
        ecarts.append(f"DATE     {ou} : {a.get('date')!r} (attendu AAAA-MM-JJ)")
    elif perime(a["date"], aujourdhui):
        ecarts.append(f"PÉRIMÉ   {ou} : avis du {a['date']}, plus de {DUREE_MAX_ANS} ans — ne plus le retenir dans l'application, puis réexporter")
    if rempli(a.get("auteur")) and a["auteur"].strip() == EDITEUR:
        ecarts.append(f"ÉDITEUR  {ou} : l'avis de l'éditeur paraît en « mot du créateur », pas parmi les avis — ne pas le retenir dans l'application")
    if rempli(a.get("auteur")) and not AUTEUR.fullmatch(a["auteur"].strip()):
        ecarts.append(f"AUTEUR   {ou} : « {a['auteur']} » (forme publique attendue : « Prénom N. »)")
    for cle in ("titre", "texte"):
        v = a.get(cle) if isinstance(a.get(cle), str) else ""
        if COURRIEL.search(v):
            ecarts.append(f"DONNÉE   {ou} : une adresse de courriel dans « {cle} »")
        if TELEPHONE.search(v):
            ecarts.append(f"DONNÉE   {ou} : un numéro de téléphone dans « {cle} »")
    return ecarts


def juger(donnees, aujourdhui: date) -> list[str]:
    """Fonction PURE : les écarts du fichier entier."""
    if not isinstance(donnees, dict):
        return ["FORME    la racine n'est pas un objet { genere_le, avis }"]
    ecarts = [f"CLÉ      racine : « {c} » n'est pas une clé de l'export" for c in sorted(set(donnees) - CLES_RACINE)]
    if not est_jour(donnees.get("genere_le")):
        ecarts.append(f"DATE     genere_le : {donnees.get('genere_le')!r} (attendu AAAA-MM-JJ)")
    avis = donnees.get("avis")
    if not isinstance(avis, list):
        return ecarts + ["FORME    « avis » n'est pas une liste"]
    for i, a in enumerate(avis):
        ecarts += juger_avis(i, a, aujourdhui)
    return ecarts


def lire(chemin: Path):
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Inconnu(f"{chemin} absent")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise Inconnu(f"{chemin} illisible : {e}")


def verifier(chemin: Path) -> int:
    try:
        donnees = lire(chemin)
    except Inconnu as e:
        print(f"INCONNU : {e}")
        return 2
    ecarts = juger(donnees, date.today())
    for e in ecarts:
        print(e)
    if ecarts:
        print(f"verifier-avis : {len(ecarts)} écart(s) dans {chemin}")
        return 1
    n = len(donnees["avis"])
    print(f"verifier-avis : OK — {n} avis conforme(s) dans {chemin}")
    return 0


def selftest() -> int:
    bon = {"titre": "Enfin clair", "texte": "Tout est suivi.", "note": 5,
           "auteur": "Alain G.", "role": "Copropriétaire", "date": "2026-10-18"}
    cas = [
        ("export vide", {"genere_le": "2026-10-18", "avis": []}, []),
        ("avis conforme", {"genere_le": "2026-10-18", "avis": [bon]}, []),
        ("rôle null, prénom composé", {"genere_le": "2026-10-18", "avis": [{**bon, "role": None, "auteur": "Jean-Baptiste É."}]}, []),
        ("prénom seul", {"genere_le": "2026-10-18", "avis": [{**bon, "auteur": "Alain"}]}, []),
        ("clé inconnue", {"genere_le": "2026-10-18", "avis": [{**bon, "courriel": "x"}]}, ["CLÉ"]),
        ("clé inconnue à la racine", {"genere_le": "2026-10-18", "avis": [], "residence": "x"}, ["CLÉ"]),
        ("note 3", {"genere_le": "2026-10-18", "avis": [{**bon, "note": 3}]}, ["NOTE"]),
        ("note texte", {"genere_le": "2026-10-18", "avis": [{**bon, "note": "5"}]}, ["NOTE"]),
        ("note booléenne", {"genere_le": "2026-10-18", "avis": [{**bon, "note": True}]}, ["NOTE"]),
        ("date fausse", {"genere_le": "2026-10-18", "avis": [{**bon, "date": "2026-02-30"}]}, ["DATE"]),
        ("genere_le absent", {"avis": []}, ["DATE"]),
        ("texte vide", {"genere_le": "2026-10-18", "avis": [{**bon, "texte": "  "}]}, ["VIDE"]),
        ("nom entier", {"genere_le": "2026-10-18", "avis": [{**bon, "auteur": "Alain Girard"}]}, ["AUTEUR"]),
        ("courriel", {"genere_le": "2026-10-18", "avis": [{**bon, "texte": "écrivez à a.g@exemple.fr"}]}, ["DONNÉE"]),
        ("téléphone", {"genere_le": "2026-10-18", "avis": [{**bon, "texte": "appelez le 06 12 34 56 78"}]}, ["DONNÉE"]),
        ("avis pas objet", {"genere_le": "2026-10-18", "avis": ["x"]}, ["FORME"]),
        ("avis pas liste", {"genere_le": "2026-10-18", "avis": {}}, ["FORME"]),
        ("racine liste", [], ["FORME"]),
        ("nom de résidence admis", {"genere_le": "2026-10-18", "avis": [{**bon, "texte": "Toute la résidence 5Hostachy s'en sert."}]}, []),
        ("avis de l'éditeur", {"genere_le": "2026-10-18", "avis": [{**bon, "auteur": "Philippe T."}]}, ["ÉDITEUR"]),
        ("veille des deux ans", {"genere_le": "2026-10-18", "avis": [{**bon, "date": "2024-10-21"}]}, []),
        ("deux ans révolus", {"genere_le": "2026-10-18", "avis": [{**bon, "date": "2024-10-20"}]}, ["PÉRIMÉ"]),
        ("29 février", {"genere_le": "2026-10-18", "avis": [{**bon, "date": "2024-02-29"}]}, ["PÉRIMÉ"]),
    ]
    aujourdhui = date(2026, 10, 20)
    echecs = 0
    for nom, donnees, attendu in cas:
        obtenu = [e.split()[0] for e in juger(donnees, aujourdhui)]
        ok = obtenu == attendu
        echecs += not ok
        print(f"  {'ok     ' if ok else 'ÉCHEC  '} {nom} → {obtenu}" + ("" if ok else f", attendu {attendu}"))
    with tempfile.TemporaryDirectory() as t:
        illisible = Path(t) / "avis.json"
        illisible.write_text('{"avis": [', encoding="utf-8")
        for nom, chemin in (("fichier absent", Path(t) / "absent.json"), ("JSON illisible", illisible)):
            try:
                lire(chemin)
                ok = False
            except Inconnu:
                ok = True
            echecs += not ok
            print(f"  {'ok     ' if ok else 'ÉCHEC  '} {nom} → INCONNU")
    print("selftest : OK" if echecs == 0 else f"selftest : {echecs} ÉCHEC(S)")
    return 1 if echecs else 0


if __name__ == "__main__":
    # La console Windows est en cp1252 : sans cela, « → » fait tomber le contrôle.
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if args == ["--selftest"]:
        sys.exit(selftest())
    racine = Path(__file__).resolve().parent.parent
    chemin = Path(args[1]) if args[:1] == ["--fichier"] and len(args) == 2 else racine / "site" / "avis.json"
    sys.exit(verifier(chemin))
