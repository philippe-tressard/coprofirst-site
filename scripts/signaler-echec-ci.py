#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# signaler-echec-ci.py — un workflow rouge sur main, ou un passage planifié qui
# échoue, ouvre un ticket : la trace qu'on ne peut pas manquer (standards/07 §1).
#
# Le 30/10/2026, la CI était rouge sur main depuis cinq jours, et le passage
# quotidien de la concordance depuis sept, sans que personne ne le voie : le
# courriel de GitHub sur un workflow planifié ne partait pas, ou ne se lisait pas.
# Un ticket, lui, compte parmi les issues ouvertes que chaque
# session trie.
#
# Quand : un passage planifié (schedule, toujours sur main), ou un push ou un
# lancement à la main (workflow_dispatch) sur main. Jamais sur une PR ni une autre
# branche — la branche du robot de version-produit.yml comprise, dont la CI tourne
# sur sa PR : son auteur voit le rouge là où il travaille.
# Dédoublonnage : un seul ticket ouvert par workflow, reconnu à son titre exact ; un
# échec suivant y ajoute un commentaire, au plus un toutes les DELAI_HEURES : un
# passage horaire en échec ferait sinon 24 messages par jour (standards/07 §3).
# Le ticket se ferme à la main, avec le passage revenu au vert qui le prouve.
#
# Usage (le pas final de chaque job, `if: failure()`, GH_TOKEN posé) :
#         python3 scripts/signaler-echec-ci.py --signaler
#         python3 scripts/signaler-echec-ci.py --verifier   chaque job a ce pas final
#         python3 scripts/signaler-echec-ci.py --selftest
# Sortie : 0 rien à signaler ou signalé, 1 écart (--verifier) ou envoi impossible.
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
WORKFLOWS = RACINE / ".github" / "workflows"
SCRIPT = "scripts/signaler-echec-ci.py"
ETIQUETTES = ("bug", "priorité haute")
DELAI_HEURES = 12


def titre(workflow: str) -> str:
    return f"CI rouge : {workflow}"


def decider(evenement: str, ref: str, workflow: str, ouverts: list[dict], maintenant: datetime):
    """Fonction PURE. ("rien", raison) | ("creer", titre) | ("commenter", numéro).
    ouverts : les tickets ouverts, {number, title, updatedAt (ISO 8601)}."""
    if evenement != "schedule" and not (evenement in ("push", "workflow_dispatch") and ref == "refs/heads/main"):
        return ("rien", f"{evenement} sur {ref} : le rouge se voit là où l'on travaille")
    for ticket in ouverts:
        if ticket.get("title") == titre(workflow):
            vu = datetime.fromisoformat(ticket.get("updatedAt", "1970-01-01T00:00:00Z").replace("Z", "+00:00"))
            if maintenant - vu < timedelta(hours=DELAI_HEURES):
                return ("rien", f"déjà signalé au ticket {ticket['number']} il y a moins de {DELAI_HEURES} h")
            return ("commenter", ticket["number"])
    return ("creer", titre(workflow))


def corps(env: dict) -> str:
    """L'exécution courante, et elle seule (standards/07 §4)."""
    adresse = f"{env.get('GITHUB_SERVER_URL', 'https://github.com')}/{env.get('GITHUB_REPOSITORY', '?')}"
    return (f"Le workflow « {env.get('GITHUB_WORKFLOW', '?')} » a échoué "
            f"({env.get('GITHUB_EVENT_NAME', '?')}, commit {env.get('GITHUB_SHA', '?')[:7]}) : "
            f"{adresse}/actions/runs/{env.get('GITHUB_RUN_ID', '?')}\n\n"
            f"Signalé par `{SCRIPT}`. Un échec suivant du même workflow s'ajoute ici en "
            f"commentaire ; fermer quand il est revenu au vert, avec le passage qui le prouve.")


