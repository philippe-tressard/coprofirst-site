#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# contenus_compte.py — ce que supprimer-compte.html dit qu'un compte supprimé EFFACE
# (#t-efface) et LAISSE à la copropriété (#t-garde), est-ce ce que fait le code ?
#
# CoproFirst tient les deux listes dans api/app/utils/suppression_compte.py, une paire
# (table, colonne) par contenu : CONTENUS_PERSONNELS (la ligne part avec le compte) et
# CONTENUS_GARDES (l'auteur devient « Ancien résident »). La page en avait oublié cinq
# côté gardé pendant des semaines (24/11/2026, coprofirst-site#149), puis six côté
# effacé — signalements, masques, bail, liens de vérification et de mot de passe,
# la demande elle-même — et disait « vos badges » effacés quand ils restent sur leur
# lot (25/11/2026, coprofirst-site#150) : chaque liste n'était relue qu'à la main.
#
# Pour chaque liste (LISTES), NOMMES traduit chaque paire en ce que la page en dit, et
# ETAPES fonde chaque phrase de la page qui ne vient pas du dictionnaire (une étape
# métier de supprimer_compte) sur un extrait de la source. Les deux sens de rupture
# (standards/05 §9 bis) :
#   - le dictionnaire a une paire que NOMMES ignore → la page ne la dit pas : écart, CÔTÉ CODE ;
#   - NOMMES nomme une paire que le dictionnaire n'a plus (passée dans l'autre liste,
#     peut-être), ou l'extrait d'une ETAPE a disparu → la page promet ce que le code ne
#     fait plus : écart, CÔTÉ CODE ;
#   - la page ne dit plus la phrase de NOMMES ou d'ETAPES → écart, CÔTÉ PAGE.
# Un dictionnaire introuvable, ou vide, rend INCONNU (standards/04 §1).
#
# Ce qu'il ne couvre pas : le sens de chaque phrase, ni CONSEQUENCES
# (api/app/utils/demande_suppression.py), le résumé que l'app et le site de la
# résidence montrent avant la confirmation, qui se relit à la main.
#
# Appelé par verifier-faits-produit.py (sa table, son selftest), qui le lance en CI.
import re
from dataclasses import dataclass, field

from lecture_distante import Illisible

DEPOT, SOURCE = "coprofirst", "api/app/utils/suppression_compte.py"
PAGE = "supprimer-compte.html"


@dataclass(frozen=True)
class Liste:
    dictionnaire: str  # son nom dans SOURCE
    lieu: str  # la section de PAGE qui la dit
    nommes: dict[tuple[str, str], str]  # (table, colonne) → ce que dit la page
    etapes: dict[str, str] = field(default_factory=dict)  # phrase hors dictionnaire → extrait de SOURCE


GARDES = Liste("CONTENUS_GARDES", "t-garde", {
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
})

