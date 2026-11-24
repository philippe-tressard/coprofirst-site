#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# verifier-faits-produit.py — les chiffres et les libellés d'écran que les pages du
# site recopient du code de CoproFirst et de ses apps sont-ils encore ceux du code ?
#
# Une page statique recopie : « sous 30 jours au plus », « après 60 jours », le
# libellé d'un bouton. Le jour où le code change, la page ment sans que rien ne le
# dise — et ces pages sont celles que citent les magasins (Google Play exige l'adresse
# de supprimer-compte.html, coprofirst-site#104 ; les notifications de
# confidentialite.html, coprofirst-site#108).
#
# FAITS est la table : pour chaque fait, le fichier source (dépôt public, branche
# main, lu sans jeton), le motif qui en extrait la valeur — il doit trouver UNE
# valeur, ni zéro ni deux —, la page, le lieu et la phrase qui doit y figurer, valeur
# comprise. Le lieu est une section (son aria-labelledby), un élément de l'accueil
# (« contenu:<id> », son data-contenu) ou, vide, la page entière (llms.txt, le JSON-LD
# de l'accueil). Une traduction facultative passe de la valeur du code à celle du texte
# (un niveau d'API Android à son numéro de version). La valeur se lit dans le code, elle
# n'est jamais recopiée ici : seule la phrase autour l'est. L'accueil et llms.txt y
# sont depuis le 23/11/2026 (coprofirst-site#126, coprofirst-site#122).
#
# La liste de ce qui est gardé (#t-garde, CONTENUS_GARDES) se compare paire par paire,
# dans les deux sens : contenus_gardes.py, appelé d'ici.
#
# Ce qu'il ne couvre pas (standards/04 §12) : le sens des phrases. Ce qui est effacé
# (CONSEQUENCES, CONTENUS_PERSONNELS de CoproFirst), et ce qui sonne sur un
# téléphone (porte.TYPE_POUSSE, l'alerte d'une actualité ⚡), se relisent à la main
# quand ces sources changent : le commentaire de tête de supprimer-compte.html les
# nomme. Les apps ont leur propre contrôle (verifier-app-ios.py, verifier-app-android.py).
#
# En CI seulement, à chaque poussée et chaque jour (.github/workflows/comptes-demo.yml) :
# la dérive naît dans l'autre dépôt, comme pour verifier-comptes-demo.py.
#
# Verdicts (standards/04 §1) : 0 = conforme, 1 = écart, 2 = INCONNU — source
# injoignable, motif introuvable ou ambigu, section absente. Jamais un vert faute
# d'avoir pu lire. Chaque INCONNU de motif et chaque écart disent en plus quel côté a
# bougé — le code, la page, ou les deux — d'après ce que la page dit encore (une piste,
# avec les lignes de la source : cote_du_motif, cote_de_l_ecart).
#
# Usage : python3 scripts/verifier-faits-produit.py
#         python3 scripts/verifier-faits-produit.py --racine DOSSIER   (sources locales)
#         python3 scripts/verifier-faits-produit.py --selftest
import argparse
import html
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import contenus_gardes
from lecture_distante import Illisible, lire

RACINE = Path(__file__).resolve().parent.parent
BRUT = "https://raw.githubusercontent.com/philippe-tressard/{depot}/main/"
OK, ECART, INCONNU = 0, 1, 2


@dataclass(frozen=True)
class Fait:
    nom: str
    depot: str  # dépôt public de philippe-tressard
    source: str  # chemin dans ce dépôt
    motif: str  # une expression régulière à UN groupe : la valeur
    page: str  # sous site/
    section: str  # aria-labelledby de la <section>, « contenu:<id> », ou « » : la page
    phrase: str  # ce que le lieu doit dire, « {} » étant la valeur
    traduction: tuple = ()  # paires (valeur du code, valeur écrite), facultatives


