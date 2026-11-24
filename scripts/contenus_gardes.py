#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# contenus_gardes.py — la liste de ce qu'un compte supprimé laisse à la copropriété,
# dite par supprimer-compte.html#t-garde, est-elle celle du code ?
#
# CoproFirst la tient dans CONTENUS_GARDES (api/app/utils/suppression_compte.py) : une
# paire (table, colonne) par contenu dont l'auteur devient « Ancien résident ». La page
# en a oublié cinq pendant des semaines (règles, annonces du hall, questions au
# règlement, rapports de diagnostic, créateur d'une délégation), sans qu'aucun contrôle
# le dise (24/11/2026) : la liste n'était relue qu'à la main.
#
# NOMMES traduit chaque paire en ce que la page en dit. Les deux sens de rupture
# (standards/05 §9 bis) :
#   - le code garde une paire que NOMMES ignore → la page ne la dit pas : écart, CÔTÉ CODE ;
#   - NOMMES nomme une paire que le code ne garde plus (partie dans CONTENUS_PERSONNELS,
#     peut-être) → la page promet ce qui ne l'est plus : écart, CÔTÉ CODE ;
#   - la page ne dit plus la phrase de NOMMES → écart, CÔTÉ PAGE.
# Le dictionnaire introuvable, ou vide, rend INCONNU (standards/04 §1).
#
# Ce qu'il ne couvre pas : la description de chaque paire, ni « Ce qui est effacé »
# (CONTENUS_PERSONNELS, CONSEQUENCES), qui se relisent à la main.
#
# Appelé par verifier-faits-produit.py (sa table, son selftest), qui le lance en CI.
import re

from lecture_distante import Illisible

DEPOT, SOURCE = "coprofirst", "api/app/utils/suppression_compte.py"
PAGE, LIEU = "supprimer-compte.html", "t-garde"

# (table, colonne) du code → ce que #t-garde en dit (texte normalisé, sans balise).
NOMMES = {
    ("ticket", "auteur_id"): "Les affaires",
    ("ticket_evolution", "auteur_id"): "leur suivi",
    ("message_ticket", "auteur_id"): "leurs messages",
    # Les anciens évènements, migrés en affaires (0212 de CoproFirst).
    ("evenement", "auteur_id"): "Les affaires",
    ("evenement_evolution", "auteur_id"): "leur suivi",
    ("document", "publie_par_id"): "les documents publiés",
    ("diagnostic_rapport", "publie_par_id"): "les rapports de diagnostic",
    ("regle_residence", "cree_par_id"): "les règles de la résidence",
    ("annonce_hall", "auteur_id"): "les annonces affichées dans le hall",
    ("sondage", "auteur_id"): "les sondages",
    ("vote_sondage", "user_id"): "les votes",
    ("commentaire_sondage", "auteur_id"): "les réponses dans les échanges",
    ("idee", "auteur_id"): "les idées",
    ("question_reglement", "auteur_id"): "les questions au règlement",
    ("vote_idee", "user_id"): "leurs soutiens",
    ("reponse_communaute", "auteur_id"): "les réponses dans les échanges",
    ("notation_prestataire", "auteur_id"): "l'évaluation des prestataires",
    ("delegation", "cree_par_id"): "la mention de qui l'a créée",
}


def paires(source: str) -> set[tuple[str, str]]:
    """Les clés de CONTENUS_GARDES, sur une ligne ou plusieurs."""
    bloc = re.search(r"^CONTENUS_GARDES\b[^=\n]*= \{\n(.*?)^\}", source, re.M | re.S)
    if not bloc:
        raise Illisible(f"{DEPOT}/{SOURCE} : CONTENUS_GARDES introuvable — la forme du code a changé")
    trouvees = set(re.findall(r'^\s*\(\s*"(\w+)",\s*"(\w+)",?\s*\)', bloc.group(1), re.M))
    if not trouvees:
        raise Illisible(f"{DEPOT}/{SOURCE} : CONTENUS_GARDES sans aucune paire lisible")
    return trouvees