EFFACES = Liste("CONTENUS_PERSONNELS", "t-efface", {
    ("user_lot", "user_id"): "les liens à vos lots",
    ("refresh_token", "user_id"): "vos sessions",
    ("password_reset_token", "user_id"): "mot de passe oublié",
    ("email_verification_token", "user_id"): "vérification de votre adresse",
    ("notification", "destinataire_id"): "vos notifications",
    ("appareil", "utilisateur_id"): "les téléphones",
    ("jeton_montre", "utilisateur_id"): "montres enregistrés pour vous avertir",
    ("commande_acces", "user_id"): "vos demandes (de badge",
    ("demande_modification_profil", "utilisateur_id"): "de modification de votre profil",
    ("demande_suppression_compte", "utilisateur_id"): "votre demande de suppression elle-même",
    ("delegation", "mandant_id"): "vos délégations, données ou reçues",
    ("delegation", "aidant_id"): "vos délégations, données ou reçues",
    ("mandat", "bailleur_id"): "vos mandats de gestion",
    ("mandat", "mandataire_id"): "vos mandats de gestion",
    ("location_bail", "bailleur_id"): "les baux des lots que vous mettez en location",
    ("petite_annonce", "auteur_id"): "vos petites annonces",
    ("signalement", "signale_par_id"): "vos signalements à la modération",
    ("masquage_auteur", "masque_par_id"): "les auteurs que vous avez masqués",
    ("masquage_auteur", "auteur_id"): "les masques posés sur vous",
    ("avis", "auteur_id"): "vos avis sur l'application",
}, etapes={
    # Le compte lui-même : la dernière ligne que `purger` supprime.
    "votre profil": 'purger(session, "utilisateur", user_id)',
    # Étape 8 : le badge reste sur son lot, seul son lien à la personne part (#1194).
    "le lien entre vous et vos badges, qui restent sur leur lot": "Les badges RESTENT sur leur lot",
    # Étape 0 : la télémétrie (#1629).
    "votre historique de navigation dans l'application": "effacer_telemetrie(session, user_id)",
    # Étape 10 : un bail part avec les objets remis au locataire.
    "la liste des objets remis au locataire": "RemiseObjet.bail_id == bail.id",
})

LISTES = (EFFACES, GARDES)


def paires(source: str, dictionnaire: str) -> set[tuple[str, str]]:
    """Les clés du dictionnaire, sur une ligne ou plusieurs."""
    bloc = re.search(rf"^{dictionnaire}\b[^=\n]*= \{{\n(.*?)^\}}", source, re.M | re.S)
    if not bloc:
        raise Illisible(f"{DEPOT}/{SOURCE} : {dictionnaire} introuvable — la forme du code a changé")
    trouvees = set(re.findall(r'^\s*\(\s*"(\w+)",\s*"(\w+)",?\s*\)', bloc.group(1), re.M))
    if not trouvees:
        raise Illisible(f"{DEPOT}/{SOURCE} : {dictionnaire} sans aucune paire lisible")
    return trouvees


def ecarts_liste(liste: Liste, source: str, texte: str) -> list[str]:
    ou, nom, nommes = f"{PAGE}#{liste.lieu}", liste.dictionnaire, liste.nommes
    code = paires(source, nom)
    ecarts = []
    for table, colonne in sorted(code - nommes.keys()):
        ecarts.append(f"{ou} : {nom} contient {table}.{colonne}, que la page ne nomme pas — côté CODE : "
                      "le dire sur la page, et dans NOMMES (contenus_compte.py)")
    for table, colonne in sorted(nommes.keys() - code):
        ecarts.append(f"{ou} : « {nommes[(table, colonne)]} » ({table}.{colonne}) n'est plus dans {nom} — "
                      "côté CODE : la page promet ce que le code ne fait plus")
    for cle in sorted(code & nommes.keys()):
        if nommes[cle] not in texte:
            ecarts.append(f"{ou} ne dit plus « {nommes[cle]} » ({cle[0]}.{cle[1]}, dans {nom}) — côté PAGE")
    for phrase, extrait in sorted(liste.etapes.items()):
        if extrait not in source:
            ecarts.append(f"{ou} : « {phrase} » repose sur « {extrait} », absent de {SOURCE} — côté CODE : "
                          "relire l'étape, puis la page et ETAPES (contenus_compte.py)")
        if phrase not in texte:
            ecarts.append(f"{ou} ne dit plus « {phrase} » (étape de supprimer_compte) — côté PAGE")
    return ecarts


def verifier(lire_source, lire_lieu, listes=LISTES) -> tuple[list[str], list[str]]:
    """(inconnus, écarts). lire_source(depot, chemin) et lire_lieu(page, lieu) rendent du
    texte (le lieu normalisé) ou lèvent Illisible."""
    try:
        source = lire_source(DEPOT, SOURCE).replace("\r\n", "\n")
    except Illisible as e:
        return [str(e)], []
    inconnus, ecarts = [], []
    for liste in listes:
        try:
            ecarts += ecarts_liste(liste, source, lire_lieu(PAGE, liste.lieu))
        except Illisible as e:
            inconnus.append(str(e))
    return inconnus, ecarts


