#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# lecture_distante.py — lire un fichier local ou une adresse https publique (sans
# jeton, sauf celui de la CI pour l'API de GitHub), pour les contrôles qui comparent
# le site à CoproFirst (verifier-comptes-demo.py, version-produit.py), et le code
# HTTP d'une adresse (verifier-renvois.py). Module, pas commande.
#
# Tout échec de lecture lève Illisible : le contrôle qui l'appelle rend INCONNU
# (standards/04 §1), jamais un vert faute d'avoir pu lire.
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Une erreur passagère de GitHub (500, 502, 504, push refusé, limite de débit) ne doit
# pas ouvrir un ticket « CI rouge » : trois essais, avec une attente entre eux
# (coprofirst-site#63 : trois tickets en 36 h, chaque fois verts à la relance).
ATTENTES = (2, 6)  # secondes avant le 2ᵉ et le 3ᵉ essai
HOTE_AVEC_JETON = "api.github.com"  # le seul hôte à qui un jeton d'environnement est envoyé


class Illisible(Exception):
    """Une entrée ne se lit pas : le verdict est INCONNU, jamais OK."""


class _MemeHote(urllib.request.HTTPRedirectHandler):
    """Une requête à jeton ne suit jamais une redirection vers un autre hôte :
    l'en-tête Authorization ne doit pas la suivre (standards/03)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if req.has_header("Authorization") and urllib.parse.urlsplit(newurl).hostname != urllib.parse.urlsplit(req.full_url).hostname:
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OUVREUR = urllib.request.build_opener(_MemeHote)


def _requete(url: str, jeton: str | None = None) -> urllib.request.Request:
    """Le jeton explicite part toujours ; celui de l'environnement (GH_TOKEN, posé par
    la CI) ne part qu'à l'API de GitHub : sans lui, l'IP partagée du runner épuise la
    limite des appels anonymes (403, coprofirst-site#69)."""
    if not jeton and urllib.parse.urlsplit(url).hostname == HOTE_AVEC_JETON:
        jeton = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    entetes = {"User-Agent": "coprofirst-site-ci"}
    if jeton:
        entetes["Authorization"] = f"Bearer {jeton}"
    return urllib.request.Request(url, headers=entetes)


def _passagere(code: int, entetes) -> bool:
    """Un code qui vaut la peine d'un nouvel essai : serveur en panne, trop de requêtes,
    limite de débit (403 avec un quota épuisé). 404, 410, 403 ordinaire : non."""
    return code >= 500 or code == 429 or (code == 403 and entetes.get("x-ratelimit-remaining") == "0")


def _ouvrir(url: str, jeton: str | None = None) -> tuple[int, bytes]:
    """(code, corps) d'une URL, erreurs HTTP comprises. Réessaie ce qui est passager ;
    une erreur HTTP qui dure est rendue telle quelle, un serveur qui ne répond pas
    lève Illisible (une réponse absente n'est pas un code)."""
    resultat: tuple[int, bytes] | None = None
    erreur = ""
    for essai in range(len(ATTENTES) + 1):
        if essai:
            time.sleep(ATTENTES[essai - 1])
        try:
            with _OUVREUR.open(_requete(url, jeton), timeout=30) as reponse:
                return reponse.status, reponse.read()
        except urllib.error.HTTPError as e:
            resultat, erreur = (e.code, e.read()), f"HTTP {e.code}"
            if not _passagere(e.code, e.headers):
                return resultat
        except ValueError as e:
            raise Illisible(f"{url} : {e}")
        except OSError as e:  # URLError, délai dépassé, connexion coupée
            resultat, erreur = None, str(e)
    if resultat is not None:
        return resultat
    raise Illisible(f"{url} : {erreur} (après {len(ATTENTES) + 1} essais)")


def statut(url: str, jeton: str | None = None) -> int:
    """Le code HTTP d'une URL https, erreurs comprises (404, 410…). Illisible si le
    serveur ne répond pas : une réponse absente n'est pas un code."""
    return _ouvrir(url, jeton)[0]


def lire(origine: str) -> str:
    """Le texte d'un fichier local ou d'une URL https. Illisible sinon."""
    try:
        if origine.startswith("https://"):
            code, octets = _ouvrir(origine)
            if code != 200:
                raise Illisible(f"{origine} : HTTP {code}")
        else:
            octets = Path(origine).read_bytes()
        return octets.decode("utf-8")
    except Illisible:
        raise
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise Illisible(f"{origine} : {e}")


def selftest() -> int:
    """Un serveur local qui échoue de façon contrôlée : chaque règle de réessai est jouée."""
    from http.server import BaseHTTPRequestHandler, HTTPServer

    appels: dict[str, int] = {}
    entetes_vus: dict[str, str | None] = {}

    class Serveur(BaseHTTPRequestHandler):
        def do_GET(self):
            n = appels[self.path] = appels.get(self.path, 0) + 1
            entetes_vus[self.path] = self.headers.get("Authorization")
            code, extra = 200, {}
            if self.path == "/panne-passagere" and n <= 2:
                code = 502
            elif self.path == "/toujours-500":
                code = 500
            elif self.path == "/limite" and n == 1:
                code, extra = 403, {"x-ratelimit-remaining": "0"}
            elif self.path == "/interdit":
                code = 403
            elif self.path == "/absent":
                code = 404
            elif self.path == "/ailleurs":
                code, extra = 302, {"Location": f"http://localhost:{self.server.server_port}/arrivee"}
            self.send_response(code)
            for cle, valeur in extra.items():
                self.send_header(cle, valeur)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *_):
            pass

    serveur = HTTPServer(("127.0.0.1", 0), Serveur)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{serveur.server_port}"
    global ATTENTES
    ATTENTES, avant = (0, 0), ATTENTES
    echecs = 0

    def verifie(nom, ok):
        nonlocal echecs
        echecs += not ok
        print(f"  {'ok     ' if ok else 'ÉCHEC  '} {nom}")

    try:
        verifie("200 d'emblée : un seul appel", statut(base + "/ok") == 200 and appels["/ok"] == 1)
        verifie("502 deux fois puis 200 → 200 au 3ᵉ essai", statut(base + "/panne-passagere") == 200 and appels["/panne-passagere"] == 3)
        verifie("500 qui dure → 500 rendu après 3 essais", statut(base + "/toujours-500") == 500 and appels["/toujours-500"] == 3)
        verifie("403 limite de débit puis 200 → réessayé", statut(base + "/limite") == 200 and appels["/limite"] == 2)
        verifie("403 ordinaire → rendu sans réessai", statut(base + "/interdit") == 403 and appels["/interdit"] == 1)
        verifie("404 → rendu sans réessai", statut(base + "/absent") == 404 and appels["/absent"] == 1)
        verifie("redirection vers un autre hôte suivie sans jeton", statut(base + "/ailleurs") == 200)
        verifie("… jamais avec un jeton", statut(base + "/ailleurs", "secret") == 302 and entetes_vus.get("/arrivee") is None)
        port_mort = HTTPServer(("127.0.0.1", 0), Serveur)
        adresse_morte = f"http://127.0.0.1:{port_mort.server_port}/"
        port_mort.server_close()
        try:
            statut(adresse_morte)
            verifie("serveur injoignable → Illisible", False)
        except Illisible:
            verifie("serveur injoignable → Illisible, jamais un code", True)
    finally:
        ATTENTES = avant
        serveur.shutdown()
    environ = os.environ.copy()
    try:
        os.environ["GH_TOKEN"] = "jeton-ci"
        verifie("jeton d'environnement envoyé à api.github.com", _requete("https://api.github.com/x").get_header("Authorization") == "Bearer jeton-ci")
        verifie("… et à aucun autre hôte", _requete("https://raw.githubusercontent.com/x").get_header("Authorization") is None)
        verifie("… ni à un hôte qui l'imite", _requete("https://api.github.com.evil.fr/x").get_header("Authorization") is None)
        verifie("jeton explicite toujours envoyé", _requete("https://exemple.fr/x", "a").get_header("Authorization") == "Bearer a")
    finally:
        os.environ.clear()
        os.environ.update(environ)
    print("selftest : OK" if echecs == 0 else f"selftest : {echecs} ÉCHEC(S)")
    return 1 if echecs else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(selftest())
    print("Module. Usage : python3 scripts/lecture_distante.py --selftest")
    sys.exit(1)