SERVEUR, IOS, ANDROID = "coprofirst", "coprofirst-ios", "coprofirst-android"
SUPPR, CONFID = "supprimer-compte.html", "confidentialite.html"
FRONT_SUPPR = "front/src/lib/components/SuppressionCompte.svelte"
IOS_SUPPR = "CoproFirst/Fonctions/Profil/SuppressionCompte/SectionSuppressionCompte.swift"
ANDROID_CHAINES = "app/src/main/res/values/strings_profil.xml"
REGLES = "api/app/utils/purge_comptes/regles.py"
ACCUEIL, LLMS = "index.html", "llms.txt"
CONSERVATION = "api/app/utils/conservation_affaires.py"
# Les trois durées de conservation d'une affaire close, dites partout ensemble.
DUREES_AFFAIRES = (("brèves", "BREVES", "{}, 5 ou 10 exercices"),
                   ("pannes et entretien", "ENTRETIEN", "2, {} ou 10 exercices"),
                   ("travaux et sinistres", "TRAVAUX", "2, 5 ou {} exercices"))
LIEUX_CONSERVATION = ((ACCUEIL, "contenu:conservation"), (LLMS, ""), ("supprimer-compte.html", "t-garde"))
# Niveau d'API Android → numéro de version que lit un utilisateur.
API_ANDROID = (("26", "8"), ("27", "8.1"), ("28", "9"), ("29", "10"), ("R", "11"), ("30", "11"),
               ("S", "12"), ("31", "12"), ("TIRAMISU", "13"), ("33", "13"))

