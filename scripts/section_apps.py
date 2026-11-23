#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# section_apps.py — ce que verifier-app-ios.py et verifier-app-android.py ont en commun :
# ils confrontent LA MÊME section de site/confidentialite.html (#t-application, commune
# aux deux apps depuis coprofirst-site#110) au dépôt de chaque app. Module, pas commande.
#
# Une section commune a un revers, déclaré ici (standards/04 §12) : un mot exigé par un
# contrôle peut être satisfait par le texte de l'autre app (« caméra », « 7 jours »). Les
# mots qui distinguent une app (Face ID, Keystore, Google Play services…) se choisissent
# dans chaque contrôle.
import html
import re
import tempfile
from pathlib import Path

from lecture_distante import Illisible

RACINE = Path(__file__).resolve().parent.parent
PAGE = RACINE / "site" / "confidentialite.html"
ANCRE = "t-application"
OK, ECART, INCONNU = 0, 1, 2
# Ce que le bloc d'une montre dit tant que sa liaison est éteinte.
EN_SERVICE = "pas encore en service"


def nomme(section: str, mot: str) -> bool:
    """Le mot entier figure dans la section (« MIT » n'est pas dans « LIMITE »)."""
    return re.search(rf"(?<!\w){re.escape(mot)}(?!\w)", section) is not None


def section_application(texte: str) -> str:
    """Le texte de la section #t-application, entités résolues, insécables en espaces."""
    bloc = re.search(rf'<section aria-labelledby="{ANCRE}">(.*?)</section>', texte, re.S)
    if not bloc:
        raise Illisible(f"confidentialite.html : section #{ANCRE} introuvable")
    return html.unescape(bloc.group(1)).replace("\xa0", " ")


def bloc(section: str, mot: str) -> str | None:
    """Le bloc de la section qui commence au <h3> nommant `mot` et finit au <h3> suivant ;
    None s'il n'y en a pas. Deux montres, deux blocs : le « pas encore en service » de
    l'une ne vaut pas pour l'autre (coprofirst-site#124)."""
    for morceau in re.split(r"(?=<h3)", section):
        titre = morceau.split("</h3>", 1)[0] if morceau.startswith("<h3") else ""
        if titre and nomme(re.sub(r"<[^>]+>", "", titre), mot):
            return morceau
    return None


def ecarts_de_liaison(section: str, montre: str, active: bool, drapeau: str) -> list[str]:
    """La montre a son bloc (un <h3> qui la nomme) ; liaison éteinte, il dit EN_SERVICE ;
    allumée, il ne le dit plus."""
    texte = bloc(section, montre)
    if texte is None:
        return [f"la section #{ANCRE} n'a pas de bloc (<h3>) qui nomme « {montre} »"]
    if active and nomme(texte, EN_SERVICE):
        return [f"la liaison avec l'{montre} est en service ({drapeau}) : son bloc dit encore « {EN_SERVICE} »"]
    if not active and not nomme(texte, EN_SERVICE):
        return [f"la liaison avec l'{montre} est éteinte ({drapeau}) : son bloc ne dit pas « {EN_SERVICE} »"]
    return []


def ecarts_des_tiers(paquets, admis: dict[str, set[str]], section: str, liste: str,
                     mot=lambda nom: nom, libelle=lambda licence: licence) -> list[str]:
    """paquets : (nom, licences) de ce que l'app embarque hors de son éditeur de système.
    Chaque nom est DÉCLARÉ dans `admis` (la liste `liste` du contrôle), avec ses licences
    exactes, et la section nomme `mot(nom)` et `libelle(licence)` de chacune. Un tiers
    déclaré qui n'est plus embarqué est un écart : une exception qui ne sert plus se retire."""
    ecarts, vus = [], set()
    for nom, lics in paquets:
        if nom not in admis:
            ecarts.append(f"composant embarqué non déclaré : {nom} — le décrire dans #{ANCRE}, "
                          f"puis dans {liste}")
            continue
        vus.add(nom)
        if lics != admis[nom]:
            ecarts.append(f"licences de {nom} : l'app dit {', '.join(sorted(lics))}, {liste} et la page "
                          f"disent {', '.join(sorted(admis[nom]))}")
        ecarts += [f"la section #{ANCRE} ne nomme pas « {m} » ({nom}, embarqué par l'app)"
                   for m in [mot(nom), *sorted(libelle(l) for l in admis[nom])] if not nomme(section, m)]
    ecarts += [f"{nom} n'est plus embarqué par l'app : le retirer de {liste} et de la page"
               for nom in sorted(admis.keys() - vus)]
    return ecarts


def ecarts_des_permissions(cles: set[str], permissions: dict[str, str], section: str) -> list[str]:
    """Les permissions de l'app sont EXACTEMENT les clés de `permissions`, et la section
    nomme le mot de chacune. Ajoutée ou retirée sans la page : écart."""
    ecarts = [f"permission {c} demandée par l'app, absente de PERMISSIONS et de la page"
              for c in sorted(cles - permissions.keys())]
    ecarts += [f"permission {c} retirée de l'app : la retirer de PERMISSIONS et de la page"
               for c in sorted(permissions.keys() - cles)]
    ecarts += [f"la section #{ANCRE} ne nomme pas « {mot} » ({c})"
               for c, mot in permissions.items() if c in cles and not nomme(section, mot)]
    return ecarts


def rejouer(nom: str, cas, verifier) -> int:
    """Le selftest : chaque cas est (libellé, verdict attendu, contenu de chaque source,
    dans l'ordre des arguments de `verifier`). Plus un cas où la première source manque,
    qui doit rendre INCONNU."""
    echecs = 0
    with tempfile.TemporaryDirectory() as dossier:
        for libelle, attendu, *contenus in cas:
            chemins = []
            for i, contenu in enumerate(contenus):
                f = Path(dossier) / f"{i}.txt"
                f.write_text(contenu, encoding="utf-8")
                chemins.append(str(f))
            obtenu, _ = verifier(*chemins)
            if obtenu != attendu:
                echecs += 1
                print(f"selftest ÉCHEC : {libelle} — attendu {attendu}, obtenu {obtenu}")
        obtenu, _ = verifier(str(Path(dossier) / "absent"), *chemins[1:])
        if obtenu != INCONNU:
            echecs += 1
            print(f"selftest ÉCHEC : source illisible — attendu {INCONNU}, obtenu {obtenu}")
    print(f"{nom} --selftest : {len(cas) + 1 - echecs}/{len(cas) + 1} cas")
    return 1 if echecs else 0


def conclure(nom: str, verdict: int, messages: list[str]) -> int:
    for m in messages:
        print(("INCONNU : " if verdict == INCONNU else "ÉCART : ") + m)
    print(f"{nom} : " + {OK: "conforme", ECART: f"{len(messages)} écart(s)", INCONNU: "INCONNU"}[verdict])
    return verdict