def selftest() -> tuple[int, int]:
    """(cas, échecs)."""
    source = ('CONTENUS_GARDES: dict[tuple[str, str], str] = {\n'
              '    ("ticket", "auteur_id"): "une affaire",\n'
              '    (\n        "delegation",\n        "cree_par_id",\n    ): "qui a créé une délégation",\n'
              '}\n\nCONTENUS_PERSONNELS = {\n    ("avis", "auteur_id"): "un avis",\n}\n\n'
              '    effacer_telemetrie(session, user_id)\n')
    gardes = Liste("CONTENUS_GARDES", "g", {("ticket", "auteur_id"): "Les affaires",
                                            ("delegation", "cree_par_id"): "qui l'a créée"})
    effaces = Liste("CONTENUS_PERSONNELS", "e", {("avis", "auteur_id"): "vos avis"},
                    {"votre historique": "effacer_telemetrie(session, user_id)"})
    textes = {"g": "Les affaires restent, comme la mention de qui l'a créée.",
              "e": "vos avis ; votre historique."}
    sans_avis = source.replace('    ("avis", "auteur_id"): "un avis",\n', "")
    cas = [
        ("conforme (paire sur plusieurs lignes, deux listes dans la même source)", source, textes, "conforme"),
        ("source en CRLF", source.replace("\n", "\r\n"), textes, "conforme"),
        ("table neuve gardée par le code", source.replace("}\n\n", '    ("regle", "cree_par_id"): "r",\n}\n\n', 1),
         textes, "CONTENUS_GARDES contient regle.cree_par_id"),
        ("table neuve effacée par le code", source.replace('"un avis",\n', '"un avis",\n    ("masque", "x_id"): "m",\n'),
         textes, "CONTENUS_PERSONNELS contient masque.x_id"),
        ("table qui n'est plus gardée", source.replace('    ("ticket", "auteur_id"): "une affaire",\n', ""),
         textes, "n'est plus dans CONTENUS_GARDES"),
        ("page qui ne dit plus une phrase", source, {**textes, "g": textes["g"].replace("Les affaires", "Elles")},
         "ne dit plus « Les affaires »"),
        ("étape disparue du code", source.replace("effacer_telemetrie", "oublier"), textes,
         "« votre historique » repose sur"),
        ("page qui ne dit plus une étape", source, {**textes, "e": "vos avis."}, "ne dit plus « votre historique »"),
        ("dictionnaire renommé", source.replace("CONTENUS_GARDES", "GARDES"), textes, "INCONNU"),
        ("dictionnaire sans paire lisible", sans_avis.replace("CONTENUS_PERSONNELS = {\n}",
                                                              'CONTENUS_PERSONNELS = {\n    "x": 1,\n}'),
         textes, "INCONNU"),
    ]
    echecs = 0
    for nom, src, txt, attendu in cas:
        inconnus, ecarts = verifier(lambda _d, _c, src=src: src, lambda _p, lieu, txt=txt: txt[lieu],
                                    (effaces, gardes))
        obtenu = ("INCONNU" if inconnus else " ".join(ecarts) or "conforme")
        if attendu not in obtenu or (attendu == "conforme") != (obtenu == "conforme"):
            echecs += 1
            print(f"selftest ÉCHEC : contenus du compte, {nom} — attendu « {attendu} », obtenu « {obtenu} »")
    return len(cas), echecs


if __name__ == "__main__":  # python3 scripts/contenus_compte.py : son selftest seul
    import sys
    n, e = selftest()
    print(f"contenus_compte --selftest : {n - e}/{n} cas")
    sys.exit(1 if e else 0)