FAITS = (
    # Supprimer votre compte (coprofirst-site#104)
    Fait("délai de traitement d'une demande", SERVEUR, "api/app/utils/delais_rgpd.py",
         r"^DELAI_TRAITEMENT_DEMANDE_JOURS = (\d+)$", SUPPR, "t-ensuite", "sous {} jours au plus"),
    Fait("inactivité avant l'avertissement", SERVEUR, REGLES,
         r"^INACTIVITE_ANS = (\d+)$", SUPPR, "t-inactif", "{} ans sans connexion"),
    Fait("délai entre l'avertissement et la suppression", SERVEUR, REGLES,
         r"^DELAI_AVANT_SUPPRESSION_JOURS = (\d+)$", SUPPR, "t-inactif", "{} jours plus tard"),
    # La constante que la purge applique, et dont la politique compose sa phrase depuis
    # coprofirst#3029 (24/11/2026) : la phrase n'écrit plus le nombre.
    Fait("conservation de l'historique des courriels", SERVEUR, "api/app/utils/maintenance.py",
         r"^CONSERVATION_COURRIELS_JOURS = (\d+)$", SUPPR, "t-garde", "gardé {} jours"),
    Fait("site : titre du bloc", SERVEUR, FRONT_SUPPR,
         r'<h3 class="titre-suppression">([^<]+)</h3>', SUPPR, "t-demander", "« {} »"),
    Fait("site : bouton qui ouvre la demande", SERVEUR, FRONT_SUPPR,
         r"\(formulaire = true\)\}>\s*([^<]+?)\s*</button>", SUPPR, "t-demander", "« {} »"),
    Fait("site : bouton qui confirme", SERVEUR, FRONT_SUPPR,
         r'type="submit"[^>]*>\s*([^<]+?)\s*</button>', SUPPR, "t-demander", "« {} »"),
    Fait("site : bouton qui retire la demande", SERVEUR, FRONT_SUPPR,
         r"on:click=\{retirer\}>\s*([^<]+?)\s*</button>", SUPPR, "t-ensuite", "« {} »"),
    # L'en-tête de la rubrique du Profil, que la page nomme (la feuille qu'elle ouvre porte
    # le même titre, en FeuilleDeSaisie depuis coprofirst-ios#382).
    Fait("iOS : titre de la rubrique", IOS, IOS_SUPPR,
         r'\} header: \{\s*Text\("([^"]+)"\)', SUPPR, "t-demander", "« {} »"),
    Fait("iOS : bouton qui ouvre la demande", IOS, IOS_SUPPR,
         r'Label\("([^"]+)", systemImage: "person\.crop\.circle\.badge\.xmark"\)', SUPPR, "t-demander", "« {} »"),
    Fait("Android : titre de la rubrique", ANDROID, ANDROID_CHAINES,
         r'name="profil_supprimer_compte">([^<]+)<', SUPPR, "t-demander", "« {} »"),
    Fait("Android : bouton qui ouvre la demande", ANDROID, ANDROID_CHAINES,
         r'name="profil_demander_suppression">([^<]+)<', SUPPR, "t-demander", "« {} »"),
    # Les notifications sur le téléphone (coprofirst-site#108)
    Fait("texte fixe de la notification", SERVEUR, "api/app/utils/push/envoi.py",
         r'^CORPS = "([^"]+)"$', CONFID, "t-notifications", "« {} »"),
    Fait("abandon de l'identifiant d'un appareil", SERVEUR, "api/app/utils/push/appareils.py",
         r"^ABANDON_JOURS = (\d+)$", CONFID, "t-notifications", "après {} jours"),
    # Les applications (coprofirst-site#110) : la section est commune, une durée d'Android
    # qui s'écarterait de celle de l'iPhone (verifier-app-ios.py) devrait y être dite.
    Fait("Android : durée de la lecture gardée hors ligne", ANDROID,
         "partage-android/src/main/kotlin/fr/coprofirst/app/session/LecturesGardees.kt",
         r"^\s*const val JOURS_MAX = (\d+)L$", CONFID, "t-application", "au bout de {} jours"),
    # Ancré sur le bloc « montre » : la portée « ecran » suit avec la même écriture.
    Fait("jeton de montre : durée", SERVEUR, "api/app/auth/jetons_appareil.py",
         r'"montre": Portee\((?:(?!Portee\()[\s\S])*?duree=timedelta\(days=(\d+)\)', CONFID,
         "t-application", "expire au bout de {} jours"),
    # La vitrine et llms.txt (coprofirst-site#122, coprofirst-site#126)
    Fait("mode limité : plafond de comptes actifs", SERVEUR, "api/app/inscription/regime.py",
         r"^PLAFOND_COMPTES_ACTIFS = (\d+)$", ACCUEIL, "contenu:installation", "{} comptes actifs au plus"),
    Fait("mode limité : plafond (prix)", SERVEUR, "api/app/inscription/regime.py",
         r"^PLAFOND_COMPTES_ACTIFS = (\d+)$", ACCUEIL, "contenu:cout", "à {} comptes actifs"),
    Fait("mode limité : plafond (llms.txt)", SERVEUR, "api/app/inscription/regime.py",
         r"^PLAFOND_COMPTES_ACTIFS = (\d+)$", LLMS, "", "{} comptes actifs au plus"),
    Fait("Docker Compose minimal (question)", SERVEUR, "deploiement/standard/LISEZMOI.md",
         r"Docker Compose \*\*(\d+\.\d+) ou plus récent", ACCUEIL, "contenu:installation",
         "Docker Compose ({} ou plus récent)"),
    Fait("Docker Compose minimal (données structurées)", SERVEUR, "deploiement/standard/LISEZMOI.md",
         r"Docker Compose \*\*(\d+\.\d+) ou plus récent", ACCUEIL, "", "Docker Compose {} ou plus récent"),
    Fait("Docker Compose minimal (llms.txt)", SERVEUR, "deploiement/standard/LISEZMOI.md",
         r"Docker Compose \*\*(\d+\.\d+) ou plus récent", LLMS, "", "Docker Compose {} ou plus récent"),
    *(Fait(f"conservation des affaires : {nom}", SERVEUR, CONSERVATION,
           rf'^{const} = TypeConservation\(\s*"[^"]+",\s*"[^"]+",\s*(\d+),', page, lieu, phrase)
      for nom, const, phrase in DUREES_AFFAIRES for page, lieu in LIEUX_CONSERVATION),
    # Libellés et versions des pages légales
    Fait("auteur d'un compte supprimé", SERVEUR, "api/app/utils/noms.py",
         r'^ANCIEN_RESIDENT = "([^"]+)"$', SUPPR, "t-garde", "« {} »"),
    Fait("iOS : oublier toutes les résidences", IOS, "CoproFirst/Fonctions/Profil/ProfilView.swift",
         r'Button\("([^"]+)"\) \{ geste = \.oublierTout \}', CONFID, "t-application", "« {} »"),
    Fait("Android : oublier toutes les résidences", ANDROID, "app/src/main/res/values/strings.xml",
         r'name="sortie_oublier_bouton">([^<]+)<', CONFID, "t-application", "« {} »"),
    Fait("Android : session gardée sous biométrie", ANDROID,
         "app/src/main/java/fr/coprofirst/app/session/SessionsGardeesKeystore.kt",
         r"^@RequiresApi\(Build\.VERSION_CODES\.(\w+)\)", CONFID, "t-application",
         "Sur Android {} et suivants", API_ANDROID),
    Fait("Android : version minimale", ANDROID, "build.gradle.kts",
         r"^\s*defaultConfig\.minSdk = (\d+)$", CONFID, "t-application", "Sur Android {} à 10", API_ANDROID),
)