def verifier(lire_source, lire_lieu, nommes=NOMMES) -> tuple[list[str], list[str]]:
    """(inconnus, écarts). lire_source(depot, chemin) et lire_lieu(page, lieu) rendent du
    texte (le lieu normalisé) ou lèvent Illisible."""
    try:
        code = paires(lire_source(DEPOT, SOURCE).replace("\r\n", "\n"))
        texte = lire_lieu(PAGE, LIEU)
    except Illisible as e:
        return [str(e)], []
    ecarts = []
    for table, colonne in sorted(code - nommes.keys()):
        ecarts.append(f"{PAGE}#{LIEU} : le code garde {table}.{colonne} (CONTENUS_GARDES), que la page "
                      "ne nomme pas — côté CODE : le dire sur la page, et dans NOMMES (contenus_gardes.py)")
    for table, colonne in sorted(nommes.keys() - code):
        ecarts.append(f"{PAGE}#{LIEU} : « {nommes[(table, colonne)]} » ({table}.{colonne}) n'est plus dans "
                      "CONTENUS_GARDES — côté CODE : la page promet ce qui n'est plus gardé")
    for cle in sorted(code & nommes.keys()):
        if nommes[cle] not in texte:
            ecarts.append(f"{PAGE}#{LIEU} ne dit plus « {nommes[cle]} » ({cle[0]}.{cle[1]}, gardé par le "
                          "code) — côté PAGE")
    return [], ecarts


def selftest() -> tuple[int, int]:
    """(cas, échecs)."""
    source = ('CONTENUS_GARDES: dict[tuple[str, str], str] = {\n'
              '    ("ticket", "auteur_id"): "une affaire",\n'
              '    (\n        "delegation",\n        "cree_par_id",\n    ): "qui a créé une délégation",\n'
              '}\n\nCONTENUS_PERSONNELS = {\n    ("avis", "auteur_id"): "un avis",\n}\n')
    nommes = {("ticket", "auteur_id"): "Les affaires", ("delegation", "cree_par_id"): "qui l'a créée"}
    texte = "Les affaires restent, comme la mention de qui l'a créée."
    cas = [
        ("conforme (paire sur plusieurs lignes, CONTENUS_PERSONNELS ignoré)", source, texte, nommes, "conforme"),
        ("source en CRLF", source.replace("\n", "\r\n"), texte, nommes, "conforme"),
        ("table neuve gardée par le code", source.replace("}\n\n", '    ("regle", "cree_par_id"): "r",\n}\n\n', 1),
         texte, nommes, "le code garde regle.cree_par_id"),
        ("table qui n'est plus gardée", source.replace('    ("ticket", "auteur_id"): "une affaire",\n', ""),
         texte, nommes, "n'est plus dans CONTENUS_GARDES"),
        ("page qui ne dit plus une phrase", source, texte.replace("Les affaires", "Elles"), nommes,
         "ne dit plus « Les affaires »"),
        ("dictionnaire renommé", source.replace("CONTENUS_GARDES", "GARDES"), texte, nommes, "INCONNU"),
        ("dictionnaire sans paire lisible", 'CONTENUS_GARDES = {\n    "x": 1,\n}\n', texte, nommes, "INCONNU"),
    ]
    echecs = 0
    for nom, src, txt, nm, attendu in cas:
        inconnus, ecarts = verifier(lambda _d, _c, src=src: src, lambda _p, _l, txt=txt: txt, nm)
        obtenu = ("INCONNU" if inconnus else " ".join(ecarts) or "conforme")
        if attendu not in obtenu or (attendu == "conforme") != (obtenu == "conforme"):
            echecs += 1
            print(f"selftest ÉCHEC : contenus gardés, {nom} — attendu « {attendu} », obtenu « {obtenu} »")
    return len(cas), echecs


if __name__ == "__main__":  # python3 scripts/contenus_gardes.py : son selftest seul
    import sys
    n, e = selftest()
    print(f"contenus_gardes --selftest : {n - e}/{n} cas")
    sys.exit(1 if e else 0)
