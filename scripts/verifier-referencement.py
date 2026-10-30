#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# verifier-referencement.py — ce que les moteurs de recherche, les assistants IA et
# les aperçus de lien lisent du site est-il complet et cohérent ?
#
# Un site sans build recopie ses balises de tête page par page : une page ajoutée
# sans adresse canonique, un sitemap qui oublie une page, un JSON-LD qui ne se lit
# plus ou une balise `noindex` oubliée ne se voient pas à l'écran. Ce contrôle les
# attrape avant le commit (pre-commit) et en CI.
#
# Pour chaque page site/*.html :
#   - <html lang="fr">, un seul <title>, une meta description, un seul <h1> ;
#   - une adresse canonique absolue sur https://coprofirst.fr, et og:url identique ;
#   - og:title, og:description, og:image (fichier présent, PNG 1200 × 630), twitter:card ;
#   - aucun `noindex` ;
#   - chaque bloc application/ld+json est du JSON valide, avec un @context schema.org.
# Les pages d'ERREUR (PAGES_D_ERREUR : 404.html, servie par le Caddyfile) suivent la
# règle inverse : `noindex` obligatoire, ni canonique, ni Open Graph, ni sitemap.
# Elles sont nommées, jamais déduites de leur `noindex` : un `noindex` oublié sur une
# vraie page doit rester un écart, pas une exemption.
# Puis, pour le site :
#   - sitemap.xml liste exactement les adresses canoniques des pages, et le lastmod
#     de chacune n'est pas plus ancien que le dernier commit de la page (git) ;
#   - robots.txt désigne ce sitemap et ne ferme aucun robot (`Disallow: /`) ;
#   - llms.txt commence par un titre, et chacun de ses liens vers coprofirst.fr
#     mène à un fichier du site.
#
# Verdicts (standards/04 §1) : 0 = conforme, 1 = écart, 2 = INCONNU (aucune page
# trouvée). Ce qu'il ne couvre pas : ce que le serveur sert réellement (en-têtes,
# codes de retour) — deploiement/deployer.sh --verifier compare le contenu servi.
#
# Usage : python3 scripts/verifier-referencement.py [--site DOSSIER]
#         python3 scripts/verifier-referencement.py --selftest
import argparse
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

ORIGINE = "https://coprofirst.fr/"
IMAGE_PARTAGE = (1200, 630)
# Servies sur une erreur (deploiement/Caddyfile, handle_errors) : jamais indexées.
PAGES_D_ERREUR = {"404.html"}


class Tete(HTMLParser):
    """Relève ce qu'un robot lit d'une page : langue, titres, balises meta et link,
    blocs JSON-LD."""

    def __init__(self):
        super().__init__()
        self.lang = None
        self.titres = 0
        self.h1 = 0
        self.meta = {}  # name ou property → [contenus]
        self.liens = {}  # rel → [href]
        self.ld = []
        self._dans_ld = False

    def handle_starttag(self, balise, attrs):
        a = dict(attrs)
        if balise == "html":
            self.lang = a.get("lang")
        elif balise == "title":
            self.titres += 1
        elif balise == "h1":
            self.h1 += 1
        elif balise == "meta":
            cle = a.get("name") or a.get("property")
            if cle:
                self.meta.setdefault(cle.lower(), []).append(a.get("content") or "")
        elif balise == "link" and a.get("rel"):
            for rel in a["rel"].lower().split():
                self.liens.setdefault(rel, []).append(a.get("href") or "")
        elif balise == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._dans_ld = True
            self.ld.append("")

    def handle_endtag(self, balise):
        if balise == "script":
            self._dans_ld = False

    def handle_data(self, donnees):
        if self._dans_ld:
            self.ld[-1] += donnees


def adresse_canonique(page: Path) -> str:
    return ORIGINE if page.name == "index.html" else ORIGINE + page.name