def normaliser(texte: str) -> str:
    """Le texte lu comme un lecteur le lit : entités résolues, espaces insécables et
    retours à la ligne ramenés à une espace."""
    return re.sub(r"\s+", " ", html.unescape(texte).replace("\xa0", " "))


def valeur(fait: Fait, source: str) -> str:
    trouvees = re.findall(fait.motif, source, re.M)
    if len(trouvees) != 1:
        raise Illisible(f"{fait.depot}/{fait.source} : {len(trouvees)} valeur(s) pour « {fait.nom} » "
                        "(une attendue)")
    v = normaliser(trouvees[0]).strip()
    if not fait.traduction:
        return v
    table = dict(fait.traduction)
    if v not in table:
        raise Illisible(f"{fait.depot}/{fait.source} : « {v} » sans traduction pour « {fait.nom} »")
    return table[v]


def section(page: str, lieu: str, nom_page: str) -> str:
    """Le texte du lieu : une section (aria-labelledby), un élément « contenu:<id> »
    (data-contenu, jusqu'à la fermeture de sa balise), ou la page entière si vide."""
    if not lieu:
        return normaliser(re.sub(r"<[^>]+>", "", page))
    if lieu.startswith("contenu:"):
        ident = re.escape(lieu.removeprefix("contenu:"))
        bloc = re.search(rf'<(\w+)[^>]*\bdata-contenu="{ident}"[^>]*>(.*?)</\1>', page, re.S)
        texte = bloc.group(2) if bloc else None
    else:
        bloc = re.search(rf'<section aria-labelledby="{re.escape(lieu)}">(.*?)</section>', page, re.S)
        texte = bloc.group(1) if bloc else None
    if texte is None:
        raise Illisible(f"{nom_page} : {lieu} introuvable")
    return normaliser(re.sub(r"<[^>]+>", "", texte))


# Quel côté a bougé ? (coprofirst-site#147, 24/11/2026 : deux motifs muets le même jour,
# la politique réécrite d'un côté, l'écran iOS refait de l'autre, et le message ne
# disait que « la forme du code a changé ».) La page se relit avec sa phrase, la valeur
# laissée libre : ce qu'elle dit encore, et si le code l'écrit encore quelque part. Une
# PISTE, jamais un verdict : 0 ou 2 valeurs restent INCONNU, et une phrase « « {} » »
# attrape tous les libellés cités du lieu.
def valeurs_lues(fait: Fait, texte: str) -> list[str]:
    """Les valeurs que le lieu donne au fait, sans doublon, dans l'ordre de la page."""
    avant, apres = (re.escape(morceau) for morceau in fait.phrase.split("{}"))
    return list(dict.fromkeys(re.findall(avant + r"([^«»]{1,60}?)" + apres, texte)))