def signaler(env: dict, gh) -> int:
    """gh(liste d'arguments) -> stdout, ou lève CalledProcessError. Injecté pour le selftest."""
    depot = env.get("GITHUB_REPOSITORY", "")
    workflow = env.get("GITHUB_WORKFLOW", "")
    if not depot or not workflow:
        print("::error::GITHUB_REPOSITORY ou GITHUB_WORKFLOW absent : rien n'a été signalé")
        return 1
    try:
        ouverts = json.loads(gh(["issue", "list", "-R", depot, "--state", "open",
                                 "--limit", "200", "--json", "number,title,updatedAt"]))
        geste, valeur = decider(env.get("GITHUB_EVENT_NAME", ""), env.get("GITHUB_REF", ""), workflow, ouverts,
                                datetime.now(timezone.utc))
        if geste == "rien":
            print(f"signaler-echec-ci : rien à signaler ({valeur})")
            return 0
        if geste == "commenter":
            gh(["issue", "comment", str(valeur), "-R", depot, "--body", corps(env)])
            print(f"signaler-echec-ci : commentaire ajouté au ticket {depot}#{valeur}")
            return 0
        base = ["issue", "create", "-R", depot, "--title", valeur, "--body", corps(env)]
        try:
            print(gh(base + [a for e in ETIQUETTES for a in ("--label", e)]).strip())
        except subprocess.CalledProcessError:
            # Une étiquette renommée ne doit pas taire l'alerte : le ticket part sans elle.
            print(gh(base).strip())
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        print(f"::error::signaler-echec-ci : le ticket n'a pas pu être ouvert ({e})")
        return 1


def gh_reel(args: list[str]) -> str:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


def verifier(dossier: Path) -> list[str]:
    """Chaque job de chaque workflow finit par le pas `if: failure()` qui lance ce
    script : un workflow ajouté sans lui serait de nouveau un rouge muet."""
    ecarts = []
    fichiers = sorted(dossier.glob("*.yml")) + sorted(dossier.glob("*.yaml"))
    if not fichiers:
        return [f"INCONNU  aucun workflow dans {dossier}"]
    for f in fichiers:
        texte = f.read_text(encoding="utf-8")
        jobs = len(re.findall(r"^\s+runs-on:", texte, re.M))
        pas = re.findall(r"^\s+- [^\n]*(?:\n(?!\s+- )[^\n]*)*", texte, re.M)
        alertes = [p for p in pas if SCRIPT in p and "--signaler" in p]
        if len(alertes) != jobs or not all(re.search(r"if: failure\(\)\s*$", p, re.M) for p in alertes):
            ecarts.append(f"ALERTE   {f.name} : {jobs} job(s), {len(alertes)} pas `if: failure()` → {SCRIPT} --signaler")
        if not re.search(r"^\s+issues: write\s*(?:#.*)?$", texte, re.M):
            ecarts.append(f"DROIT    {f.name} : permissions sans `issues: write`, le ticket ne pourrait pas s'ouvrir")
        # Le pas d'alerte est le dernier de son job : un pas après lui ne serait pas couvert.
        for job in re.split(r"^  [\w-]+:\s*$", texte, flags=re.M)[1:]:
            etapes = re.findall(r"^\s+- (?:name|uses|run|if):", job, re.M)
            if etapes and SCRIPT not in job[job.rfind(etapes[-1]):]:
                ecarts.append(f"ORDRE    {f.name} : le pas d'alerte n'est pas le dernier du job")
    return ecarts


