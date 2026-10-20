#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
"""recuperer-avis.py — installe en site/avis.json le dernier export des avis, puis l'efface.

Après « Exporter les avis retenus pour coprofirst.fr » dans l'application, le
navigateur dépose avis-coprofirst-AAAA-MM-JJ.json (ou « … (1).json ») dans les
Téléchargements. deploiement/deployer.sh appelle ce script avant d'envoyer :

  - le plus récent des avis-coprofirst-*.json du dossier est retenu ;
  - identique à site/avis.json : rien à installer ;
  - plus récent et différent : vérifié par scripts/verifier-avis.py dans un fichier
    temporaire, puis installé d'un bloc — un export refusé laisse site/avis.json
    intact ;
  - plus ancien et différent : REFUS (site/avis.json a été installé d'ailleurs ;
    --export CHEMIN pour imposer un fichier) ;
  - aucun export : site/avis.json en place est gardé, et on le dit.

Une fois l'export installé (ou déjà en place), TOUS les avis-coprofirst-*.json du
dossier sont effacés : ce sont des copies de données personnelles, dont des avis
dont l'accord a pu être retiré depuis, et site/avis.json fait foi. Avec --export,
seul ce fichier s'efface, et seulement s'il est dans le dossier.

Sortie : 0 prêt à déployer, 1 refus (rien n'est changé).
Usage : python3 scripts/recuperer-avis.py [--export CHEMIN] [--dossier DOSSIER] | --selftest
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CIBLE = RACINE / "site" / "avis.json"
VERIFIER = RACINE / "scripts" / "verifier-avis.py"
MOTIF = "avis-coprofirst-*.json"


def telechargements() -> Path:
    """Le dossier Téléchargements de l'utilisateur, sans chemin écrit en dur."""
    base = os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())
    return Path(base) / "Downloads"


def exports(dossier: Path) -> list[Path]:
    """Les exports du dossier, du plus récent au plus ancien (« (1) » compris)."""
    if not dossier.is_dir():
        return []
    return sorted(dossier.glob(MOTIF), key=lambda p: p.stat().st_mtime, reverse=True)


def conforme(chemin: Path) -> bool:
    return subprocess.run([sys.executable, str(VERIFIER), "--fichier", str(chemin)]).returncode == 0


def recuperer(dossier: Path, cible: Path, explicite: Path | None = None, verifier=conforme) -> int:
    """Installe l'export retenu en `cible`, puis efface les exports du dossier. Rend 0 ou 1."""
    trouves = exports(dossier)
    if explicite is not None:
        if not explicite.is_file():
            print(f"REFUS : {explicite} introuvable.")
            return 1
        source = explicite
    elif trouves:
        source = trouves[0]
    else:
        etat = "gardé tel quel" if cible.is_file() else "ABSENT"
        print(f"Aucun export dans {dossier} : {cible.name} en place {etat}.")
        return 0

    donnees = source.read_bytes()
    if cible.is_file() and cible.read_bytes() == donnees:
        print(f"{source.name} : identique à {cible.name}, rien à installer.")
    else:
        if (explicite is None and cible.is_file()
                and source.stat().st_mtime < cible.stat().st_mtime):
            print(f"REFUS : {source.name} est plus ancien que {cible.name} et en diffère.")
            print("  Exporter de nouveau, ou imposer un fichier : --export CHEMIN.")
            return 1
        # Vérifié AVANT d'installer, dans le dossier de la cible (même disque :
        # le remplacement est d'un bloc) — un refus ne touche pas à la cible.
        fd, temp = tempfile.mkstemp(prefix=".avis-", suffix=".json", dir=cible.parent)
        with os.fdopen(fd, "wb") as f:
            f.write(donnees)
        if not verifier(Path(temp)):
            os.remove(temp)
            print(f"REFUS : {source.name} non conforme (ci-dessus) — {cible.name} inchangé, export gardé.")
            return 1
        os.replace(temp, cible)
        print(f"{source.name} installé en {cible.relative_to(cible.parent.parent).as_posix()}.")

    # Avec --export, seul ce fichier s'efface, et seulement s'il est dans le dossier.
    effacer = trouves if explicite is None else [p for p in trouves if p.resolve() == explicite.resolve()]
    for p in effacer:
        p.unlink()
        print(f"Effacé de {dossier} : {p.name} (copie de données personnelles ; {cible.name} fait foi).")
    return 0


