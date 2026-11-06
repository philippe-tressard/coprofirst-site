#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# dates_pages.py — la date que le lastmod d'une page doit atteindre, lue dans git.
# Module de verifier-referencement.py (qui lance son selftest).
#
# La règle : la date du dernier commit qui a changé la page. Trois précisions :
#   1. Une page modifiée et pas encore committée compte pour AUJOURD'HUI : c'est la
#      date du commit qui la portera (main rouge du 25 au 30/10/2026, sinon).
#   2. git se lance sans les variables qu'un hook exporte (GIT_DIR, GIT_INDEX_FILE…) :
#      depuis site/, il prendrait site/ pour la racine de l'arbre de travail (faux
#      écarts au pre-commit d'un worktree lié, 03/11/2026).
#   3. Un commit de SQUASH (« … (#N) » en fin de sujet) porte la date de la fusion,
#      qu'aucune PR ne peut écrire d'avance : une PR verte rendait main rouge quand on
#      la fusionnait le lendemain (quatre fois entre le 25/10 et le 06/11/2026). Sa
#      page prend alors la date du dernier commit de la PR qui la touche (lu dans
#      refs/pull/N/head d'origin), si la page du squash est celle de la PR. Sinon —
#      la page a aussi changé sur main entre-temps — la date du squash reste.
#      Arbitrage du 06/11/2026 : ni tolérance de N jours (une page vraiment oubliée
#      passerait), ni fusion sans squash (la façon de fusionner reste à Philippe), ni
#      robot (une PR de plus à chaque fusion).
# Le réseau n'est lu que pour un squash dont la page aurait sinon un écart : un
# lastmod déjà à la date du squash ne demande rien. PR introuvable → INCONNU, jamais
# OK (standards/04 §1), et jamais un faux écart non plus.
import os
import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path

SQUASH = re.compile(r"\(#(\d+)\)$")