def selftest() -> int:
    echecs = 0

    def cas(libelle, obtenu, attendu):
        nonlocal echecs
        print(f"  {'ok    ' if obtenu == attendu else 'ÉCHEC '}  {libelle} → {obtenu}")
        echecs += obtenu != attendu

    t = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)
    ouvert = [{"number": 7, "title": titre("CI"), "updatedAt": "2026-11-05T06:00:00Z"},
              {"number": 8, "title": "autre", "updatedAt": "2026-11-06T11:00:00Z"}]
    recent = [{"number": 7, "title": titre("CI"), "updatedAt": "2026-11-06T11:30:00Z"}]
    cas("push sur main, aucun ticket", decider("push", "refs/heads/main", "CI", [], t)[0], "creer")
    cas("passage planifié, ticket ouvert hier", decider("schedule", "refs/heads/main", "CI", ouvert, t), ("commenter", 7))
    cas("passage horaire, signalé il y a 30 min", decider("schedule", "refs/heads/main", "CI", recent, t)[0], "rien")
    cas("lancé à la main sur main", decider("workflow_dispatch", "refs/heads/main", "X", ouvert, t)[0], "creer")
    cas("lancé à la main sur une autre branche", decider("workflow_dispatch", "refs/heads/version", "CI", [], t)[0], "rien")
    cas("pull request", decider("pull_request", "refs/pull/3/merge", "CI", [], t)[0], "rien")
    cas("push sur une autre branche", decider("push", "refs/heads/fix/x", "CI", [], t)[0], "rien")

    # L'envoi lui-même, gh simulé : prouve que la commande part, et laquelle.
    env = {"GITHUB_REPOSITORY": "o/d", "GITHUB_WORKFLOW": "CI", "GITHUB_EVENT_NAME": "schedule",
           "GITHUB_REF": "refs/heads/main", "GITHUB_RUN_ID": "42", "GITHUB_SHA": "abcdef0123"}

    def simule(ouverts, refuse_etiquette=False, panne=False):
        appels = []

        def gh(args):
            appels.append(args)
            if panne:
                raise subprocess.CalledProcessError(1, "gh")
            if args[:2] == ["issue", "list"]:
                return json.dumps(ouverts)
            if refuse_etiquette and "--label" in args:
                raise subprocess.CalledProcessError(1, "gh")
            return "https://github.com/o/d/issues/9\n"
        return signaler(env, gh), [a[:2] + (["--label"] if "--label" in a else []) for a in appels], appels

    code, gestes, appels = simule([])
    cas("création : la commande part", (code, gestes[-1]), (0, ["issue", "create", "--label"]))
    cas("création : le corps cite le passage", "/o/d/actions/runs/42" in appels[-1][appels[-1].index("--body") + 1], True)
    cas("dédoublonnage : commentaire", simule(ouvert)[1][-1], ["issue", "comment"])
    code, gestes, _ = simule([], refuse_etiquette=True)
    cas("étiquette refusée : le ticket part sans elle", (code, gestes[-1]), (0, ["issue", "create"]))
    cas("gh en panne : sortie 1, jamais un faux succès", simule([], panne=True)[0], 1)
    cas("dépôt absent : sortie 1", signaler({}, lambda a: "[]"), 1)

    # Le contrôle des workflows, sur des workflows fabriqués.
    pas = (f"      - name: Alerte\n        if: failure()\n        env:\n          GH_TOKEN: x\n"
           f"        run: python3 {SCRIPT} --signaler\n")
    tete = "on: push\npermissions:\n  issues: write\njobs:\n  a:\n    runs-on: u\n    steps:\n      - run: echo\n"
    with tempfile.TemporaryDirectory() as d:
        dossier = Path(d)
        cas("aucun workflow (cas zéro)", [e.split()[0] for e in verifier(dossier)], ["INCONNU"])
        for libelle, texte, attendu in [
            ("workflow conforme", tete + pas, []),
            ("workflow sans alerte", tete, ["ALERTE", "ORDRE"]),
            ("alerte sans if: failure()", tete + pas.replace("        if: failure()\n", ""), ["ALERTE"]),
            ("sans issues: write", (tete + pas).replace("issues: write", "contents: read"), ["DROIT"]),
            ("issues: write suivi d'un commentaire", (tete + pas).replace("issues: write", "issues: write # x"), []),
            ("pas après l'alerte", tete + pas + "      - run: echo fin\n", ["ORDRE"]),
            ("deux jobs, une alerte", tete + pas + "  b:\n    runs-on: u\n    steps:\n      - run: echo\n",
             ["ALERTE", "ORDRE"]),
        ]:
            (dossier / "w.yml").write_text(texte, encoding="utf-8")
            cas(libelle, [e.split()[0] for e in verifier(dossier)], attendu)
    print("selftest : OK" if echecs == 0 else f"selftest : {echecs} ÉCHEC(S)")
    return 0 if echecs == 0 else 1


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--signaler", action="store_true")
    g.add_argument("--verifier", action="store_true")
    g.add_argument("--selftest", action="store_true")
    args = p.parse_args()
    if args.selftest:
        return selftest()
    if args.signaler:
        return signaler(dict(os.environ), gh_reel)
    ecarts = verifier(WORKFLOWS)
    if ecarts:
        print("\n".join(ecarts))
        return 2 if ecarts[0].startswith("INCONNU") else 1
    print("signaler-echec-ci : OK (chaque job finit par l'alerte d'échec)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
