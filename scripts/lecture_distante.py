#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# lecture_distante.py — lire un fichier local ou une adresse https publique, sans
# jeton, pour les contrôles qui comparent le site à CoproFirst
# (verifier-comptes-demo.py, version-produit.py), et le code HTTP d'une adresse
# (verifier-renvois.py). Module, pas commande.
#
# Tout échec de lecture lève Illisible : le contrôle qui l'appelle rend INCONNU
# (standards/04 §1), jamais un vert faute d'avoir pu lire.
import urllib.error
import urllib.request
from pathlib import Path


class Illisible(Exception):
    """Une entrée ne se lit pas : le verdict est INCONNU, jamais OK."""


def _requete(url: str, jeton: str | None = None) -> urllib.request.Request:
    entetes = {"User-Agent": "coprofirst-site-ci"}
    if jeton:
        entetes["Authorization"] = f"Bearer {jeton}"
    return urllib.request.Request(url, headers=entetes)


def statut(url: str, jeton: str | None = None) -> int:
    """Le code HTTP d'une URL https, erreurs comprises (404, 410…). Illisible si le
    serveur ne répond pas : une réponse absente n'est pas un code."""
    try:
        with urllib.request.urlopen(_requete(url, jeton), timeout=30) as reponse:
            return reponse.status
    except urllib.error.HTTPError as e:
        return e.code
    except (OSError, urllib.error.URLError, ValueError) as e:
        raise Illisible(f"{url} : {e}")


def lire(origine: str) -> str:
    """Le texte d'un fichier local ou d'une URL https, sans jeton. Illisible sinon."""
    try:
        if origine.startswith("https://"):
            with urllib.request.urlopen(_requete(origine), timeout=30) as reponse:
                if reponse.status != 200:
                    raise Illisible(f"{origine} : HTTP {reponse.status}")
                octets = reponse.read()
        else:
            octets = Path(origine).read_bytes()
        return octets.decode("utf-8")
    except Illisible:
        raise
    except (OSError, urllib.error.URLError, UnicodeDecodeError, ValueError) as e:
        raise Illisible(f"{origine} : {e}")