def env_git():
    """L'environnement sans les variables qui désignent un dépôt (leur liste est celle
    de `git rev-parse --local-env-vars`, jamais recopiée ici), ou None si git ne
    répond pas. Sans elles, git redécouvre le dépôt depuis son répertoire courant."""
    try:
        locales = subprocess.run(["git", "rev-parse", "--local-env-vars"],
                                 capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        return None
    return {k: v for k, v in os.environ.items() if k not in locales}


def date_dans_la_pr(git, page: str, squash: str, numero: str):
    """(date, None) : la date du dernier commit de la PR qui touche la page ;
    (None, None) : la page du squash n'est pas celle de la PR, la date du squash reste ;
    (None, raison) : la PR ne se lit pas — INCONNU."""
    try:
        tete = git("ls-remote", "origin", f"refs/pull/{numero}/head").split("\t")[0]
    except subprocess.CalledProcessError as e:
        return None, f"origin illisible ({e.stderr.strip() or e})"
    if not tete:
        return None, f"PR {numero} introuvable sur origin"
    try:
        try:
            git("cat-file", "-e", f"{tete}^{{commit}}")
        except subprocess.CalledProcessError:
            git("fetch", "-q", "--no-tags", "--no-write-fetch-head", "origin", tete)
        if git("rev-parse", f"{squash}:./{page}") != git("rev-parse", f"{tete}:./{page}"):
            return None, None
        return git("log", "-1", "--format=%cs", tete, "--", page) or None, None
    except subprocess.CalledProcessError as e:
        return None, f"PR {numero} illisible ({e.stderr.strip() or e})"


def dates_des_pages(pages: list[Path], plancher: dict):
    """({nom de page: date AAAA-MM-JJ}, [INCONNU…]), ou None si git ne répond pas.
    plancher : {nom de page: lastmod} — un squash ne se résout que si son lastmod est
    plus ancien que lui. Exige l'historique complet (en CI : fetch-depth 0)."""
    env = env_git()
    if env is None:
        return None
    dates, inconnus = {}, []
    for page in pages:
        def git(*a):  # depuis le dossier de la page, comme un humain le lancerait
            return subprocess.run(["git", *a], cwd=page.parent, env=env,
                                  capture_output=True, text=True, check=True).stdout.strip()
        try:
            if git("status", "--porcelain", "--", page.name):
                dates[page.name] = date.today().isoformat()
                continue
            ligne = git("log", "-1", "--format=%H%x00%cs%x00%s", "--", page.name)
        except (OSError, subprocess.CalledProcessError):
            return None
        if not ligne:  # une page jamais committée n'a pas encore de date
            continue
        sha, jour, sujet = ligne.split("\x00", 2)
        squash = SQUASH.search(sujet)
        if squash and (plancher.get(page.name) or "") < jour:
            dans_la_pr, raison = date_dans_la_pr(git, page.name, sha, squash.group(1))
            if raison:
                inconnus.append(f"INCONNU  {page.name} : squash {sha[:7]} du {jour}, {raison}")
                continue
            jour = dans_la_pr or jour
        dates[page.name] = jour
    return dates, inconnus


def selftest() -> int:
    echecs = 0

    def cas(libelle, obtenu, attendu):
        nonlocal echecs
        print(f"  {'ok    ' if obtenu == attendu else 'ÉCHEC '}  {libelle} → {obtenu}, attendu {attendu}")
        echecs += obtenu != attendu

    # Un dépôt dont le site est dans un sous-dossier (le piège de GIT_DIR), et un
    # « origin » local qui porte les refs/pull/N/head de GitHub : le vrai chemin de
    # code, sans réseau. env_git() : lancé depuis un hook, ces dépôts jetables
    # écriraient sinon dans le vrai.
    with tempfile.TemporaryDirectory() as d:
        origine, racine = Path(d) / "origine", Path(d) / "depot"
        site = racine / "site"
        site.mkdir(parents=True)

        def git(*a, jour="2026-01-01", cwd=racine):
            heure = f"{jour}T12:00:00"
            env = {**(env_git() or {}), "GIT_AUTHOR_DATE": heure, "GIT_COMMITTER_DATE": heure}
            return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a],
                                  cwd=cwd, capture_output=True, check=True, env=env)

        def ecrire(nom, texte):
            (site / nom).write_text(texte, encoding="utf-8")

        def commit(message, jour, *noms):
            git("add", *[f"site/{n}" for n in noms])
            git("commit", "-q", "-m", message, jour=jour)

        def pr(numero, jour, **pages):
            """Une PR partie de main : ses pages, committées ce jour-là, publiées en
            refs/pull/N/head sur origin, puis retour sur main."""
            git("switch", "-q", "-c", f"pr{numero}")
            for nom, texte in pages.items():
                ecrire(nom, texte)
            commit(f"travail de la PR {numero}", jour, *pages)
            git("push", "-q", "origin", f"pr{numero}:refs/pull/{numero}/head")
            git("switch", "-q", "main")

        def squash(titre, numero):  # le sujet que GitHub donne à un squash
            return f"{titre} (#{numero})"

        def dates(**plancher):
            return dates_des_pages(sorted(site.glob("*.html")), plancher) or ({}, ["git muet"])

        git("init", "-q", "--bare", str(origine), cwd=d)
        git("init", "-q", "-b", "main")
        git("remote", "add", "origin", str(origine))
        ecrire("index.html", "a")
        ecrire("autre.html", "a")
        commit("départ", "2026-01-01", "index.html", "autre.html")
        cas("page committée, intacte", dates()[0].get("index.html"), "2026-01-01")
        ancien = os.environ.get("GIT_DIR")
        os.environ["GIT_DIR"] = str(racine / ".git")  # ce que git exporte au pre-commit d'un worktree lié
        try:
            cas("page committée, GIT_DIR posé par un hook", dates()[0].get("index.html"), "2026-01-01")
        finally:
            if ancien is None:
                os.environ.pop("GIT_DIR", None)
            else:
                os.environ["GIT_DIR"] = ancien

        # PR 7 écrite le 02/01, squashée le lendemain : son lastmod du 02/01 est juste.
        pr(7, "2026-01-02", **{"index.html": "b"})
        ecrire("index.html", "b")
        commit(squash("titre de la PR", 7), "2026-01-03", "index.html")
        cas("squash du lendemain, lastmod de la PR", dates(**{"index.html": "2026-01-02"})[0].get("index.html"),
            "2026-01-02")
        cas("squash du lendemain, lastmod vraiment en retard → date de la PR",
            dates(**{"index.html": "2026-01-01"})[0].get("index.html"), "2026-01-02")
        cas("squash, lastmod déjà au jour du squash (rien à lire)",
            dates(**{"index.html": "2026-01-03"})[0].get("index.html"), "2026-01-03")
        # Squash d'une PR absente d'origin : ni OK ni écart, INCONNU.
        ecrire("autre.html", "b")
        commit(squash("PR disparue", 8), "2026-01-03", "autre.html")
        cas("squash d'une PR introuvable", [i.split()[0] for i in dates(**{"autre.html": "2026-01-01"})[1]],
            ["INCONNU"])
        # La page du squash n'est pas celle de la PR (main l'a aussi changée) : stricte.
        pr(9, "2026-01-02", **{"autre.html": "c"})
        ecrire("autre.html", "d")
        commit(squash("PR mêlée à main", 9), "2026-01-04", "autre.html")
        cas("squash dont la page diffère de la PR", dates()[0].get("autre.html"), "2026-01-04")
        # Hors PR : règle stricte.
        ecrire("autre.html", "e")
        commit("correctif direct sur main", "2026-01-05", "autre.html")
        cas("commit hors PR", dates()[0].get("autre.html"), "2026-01-05")
        # Une page modifiée mais pas encore committée compte pour aujourd'hui.
        ecrire("index.html", "z")
        cas("page modifiée, non indexée", dates()[0].get("index.html"), date.today().isoformat())
        git("add", "site/index.html")
        cas("page modifiée et indexée", dates()[0].get("index.html"), date.today().isoformat())
    return echecs