def lignes(source: str, lue: str, fait: Fait) -> list[int]:
    """Les lignes de la source qui écrivent la valeur de la page (traduite en retour)."""
    ecritures = [code for code, ecrit in fait.traduction if ecrit == lue] or [lue]
    motifs = [re.compile(rf"(?<!\w){re.escape(e)}(?!\w)") for e in ecritures]
    return [n for n, ligne in enumerate(source.splitlines(), 1)
            if any(m.search(normaliser(ligne)) for m in motifs)]


def cote_du_motif(fait: Fait, source: str, lues: list[str]) -> str:
    """Le motif ne rend pas une valeur : le code a-t-il changé de forme, ou la valeur
    a-t-elle quitté le fichier ?"""
    gabarit = fait.phrase.replace("{}", "…")
    if not lues:
        return f"et la page ne dit plus « {gabarit} » non plus : les deux côtés ont bougé"
    encore = [(lue, n) for lue in lues if (n := lignes(source, lue, fait))][:3]
    if encore:
        dits = " ; ".join(f"« {lue} » ligne(s) {', '.join(map(str, n[:4]))}" for lue, n in encore)
        return (f"piste : la page dit encore « {gabarit} », et la source écrit encore {dits} — "
                "le code a changé de FORME : si c'est bien la valeur, adapter le motif")
    cites = ", ".join(f"« {lue} »" for lue in lues[:3])
    return (f"piste : la page dit encore « {gabarit} » ({cites}), que la source n'écrit plus — "
            "la valeur a quitté ce fichier ou changé : chercher où le code la tient désormais")


def cote_de_l_ecart(fait: Fait, v: str, lues: list[str]) -> str:
    """La valeur se lit des deux côtés mais diffère, ou la page a perdu sa phrase."""
    if not lues:
        return (f"la page ne dit plus « {fait.phrase.replace('{}', '…')} » sous aucune valeur : "
                f"c'est la phrase de la page qui a changé (le code dit « {v} »)")
    cites = ", ".join(f"« {lue} »" for lue in lues[:4]) + (" …" if len(lues) > 4 else "")
    return f"le code dit « {v} », la page {cites} : la valeur a bougé — l'historique des deux dépôts dit où"


def verifier(faits, lire_source, lire_page) -> tuple[int, list[str], list[str]]:
    """(verdict, inconnus, écarts). lire_source(depot, chemin) et lire_page(nom) rendent
    du texte ou lèvent Illisible."""
    ecarts, inconnus = [], []
    for fait in faits:
        try:
            # Une source en CRLF (maintenance.py, 24/11/2026) ferait taire tout motif en « $ ».
            source = lire_source(fait.depot, fait.source).replace("\r\n", "\n")
            texte = section(lire_page(fait.page), fait.section, fait.page)
        except Illisible as e:
            inconnus.append(str(e))
            continue
        lues = valeurs_lues(fait, texte)
        try:
            v = valeur(fait, source)
        except Illisible as e:
            inconnus.append(f"{e} ; {cote_du_motif(fait, source, lues)}")
            continue
        attendu = fait.phrase.format(v)
        if attendu not in texte:
            ecarts.append(f"{fait.page}#{fait.section or 'page'} ne dit pas « {attendu} » ({fait.nom}, "
                          f"lu dans {fait.depot}/{fait.source}) ; {cote_de_l_ecart(fait, v, lues)}")
    verdict = INCONNU if inconnus else ECART if ecarts else OK
    return verdict, inconnus, ecarts


