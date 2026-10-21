#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# verifier-security-txt.py — site/.well-known/security.txt est-il valide, et le
# restera-t-il ? (RFC 9116, signalé par l'analyse de sécurité Cloudflare du 22/10/2026)
#
# Le fichier porte une date d'échéance (Expires) : passé cette date, il ne vaut plus
# rien, sans que rien ne casse. D'où un passage QUOTIDIEN en CI
# (.github/workflows/comptes-demo.yml) qui signale l'échéance un mois à l'avance.
# Exige : au moins un Contact, un seul Expires, dans moins d'un an (recommandation de
# la RFC) et pas avant PREAVIS jours, un Canonical égal à l'adresse servie.
#
# Verdicts (standards/04 §1) : 0 = conforme, 1 = écart, 2 = INCONNU (fichier absent
# ou illisible).
#
# Usage : python3 scripts/verifier-security-txt.py              contrôle
#         python3 scripts/verifier-security-txt.py --renouveler échéance à un an
#         python3 scripts/verifier-security-txt.py --selftest
import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

FICHIER = Path(__file__).resolve().parent.parent / "site" / ".well-known" / "security.txt"
CANONIQUE = "https://coprofirst.fr/.well-known/security.txt"
PREAVIS = timedelta(days=30)
DUREE_MAX = timedelta(days=366)
OK, ECART, INCONNU = 0, 1, 2
CHAMP = re.compile(r"^([A-Za-z-]+):\s*(.+?)\s*$")
EXPIRES = re.compile(r"^Expires:.*$", re.M)


def champs(texte: str) -> dict[str, list[str]]:
    """Fonction PURE : {nom en minuscules: [valeurs]} — les commentaires (#) ignorés."""
    lus: dict[str, list[str]] = {}
    for ligne in texte.splitlines():
        m = CHAMP.match(ligne)
        if m and not ligne.startswith("#"):
            lus.setdefault(m[1].lower(), []).append(m[2])
    return lus


def juger(texte: str, maintenant: datetime) -> list[str]:
    """Fonction PURE : la liste des écarts, vide si le fichier est conforme."""
    lus, ecarts = champs(texte), []
    if not lus.get("contact"):
        ecarts.append("aucun champ Contact")
    if lus.get("canonical", []) != [CANONIQUE]:
        ecarts.append(f"Canonical doit valoir exactement {CANONIQUE}")
    echeances = lus.get("expires", [])
    if len(echeances) != 1:
        return ecarts + [f"Expires doit paraître une fois (lu {len(echeances)} fois)"]
    try:
        echeance = datetime.fromisoformat(echeances[0].replace("Z", "+00:00"))
    except ValueError:
        return ecarts + [f"Expires illisible « {echeances[0]} »"]
    if echeance.tzinfo is None:
        ecarts.append("Expires sans fuseau (RFC 3339 l'exige)")
    elif echeance - maintenant < PREAVIS:
        ecarts.append(f"Expires {echeances[0]} : moins de {PREAVIS.days} jours, à renouveler (--renouveler)")
    elif echeance - maintenant > DUREE_MAX:
        ecarts.append(f"Expires {echeances[0]} : plus d'un an, la RFC le déconseille")
    return ecarts


def renouveler(texte: str, maintenant: datetime) -> str:
    """Fonction PURE : le texte avec une échéance à un an, à minuit UTC."""
    echeance = (maintenant + timedelta(days=365)).strftime("%Y-%m-%dT00:00:00Z")
    nouveau, n = EXPIRES.subn(f"Expires: {echeance}", texte)
    if n != 1:
        raise ValueError(f"Expires doit paraître une fois (lu {n} fois)")
    return nouveau


def selftest() -> int:
    t0 = datetime(2026, 10, 22, tzinfo=timezone.utc)
    bon = f"# commentaire: ignoré\nContact: mailto:a@b.fr\nExpires: 2027-10-01T00:00:00Z\nCanonical: {CANONIQUE}\n"
    cas = [
        ("conforme", bon, 0),
        ("sans Contact", bon.replace("Contact: mailto:a@b.fr\n", ""), 1),
        ("Contact en commentaire seulement", bon.replace("Contact:", "# Contact:"), 1),
        ("échéance dans 10 jours", bon.replace("2027-10-01", "2026-11-01"), 1),
        ("échéance passée", bon.replace("2027-10-01", "2026-01-01"), 1),
        ("échéance à deux ans", bon.replace("2027-10-01", "2028-10-01"), 1),
        ("échéance sans fuseau", bon.replace("T00:00:00Z", "T00:00:00"), 1),
        ("échéance illisible", bon.replace("2027-10-01T00:00:00Z", "bientôt"), 1),
        ("deux Expires", bon + "Expires: 2027-10-01T00:00:00Z\n", 1),
        ("Canonical faux", bon.replace(CANONIQUE, "https://exemple.fr/security.txt"), 1),
    ]
    echecs = 0
    for libelle, texte, attendu in cas:
        obtenu = len(juger(texte, t0))
        if (obtenu > 0) != (attendu > 0):
            print(f"ÉCHEC   {libelle} : {obtenu} écart(s), attendu {attendu}")
            echecs += 1
    renouvele = renouveler(bon.replace("2027-10-01", "2026-11-01"), t0)
    if juger(renouvele, t0) or "Expires: 2027-10-22T00:00:00Z" not in renouvele:
        print("ÉCHEC   --renouveler ne rend pas un fichier conforme à un an")
        echecs += 1
    print("selftest : OK" if not echecs else f"selftest : {echecs} échec(s)")
    return OK if not echecs else ECART


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--renouveler", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    try:
        texte = FICHIER.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"INCONNU  {FICHIER} illisible ({e})")
        return INCONNU
    maintenant = datetime.now(timezone.utc)
    if args.renouveler:
        try:
            texte = renouveler(texte, maintenant)
        except ValueError as e:
            print(f"ÉCART    {e}")
            return ECART
        FICHIER.write_text(texte, encoding="utf-8", newline="\n")
    ecarts = juger(texte, maintenant)
    for e in ecarts:
        print(f"ÉCART    security.txt : {e}")
    if not ecarts:
        print("security.txt : conforme")
    return ECART if ecarts else OK


if __name__ == "__main__":
    sys.exit(main())