def dimensions_png(chemin: Path):
    entete = chemin.read_bytes()[:24]
    if len(entete) < 24 or entete[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", entete[16:24])


# Servis par le site sans être dans le dépôt : deploiement/deployer.sh les envoie.
# avis.json : l'export des avis, jamais versionné.
HORS_DEPOT = {"avis.json"}


def fichier_du_site(site: Path, url: str):
    """Le fichier que sert une adresse de coprofirst.fr, ou None si elle sort du site."""
    if not url.startswith(ORIGINE):
        return None
    chemin = url[len(ORIGINE):].split("#")[0].split("?")[0]
    return site / (chemin or "index.html")


def juger_page(site: Path, page: Path) -> list[str]:
    t = Tete()
    t.feed(page.read_text(encoding="utf-8"))
    nom = page.name
    ecarts = []
    un = lambda cle: (t.meta.get(cle) or [""])[0].strip()  # noqa: E731
    if t.lang != "fr":
        ecarts.append(f"LANGUE   {nom} (<html lang> : {t.lang!r}, attendu 'fr')")
    if t.titres != 1:
        ecarts.append(f"TITRE    {nom} ({t.titres} <title>, attendu 1)")
    if t.h1 != 1:
        ecarts.append(f"H1       {nom} ({t.h1} <h1>, attendu 1)")
    if not un("description"):
        ecarts.append(f"DESCR    {nom} (meta description absente ou vide)")
    ferme = any("noindex" in c.lower() for c in t.meta.get("robots", []) + t.meta.get("googlebot", []))
    if nom in PAGES_D_ERREUR:
        if not ferme:
            ecarts.append(f"OUVERTE  {nom} (page d'erreur sans noindex : les moteurs l'indexeraient)")
        if t.liens.get("canonical"):
            ecarts.append(f"CANON    {nom} (une page d'erreur n'a pas d'adresse canonique)")
        return ecarts
    attendue = adresse_canonique(page)
    canon = t.liens.get("canonical", [])
    if canon != [attendue]:
        ecarts.append(f"CANON    {nom} (canonique {canon}, attendu ['{attendue}'])")
    if un("og:url") != attendue:
        ecarts.append(f"OG       {nom} (og:url {un('og:url')!r}, attendu {attendue!r})")
    for cle in ("og:title", "og:description", "og:image", "twitter:card"):
        if not un(cle):
            ecarts.append(f"OG       {nom} ({cle} absent)")
    image = un("og:image")
    if image:
        f = fichier_du_site(site, image)
        if f is None or not f.is_file():
            ecarts.append(f"IMAGE    {nom} (og:image {image!r} ne mène à aucun fichier du site)")
        elif dimensions_png(f) != IMAGE_PARTAGE:
            ecarts.append(f"IMAGE    {nom} ({f.name} : {dimensions_png(f)}, attendu PNG {IMAGE_PARTAGE})")
    if ferme:
        ecarts.append(f"NOINDEX  {nom} (la page se ferme aux moteurs)")
    for i, bloc in enumerate(t.ld, 1):
        try:
            donnees = json.loads(bloc)
        except json.JSONDecodeError as e:
            ecarts.append(f"JSON-LD  {nom} (bloc {i} illisible : {e})")
            continue
        if not isinstance(donnees, dict) or "schema.org" not in str(donnees.get("@context", "")):
            ecarts.append(f"JSON-LD  {nom} (bloc {i} sans @context schema.org)")
    return ecarts


def juger_site(site: Path):
    pages = sorted(site.glob("*.html"))
    if not pages:
        return None
    ecarts = []
    for page in pages:
        ecarts += juger_page(site, page)

    sitemap = site / "sitemap.xml"
    if not sitemap.is_file():
        ecarts.append("SITEMAP  sitemap.xml absent")
    else:
        try:
            ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            listees = {e.text.strip() for e in ET.parse(sitemap).getroot().findall("s:url/s:loc", ns)}
            attendues = {adresse_canonique(p) for p in pages if p.name not in PAGES_D_ERREUR}
            for u in sorted(attendues - listees):
                ecarts.append(f"SITEMAP  {u} manque à sitemap.xml")
            for u in sorted(listees - attendues):
                ecarts.append(f"SITEMAP  {u} listée dans sitemap.xml sans être une page du site")
        except ET.ParseError as e:
            ecarts.append(f"SITEMAP  sitemap.xml illisible : {e}")

    robots = site / "robots.txt"
    if not robots.is_file():
        ecarts.append("ROBOTS   robots.txt absent")
    else:
        texte = robots.read_text(encoding="utf-8")
        if f"Sitemap: {ORIGINE}sitemap.xml" not in texte.splitlines():
            ecarts.append(f"ROBOTS   robots.txt ne désigne pas {ORIGINE}sitemap.xml")
        if re.search(r"^\s*Disallow:\s*/\s*$", texte, re.M | re.I):
            ecarts.append("ROBOTS   robots.txt ferme le site à un robot (Disallow: /)")

    llms = site / "llms.txt"
    if not llms.is_file():
        ecarts.append("LLMS     llms.txt absent")
    else:
        texte = llms.read_text(encoding="utf-8")
        if not texte.startswith("# "):
            ecarts.append("LLMS     llms.txt ne commence pas par un titre « # »")
        for url in re.findall(r"\((https://coprofirst\.fr/[^)\s]*)\)", texte):
            f = fichier_du_site(site, url)
            if f.relative_to(site).as_posix() in HORS_DEPOT:
                continue
            if not f.is_file():
                ecarts.append(f"LLMS     {url} : aucun fichier du site")
    return ecarts


def lastmod_du_sitemap(site: Path) -> dict:
    """{adresse: lastmod} de sitemap.xml ({} s'il est absent ou illisible : juger_site le dit)."""
    try:
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        return {u.findtext("s:loc", "", ns).strip(): u.findtext("s:lastmod", "", ns).strip()
                for u in ET.parse(site / "sitemap.xml").getroot().findall("s:url", ns)}
    except (OSError, ET.ParseError):
        return {}


def juger_lastmod(lastmods: dict, derniers_commits: dict) -> list[str]:
    """Fonction PURE : un lastmod plus ancien que le dernier commit de sa page ment aux
    moteurs, qui cessent alors de s'y fier pour tout le sitemap. Dates AAAA-MM-JJ."""
    return [f"LASTMOD  {u} : lastmod {lastmods.get(u) or 'absent'}, page modifiée le {d}"
            for u, d in sorted(derniers_commits.items()) if not lastmods.get(u) or lastmods[u] < d]


def derniers_commits(site: Path):
    """{adresse canonique: date du dernier commit de la page}, ou None si git ne répond
    pas. Exige l'historique complet (en CI : fetch-depth 0) — un clone superficiel
    daterait chaque page du dernier commit. Une page modifiée depuis HEAD (indexée ou
    non) est datée d'aujourd'hui : c'est la date du commit qui la portera."""
    dates = {}
    for page in sorted(site.glob("*.html")):
        if page.name in PAGES_D_ERREUR:  # hors du sitemap : pas de lastmod à tenir
            continue
        try:
            lire = lambda *a: subprocess.run(["git", *a, "--", page.name], cwd=site,  # noqa: E731
                                             capture_output=True, text=True, check=True).stdout.strip()
            sortie = date.today().isoformat() if lire("status", "--porcelain") else lire("log", "-1", "--format=%cs")
        except (OSError, subprocess.CalledProcessError):
            return None
        if sortie:  # une page jamais committée n'a pas encore de date
            dates[adresse_canonique(page)] = sortie
    return dates


def selftest() -> int:
    echecs = 0
    for libelle, lastmods, commits, attendu in [
        ("lastmod à jour", {"a": "2026-10-15"}, {"a": "2026-10-15"}, 0),
        ("lastmod plus récent que le commit", {"a": "2026-10-16"}, {"a": "2026-10-15"}, 0),
        ("lastmod en retard", {"a": "2026-10-14"}, {"a": "2026-10-15"}, 1),
        ("lastmod absent", {}, {"a": "2026-10-15"}, 1),
    ]:
        obtenu = len(juger_lastmod(lastmods, commits))
        print(f"  {'ok    ' if obtenu == attendu else 'ÉCHEC '}  {libelle} → {obtenu} écart(s)")
        echecs += obtenu != attendu
    with tempfile.TemporaryDirectory() as d:
        site = Path(d)
        # Une image de partage au bon format : en-tête PNG minimal
        (site / "partage.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + struct.pack(">II", *IMAGE_PARTAGE))
        tete = lambda canon, extra="": (  # noqa: E731
            f'<html lang="fr"><head><title>T</title><meta name="description" content="D">'
            f'<link rel="canonical" href="{canon}"><meta property="og:url" content="{canon}">'
            f'<meta property="og:title" content="T"><meta property="og:description" content="D">'
            f'<meta property="og:image" content="{ORIGINE}partage.png"><meta name="twitter:card" content="summary_large_image">'
            f"{extra}</head><body><h1>T</h1></body></html>")
        (site / "index.html").write_text(tete(ORIGINE, '<script type="application/ld+json">{"@context":"https://schema.org"}</script>'), encoding="utf-8")
        (site / "sitemap.xml").write_text(
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{ORIGINE}</loc></url></urlset>', encoding="utf-8")
        (site / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {ORIGINE}sitemap.xml\n", encoding="utf-8")
        (site / "llms.txt").write_text(f"# CoproFirst\n\n- [Accueil]({ORIGINE})\n", encoding="utf-8")

        def cas(libelle, attendu):
            nonlocal echecs
            obtenu = sorted({e.split()[0] for e in juger_site(site)})
            if obtenu == attendu:
                print(f"  ok      {libelle} → {attendu}")
            else:
                print(f"  ÉCHEC   {libelle} → {obtenu}, attendu {attendu}")
                echecs += 1

        cas("site conforme", [])
        (site / "autre.html").write_text(tete(ORIGINE + "autre.html"), encoding="utf-8")
        cas("page absente du sitemap", ["SITEMAP"])
        (site / "autre.html").write_text(tete(ORIGINE, '<meta name="robots" content="noindex">'), encoding="utf-8")
        cas("canonique fausse et noindex", ["CANON", "NOINDEX", "OG", "SITEMAP"])
        (site / "autre.html").unlink()
        erreur = lambda extra: (  # noqa: E731
            f'<html lang="fr"><head><title>Introuvable</title><meta name="description" content="D">{extra}'
            f'</head><body><h1>Introuvable</h1></body></html>')
        (site / "404.html").write_text(erreur('<meta name="robots" content="noindex">'), encoding="utf-8")
        cas("page d'erreur fermée, hors sitemap", [])
        (site / "404.html").write_text(erreur(""), encoding="utf-8")
        cas("page d'erreur sans noindex", ["OUVERTE"])
        (site / "404.html").write_text(erreur(f'<meta name="robots" content="noindex"><link rel="canonical" href="{ORIGINE}404.html">'), encoding="utf-8")
        cas("page d'erreur avec canonique", ["CANON"])
        (site / "sitemap.xml").write_text(
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{ORIGINE}</loc></url><url><loc>{ORIGINE}404.html</loc></url></urlset>', encoding="utf-8")
        (site / "404.html").write_text(erreur('<meta name="robots" content="noindex">'), encoding="utf-8")
        cas("page d'erreur listée au sitemap", ["SITEMAP"])
        (site / "sitemap.xml").write_text(
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{ORIGINE}</loc></url></urlset>', encoding="utf-8")
        (site / "404.html").unlink()
        (site / "index.html").write_text(tete(ORIGINE, '<script type="application/ld+json">{"@context":</script>'), encoding="utf-8")
        cas("JSON-LD illisible", ["JSON-LD"])
        (site / "index.html").write_text(tete(ORIGINE), encoding="utf-8")
        (site / "robots.txt").write_text("User-agent: GPTBot\nDisallow: /\n", encoding="utf-8")
        cas("robots fermé et sans sitemap", ["ROBOTS"])
        (site / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {ORIGINE}sitemap.xml\n", encoding="utf-8")
        (site / "llms.txt").write_text(f"CoproFirst\n- [x]({ORIGINE}absente.html)\n", encoding="utf-8")
        cas("llms.txt sans titre, lien mort", ["LLMS"])
    # Une page modifiée mais pas encore committée : le commit qui la portera est daté
    # d'aujourd'hui. La dater de son commit précédent laissait passer, en pre-commit, un
    # lastmod en retard que la CI refusait ensuite (main rouge du 25 au 30/10/2026).
    with tempfile.TemporaryDirectory() as d:
        site = Path(d)
        horloge = {**os.environ, "GIT_AUTHOR_DATE": "2026-01-01T12:00:00", "GIT_COMMITTER_DATE": "2026-01-01T12:00:00"}
        git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a],  # noqa: E731
                                        cwd=site, capture_output=True, check=True, env=horloge)
        git("init", "-q")
        (site / "index.html").write_text("a", encoding="utf-8")
        git("add", "index.html")
        git("commit", "-q", "-m", "a")
        for libelle, geste, attendu in [
            ("page committée, intacte", lambda: None, "2026-01-01"),
            ("page modifiée, non indexée", lambda: (site / "index.html").write_text("b", encoding="utf-8"),
             date.today().isoformat()),
            ("page modifiée et indexée", lambda: git("add", "index.html"), date.today().isoformat()),
        ]:
            geste()
            obtenu = (derniers_commits(site) or {}).get(ORIGINE)
            print(f"  {'ok    ' if obtenu == attendu else 'ÉCHEC '}  {libelle} → {obtenu}, attendu {attendu}")
            echecs += obtenu != attendu
    with tempfile.TemporaryDirectory() as d:
        if juger_site(Path(d)) is not None:
            print("  ÉCHEC   dossier sans page → attendu INCONNU")
            echecs += 1
        else:
            print("  ok      dossier sans page → INCONNU")
    print("selftest : OK" if echecs == 0 else f"selftest : {echecs} ÉCHEC(S)")
    return 0 if echecs == 0 else 1


def main() -> int:
    # La console Windows n'est pas en UTF-8 : les accents et les flèches y casseraient l'affichage
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--site", default=str(Path(__file__).resolve().parent.parent / "site"))
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args()
    if args.selftest:
        return selftest()
    site = Path(args.site)
    ecarts = juger_site(site)
    if ecarts is None:
        print(f"INCONNU : aucune page .html dans {args.site} — rien n'a été vérifié")
        return 2
    commits = derniers_commits(site)
    if commits is None:
        print("INCONNU : git ne répond pas — les lastmod du sitemap n'ont pas été vérifiés")
        return 2
    ecarts += juger_lastmod(lastmod_du_sitemap(site), commits)
    if ecarts:
        print("\n".join(ecarts))
        print(f"verifier-referencement : {len(ecarts)} écart(s)")
        return 1
    print(f"verifier-referencement : OK ({len(sorted(Path(args.site).glob('*.html')))} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