def selftest() -> int:
    exemple = (Fait("délai", "d", "s.py", r"^DELAI = (\d+)$", "p.html", "t-a", "sous {} jours au plus"),
               Fait("bouton", "d", "b.svelte", r"\(ouvrir\)\}>\s*([^<]+?)\s*</button>", "p.html", "t-a", "« {} »"))
    sources = {"s.py": "DELAI = 30\n", "b.svelte": "<button on:click={(ouvrir)}>\n  Demander ceci\n</button>"}
    page = ('<section aria-labelledby="t-a"><p>Traitée sous 30&nbsp;jours\n au plus.</p>'
            '<li>Touchez «&nbsp;Demander <b>ceci</b>&nbsp;».</li></section>')
    cas = [
        ("conforme (insécables, balises et retours à la ligne)", sources, page, OK),
        ("délai changé dans le code", {**sources, "s.py": "DELAI = 45\n"}, page, ECART),
        ("libellé changé dans le code", {**sources, "b.svelte": "{(ouvrir)}>Supprimer</button>"}, page, ECART),
        ("page qui ne dit plus le délai", sources, page.replace("30&nbsp;jours", "un mois"), ECART),
        ("« 130 jours » ne dit pas « 30 jours »", sources, page.replace("sous 30", "sous 130"), ECART),
        ("valeur introuvable", {**sources, "s.py": "DELAI_JOURS = 30\n"}, page, INCONNU),
        ("valeur écrite deux fois", {**sources, "s.py": "DELAI = 30\nDELAI = 30\n"}, page, INCONNU),
        ("section absente", sources, page.replace('"t-a"', '"t-b"'), INCONNU),
        ("source illisible", {"b.svelte": sources["b.svelte"]}, page, INCONNU),
        ("source en CRLF", {**sources, "s.py": "DELAI = 30\r\n"}, page, OK),
    ]
    # Le message dit quel côté a bougé (coprofirst-site#147) : son texte est jugé.
    seul = sources["s.py"]
    diagnostics = [
        ("forme du code changée, valeur encore écrite", "DELAI_JOURS = 30\n", page, "écrit encore « 30 » ligne(s) 1"),
        ("valeur partie du fichier", "AUTRE = 7\n", page, "que la source n'écrit plus"),
        ("forme changée des deux côtés", "DELAI_JOURS = 30\n", page.replace("sous 30&nbsp;jours", "dans le"),
         "les deux côtés ont bougé"),
        ("phrase de la page changée", seul, page.replace("sous 30&nbsp;jours", "dans le"),
         "c'est la phrase de la page qui a changé (le code dit « 30 »)"),
        ("valeur différente", "DELAI = 45\n", page, "le code dit « 45 », la page « 30 »"),
    ]
    # Les autres lieux, et la traduction : un élément data-contenu, la page entière.
    lieux = (Fait("plafond", "d", "r.py", r"^PLAFOND = (\d+)$", "p.html", "contenu:q", "{} comptes actifs"),
             Fait("compose", "d", "r.py", r"^COMPOSE = ([\d.]+)$", "p.html", "", "Compose {} ou plus"),
             Fait("android", "d", "r.py", r"^API = (\w+)$", "p.html", "t-a", "Android {} et suivants",
                  (("R", "11"),)))
    srcs_l = {"r.py": "PLAFOND = 5\nCOMPOSE = 2.24\nAPI = R\n"}
    page_l = ('<script>{"x": "Compose 2.24 ou plus"}</script><article data-contenu="q"><p>5 comptes '
              'actifs</p></article><p>6 comptes actifs</p><section aria-labelledby="t-a">Android 11 '
              'et suivants</section>')
    cas_lieux = [
        ("lieux conformes", srcs_l, page_l, OK),
        ("plafond changé dans le code", {"r.py": srcs_l["r.py"].replace("= 5", "= 6")}, page_l, ECART),
        ("plafond dit hors de l'élément seulement", srcs_l, page_l.replace("<p>5 comptes", "<p>cinq comptes"), ECART),
        ("élément absent", srcs_l, page_l.replace('data-contenu="q"', 'data-contenu="r"'), INCONNU),
        ("niveau d'API sans traduction", {"r.py": srcs_l["r.py"].replace("API = R", "API = S")}, page_l, INCONNU),
        ("Compose changé", {"r.py": srcs_l["r.py"].replace("2.24", "2.30")}, page_l, ECART),
    ]
    def lecteur(srcs):
        def lire_source(_depot, chemin):
            if chemin not in srcs:
                raise Illisible(f"{chemin} : introuvable")
            return srcs[chemin]
        return lire_source

    echecs = 0
    for table, (nom, srcs, pg, attendu) in [(exemple, c) for c in cas] + [(lieux, c) for c in cas_lieux]:
        obtenu, _, _ = verifier(table, lecteur(srcs), lambda _nom, pg=pg: pg)
        if obtenu != attendu:
            echecs += 1
            print(f"selftest ÉCHEC : {nom} — attendu {attendu}, obtenu {obtenu}")
    for nom, src, pg, extrait in diagnostics:
        _, inconnus, ecarts = verifier(exemple[:1], lecteur({"s.py": src}), lambda _nom, pg=pg: pg)
        if extrait not in " ".join(inconnus + ecarts):
            echecs += 1
            print(f"selftest ÉCHEC : {nom} — « {extrait} » absent de {inconnus + ecarts}")
    # La table réelle : chaque motif a un groupe, chaque phrase une place pour la valeur,
    # chaque page et chaque section existent dans le dépôt (sans réseau).
    for fait in FAITS:
        if re.compile(fait.motif).groups != 1 or fait.phrase.count("{}") != 1:
            echecs += 1
            print(f"selftest ÉCHEC : FAITS « {fait.nom} » — un groupe et un « {{}} » exigés")
        try:
            section((RACINE / "site" / fait.page).read_text(encoding="utf-8"), fait.section, fait.page)
        except (OSError, Illisible) as e:
            echecs += 1
            print(f"selftest ÉCHEC : FAITS « {fait.nom} » — {e}")
    # La liste de ce qui est gardé : son propre selftest, et chaque phrase de NOMMES dans
    # la vraie page (sans réseau).
    n_gardes, e_gardes = contenus_gardes.selftest()
    echecs += e_gardes
    garde = section((RACINE / "site" / contenus_gardes.PAGE).read_text(encoding="utf-8"),
                    contenus_gardes.LIEU, contenus_gardes.PAGE)
    for phrase in sorted({p for p in contenus_gardes.NOMMES.values() if p not in garde}):
        echecs += 1
        print(f"selftest ÉCHEC : NOMMES « {phrase} » absent de {contenus_gardes.PAGE}#{contenus_gardes.LIEU}")
    total = len(cas) + len(cas_lieux) + len(diagnostics) + len(FAITS) + n_gardes
    print(f"verifier-faits-produit --selftest : {total - echecs}/{total} cas")
    return 1 if echecs else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--racine", help="dossier local qui contient les dépôts (au lieu de GitHub)")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()

    def lire_source(depot: str, chemin: str) -> str:
        if args.racine:
            return lire(str(Path(args.racine) / depot / chemin))
        return lire(BRUT.format(depot=depot) + chemin)

    def lire_page(nom: str) -> str:
        return lire(str(RACINE / "site" / nom))

    verdict, inconnus, ecarts = verifier(FAITS, lire_source, lire_page)
    inc_gardes, ec_gardes = contenus_gardes.verifier(
        lire_source, lambda page, lieu: section(lire_page(page), lieu, page))
    inconnus, ecarts = inconnus + inc_gardes, ecarts + ec_gardes
    verdict = INCONNU if inconnus else ECART if ecarts else OK
    for m in inconnus:
        print("INCONNU : " + m)
    for m in ecarts:
        print("ÉCART : " + m)
    print("verifier-faits-produit : " + {OK: f"conforme ({len(FAITS)} faits, et la liste de ce qui est gardé)",
                                         ECART: f"{len(ecarts)} écart(s)", INCONNU: "INCONNU"}[verdict])
    return verdict


if __name__ == "__main__":
    sys.exit(main())