def selftest() -> int:
    echecs = 0
    VIDE = b'{"genere_le":"2026-10-18","avis":[]}'
    UN = b'{"genere_le":"2026-10-20","avis":[{"auteur":"Alain G."}]}'
    DEUX = b'{"genere_le":"2026-10-21","avis":[{"auteur":"Alain G."},{"auteur":"Zo\xc3\xa9 Z."}]}'
    refuse_deux = lambda p: p.read_bytes() != DEUX  # « verifier-avis » simulé

    def cas(nom, prepare, attendu_code, attendu_cible, attendu_restants, explicite=None, garde=None):
        nonlocal echecs
        with tempfile.TemporaryDirectory() as t:
            dossier, site = Path(t) / "Downloads", Path(t) / "site"
            dossier.mkdir(); site.mkdir()
            cible = site / "avis.json"
            exp = prepare(dossier, cible)
            code = recuperer(dossier, cible, exp if explicite else None, verifier=refuse_deux)
            obtenu = (code, cible.read_bytes() if cible.exists() else None,
                      sorted(p.name for p in dossier.iterdir()),
                      sorted(p.name for p in site.iterdir() if p.name != "avis.json"),
                      exp.exists() if explicite else None)
            ok = obtenu == (attendu_code, attendu_cible, attendu_restants, [], garde)
            echecs += not ok
            print(f"  {'ok     ' if ok else 'ÉCHEC  '} {nom}" + ("" if ok else f" → {obtenu}"))

    def ecrire(p: Path, contenu: bytes, age: int = 0):
        p.write_bytes(contenu)
        t = time.time() - age
        os.utime(p, (t, t))
        return p

    cas("aucun export : cible gardée",
        lambda d, c: ecrire(c, VIDE) and None, 0, VIDE, [])
    cas("aucun export, aucune cible",
        lambda d, c: None, 0, None, [])
    cas("export plus récent : installé, exports effacés",
        lambda d, c: (ecrire(c, VIDE, 300), ecrire(d / "avis-coprofirst-2026-10-18.json", VIDE, 600),
                      ecrire(d / "avis-coprofirst-2026-10-20.json", UN, 60)) and None,
        0, UN, [])
    cas("la variante « (1) » la plus récente gagne",
        lambda d, c: (ecrire(c, VIDE, 300), ecrire(d / "avis-coprofirst-2026-10-20.json", VIDE, 120),
                      ecrire(d / "avis-coprofirst-2026-10-20 (1).json", UN, 60)) and None,
        0, UN, [])
    cas("identique : rien installé, export effacé",
        lambda d, c: (ecrire(c, UN, 300), ecrire(d / "avis-coprofirst-2026-10-20.json", UN, 60)) and None,
        0, UN, [])
    cas("export refusé : cible intacte, export gardé, aucun temporaire",
        lambda d, c: (ecrire(c, UN, 300), ecrire(d / "avis-coprofirst-2026-10-21.json", DEUX, 60)) and None,
        1, UN, ["avis-coprofirst-2026-10-21.json"])
    cas("export plus ancien et différent : refus",
        lambda d, c: (ecrire(c, UN, 60), ecrire(d / "avis-coprofirst-2026-10-18.json", VIDE, 300)) and None,
        1, UN, ["avis-coprofirst-2026-10-18.json"])
    cas("fichiers voisins jamais touchés",
        lambda d, c: (ecrire(c, VIDE, 300), ecrire(d / "photo.json", VIDE), ecrire(d / "avis-coprofirst-2026-10-20.json", UN, 60)) and None,
        0, UN, ["photo.json"])
    cas("--export hors du dossier : installé, jamais effacé",
        lambda d, c: (ecrire(c, UN, 60), ecrire(d.parent / "ailleurs.json", VIDE, 300))[1],
        0, VIDE, [], explicite=True, garde=True)
    cas("--export introuvable : refus",
        lambda d, c: (ecrire(c, UN), d.parent / "absent.json")[1],
        1, UN, [], explicite=True, garde=False)
    print("selftest : OK" if echecs == 0 else f"selftest : {echecs} ÉCHEC(S)")
    return 1 if echecs else 0


if __name__ == "__main__":
    # La console Windows est en cp1252 : sans cela, « … » ou « é » font tomber le script.
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if args == ["--selftest"]:
        sys.exit(selftest())
    explicite, dossier = None, telechargements()
    while args:
        if args[0] == "--export" and len(args) > 1:
            explicite, args = Path(args[1]), args[2:]
        elif args[0] == "--dossier" and len(args) > 1:
            dossier, args = Path(args[1]), args[2:]
        else:
            print("Usage : python3 scripts/recuperer-avis.py [--export CHEMIN] [--dossier DOSSIER] | --selftest")
            sys.exit(1)
    sys.exit(recuperer(dossier, CIBLE, explicite))
