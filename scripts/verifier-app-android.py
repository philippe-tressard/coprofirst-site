#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# verifier-app-android.py — ce que site/confidentialite.html dit de l'application
# Android (section #t-application, commune avec l'iPhone, coprofirst-site#110) est-il
# encore vrai ?
#
# La page est la politique de confidentialité que cite la fiche Google Play, et la
# section « Sécurité des données » de coprofirst-android (docs/play-store/
# securite-des-donnees.md) exige qu'elle dise la même chose que l'app (standards/14
# §3 bis). Ces affirmations se lisent dans le dépôt de l'app (philippe-tressard/
# coprofirst-android, public, branche main) :
#
#   1. les permissions : les <uses-permission> des manifestes du téléphone ET de la
#      montre sont EXACTEMENT les clés de PERMISSIONS, et la section nomme chacune ;
#   2. le manifeste : chaque <application> refuse la sauvegarde et le trafic en clair
#      (MANIFESTE), ce que la section affirme ;
#   3. les composants tiers embarqués (app/src/main/tiers/composants.json, confronté au
#      build par l'app elle-même) : chacun est déclaré dans TIERS_ADMIS avec ses
#      licences exactes, et la section nomme l'un et les autres. Un composant neuf est un
#      écart tant qu'un humain n'a pas relu à quoi il se connecte ; un composant retiré
#      aussi ;
#   4. la liaison téléphone ↔ montre : tant que `LiaisonMontre.ACTIF` est éteint, le
#      bloc « Wear OS » de la section (son <h3>) dit « pas encore en service » ; allumé,
#      il ne le dit plus. Le bloc de l'Apple Watch ne compte pas (coprofirst-site#124). Le drapeau
#      attend lui-même que cette page décrive la montre (sa condition 3).
#
# Les durées (lecture gardée hors ligne, jeton de montre) se lisent par
# verifier-faits-produit.py, qui tient les chiffres recopiés du produit.
#
# Ce qu'il ne couvre pas (standards/04 §12) : ce que les bibliothèques ajoutent au
# manifeste FUSIONNÉ (Firebase Messaging : c2dm RECEIVE et WAKE_LOCK, relevés par
# l'app le 19/11/2026, que la page nomme à la main) — il ne se voit qu'au build de la
# release ; le sens des phrases (ce qui est gardé, effacé, partagé avec Google), qui se
# relit dans le code et dans securite-des-donnees.md quand ils changent ; ce que dit
# l'app iPhone (verifier-app-ios.py). Les mots exigés sont propres à Android quand la
# section commune le permet (section_apps.py le déclare).
#
# En CI seulement, à chaque poussée et chaque jour (.github/workflows/comptes-demo.yml) :
# la dérive naît dans l'autre dépôt.
#
# Verdicts (standards/04 §1) : 0 = conforme, 1 = écart, 2 = INCONNU — source
# injoignable, manifeste ou liste illisible (forme changée). Jamais un vert faute
# d'avoir pu lire.
#
# Usage : python3 scripts/verifier-app-android.py
#         python3 scripts/verifier-app-android.py --telephone X --montre Y --composants Z --liaison W --page P
#         python3 scripts/verifier-app-android.py --selftest
import argparse
import json
import re
import sys

from lecture_distante import Illisible, lire
from section_apps import (ECART, INCONNU, OK, PAGE, conclure, ecarts_de_liaison, ecarts_des_permissions,
                          ecarts_des_tiers, nomme, rejouer, section_application)

DEPOT = "https://raw.githubusercontent.com/philippe-tressard/coprofirst-android/main/"

# Chaque permission des deux manifestes, et le mot qui la nomme dans la section.
PERMISSIONS = {
    "android.permission.INTERNET": "Internet",  # la résidence, en HTTPS seulement
    "android.permission.CAMERA": "caméra",  # QR code de la fiche d'arrivée (coprofirst-android#6)
    "android.permission.USE_BIOMETRIC": "biométrie",  # rouvrir la session gardée (coprofirst-android#13)
    "android.permission.ACCESS_NETWORK_STATE": "état du réseau",  # consultation hors ligne (coprofirst-android#28)
    "android.permission.POST_NOTIFICATIONS": "afficher des notifications",  # l'alerte urgente (coprofirst-android#280)
}

# Ce que chaque <application> déclare, et le mot de la section qui l'affirme.
MANIFESTE = {
    "android:allowBackup": ("false", "sauvegarde"),
    "android:usesCleartextTraffic": ("false", "HTTPS"),
}

# Chaque composant tiers embarqué (`nom` de composants.json) et ses licences. La section
# nomme le composant (son nom, sans la parenthèse) et chaque licence (LIBELLES).
TIERS_ADMIS = {
    # Bibliothèques libres, sans connexion propre : l'app ne parle qu'à la résidence et à
    # coprofirst.fr (dispense nommée de verifier-depot.sh de l'app). Relu le 22/11/2026.
    "Android Jetpack (AndroidX, Compose)": {"Apache-2.0"},
    "Kotlin": {"Apache-2.0"},
    "kotlinx.coroutines": {"Apache-2.0"},
    "kotlinx.serialization": {"Apache-2.0"},
    "OkHttp": {"Apache-2.0", "MPL-2.0"},  # le transport vers la résidence ; MPL : Public Suffix List
    "Okio": {"Apache-2.0"},
    "Guava ListenableFuture": {"Apache-2.0"},
    "JSpecify": {"Apache-2.0"},
    "ZXing": {"Apache-2.0"},  # le QR code, lu sur l'appareil
    "AutoValue (annotations)": {"Apache-2.0"},
    "javax.inject (JSR-330)": {"Apache-2.0"},
    "Error Prone (annotations)": {"Apache-2.0"},
    # Des dessins, ni code ni connexion (contrat/icones-svg.json).
    "Lucide": {"ISC", "MIT"},
    "Simple Icons (logo WhatsApp)": {"CC0-1.0"},
    # Les deux seules qui parlent à Google : point 4 de la licence de l'app
    # (verifier_dependances_google.py de l'app) — notifications et montre.
    "Google Play services (Wearable, Cloud Messaging)": {"LicenseRef-Android-SDK"},
    "Firebase Cloud Messaging": {"Apache-2.0"},
}
LIBELLES = {"LicenseRef-Android-SDK": "SDK Android"}


def mot(nom: str) -> str:
    """« Google Play services (Wearable, Cloud Messaging) » → « Google Play services »."""
    return nom.split(" (", 1)[0]


def application(texte: str, nom: str) -> tuple[set[str], dict[str, str]]:
    """Un manifeste : ses permissions, et les attributs de son <application>."""
    if "<manifest" not in texte:
        raise Illisible(f"{nom} : pas un manifeste Android (forme changée ?)")
    balise = re.search(r"<application\b([^>]*)>", texte, re.S)
    if not balise:
        raise Illisible(f"{nom} : balise <application> introuvable")
    cles = set(re.findall(r'<uses-permission(?:-sdk-23)?\s+android:name="([^"]+)"', texte))
    return cles, dict(re.findall(r'(android:\w+)="([^"]*)"', balise.group(1)))


def composants(texte: str) -> list[tuple[str, set[str]]]:
    try:
        liste = json.loads(texte)["composants"]
        rendus = [(c["nom"], set(c["licences"])) for c in liste]
    except (ValueError, KeyError, TypeError) as e:
        raise Illisible(f"composants.json illisible (forme changée ?) : {e!r}")
    if not rendus:
        raise Illisible("composants.json : aucun composant")
    return rendus


def liaison_active(texte: str) -> bool:
    trouve = re.findall(r"^\s*const val ACTIF: Boolean = (true|false)\s*$", texte, re.M)
    if len(trouve) != 1:
        raise Illisible("LiaisonMontre.kt : `const val ACTIF: Boolean = …` introuvable ou en double")
    return trouve[0] == "true"


def verifier(app: str, montre: str, liste: str, liaison: str, page: str) -> tuple[int, list[str]]:
    try:
        manifestes = {"le manifeste du téléphone": application(lire(app), "app/AndroidManifest.xml"),
                      "le manifeste de la montre": application(lire(montre), "montre/AndroidManifest.xml")}
        tiers = composants(lire(liste))
        active = liaison_active(lire(liaison))
        section = section_application(lire(page))
    except Illisible as e:
        return INCONNU, [str(e)]
    cles = set().union(*(c for c, _ in manifestes.values()))
    ecarts = ecarts_des_permissions(cles, PERMISSIONS, section)
    for qui, (_, attributs) in manifestes.items():
        ecarts += [f"{qui} ne déclare pas {a}=\"{v}\" : la section l'affirme (« {m} »)"
                   for a, (v, m) in MANIFESTE.items() if attributs.get(a) != v]
    ecarts += [f"la section #t-application ne nomme pas « {m} » ({a})"
               for a, (_, m) in MANIFESTE.items() if not nomme(section, m)]
    ecarts += ecarts_des_tiers(tiers, TIERS_ADMIS, section, "TIERS_ADMIS (verifier-app-android.py)",
                               mot=mot, libelle=lambda l: LIBELLES.get(l, l))
    ecarts += ecarts_de_liaison(section, "Wear OS", active, "LiaisonMontre.ACTIF")
    return (ECART if ecarts else OK), ecarts


def selftest() -> int:
    tel = ('<manifest>\n<uses-permission android:name="android.permission.INTERNET" />\n'
           '<uses-permission android:name="android.permission.CAMERA" />\n'
           '<application\n android:allowBackup="false"\n android:usesCleartextTraffic="false">\n</application></manifest>')
    montre = tel.replace('<uses-permission android:name="android.permission.CAMERA" />\n', "")
    tiers = json.dumps({"composants": [{"nom": "OkHttp", "licences": ["Apache-2.0", "MPL-2.0"]},
                                       {"nom": "Google Play services (Wearable, Cloud Messaging)",
                                        "licences": ["LicenseRef-Android-SDK"]}]})
    eteinte = "object LiaisonMontre {\n    const val ACTIF: Boolean = false\n}\n"
    page = ('<section aria-labelledby="t-application"><p>Internet, la caméra, en HTTPS, hors de toute sauvegarde.</p>'
            '<p>OkHttp (Apache-2.0, MPL-2.0), Google Play services (licence du SDK Android).</p>'
            '<h3>La montre Wear&nbsp;OS</h3><p>Le lien&nbsp;: pas encore en service.</p>'
            '<h3>L\'Apple Watch</h3><p>Ailleurs.</p></section>')
    global PERMISSIONS, TIERS_ADMIS
    reelles = PERMISSIONS, TIERS_ADMIS
    PERMISSIONS = {"android.permission.INTERNET": "Internet", "android.permission.CAMERA": "caméra"}
    TIERS_ADMIS = {"OkHttp": {"Apache-2.0", "MPL-2.0"},
                   "Google Play services (Wearable, Cloud Messaging)": {"LicenseRef-Android-SDK"}}
    localisation = '<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />\n'
    zxing = tiers.replace('[{', '[{"nom": "ZXing", "licences": ["Apache-2.0"]}, {')
    cas = [
        ("conforme", OK, tel, montre, tiers, eteinte, page),
        ("permission ajoutée au téléphone", ECART, tel.replace("<application", localisation + "<application"),
         montre, tiers, eteinte, page),
        ("permission ajoutée à la montre seule", ECART, tel, montre.replace("<application", localisation + "<application"),
         tiers, eteinte, page),
        ("permission retirée des deux manifestes", ECART, tel.replace("android.permission.CAMERA", "x"),
         montre, tiers, eteinte, page),
        ("page qui ne nomme plus la caméra", ECART, tel, montre, tiers, eteinte, page.replace("la caméra", "le QR")),
        ("sauvegarde permise par la montre", ECART, tel, montre.replace('allowBackup="false"', 'allowBackup="true"'),
         tiers, eteinte, page),
        ("sauvegarde non déclarée (vraie par défaut)", ECART, tel.replace(' android:allowBackup="false"\n', ""),
         montre, tiers, eteinte, page),
        ("trafic en clair permis", ECART, tel.replace('Traffic="false"', 'Traffic="true"'), montre, tiers, eteinte, page),
        ("composant neuf non déclaré", ECART, tel, montre, zxing, eteinte, page),
        ("composant déclaré qui n'est plus embarqué", ECART, tel, montre,
         json.dumps({"composants": [{"nom": "OkHttp", "licences": ["Apache-2.0", "MPL-2.0"]}]}), eteinte, page),
        ("licence changée dans l'app", ECART, tel, montre, tiers.replace('"MPL-2.0"', '"GPL-3.0"'), eteinte, page),
        ("page qui ne nomme plus un composant", ECART, tel, montre, tiers, eteinte,
         page.replace("Google Play services", "une bibliothèque de Google")),
        ("page qui ne nomme plus une licence (libellé)", ECART, tel, montre, tiers, eteinte,
         page.replace("SDK Android", "Google")),
        ("liaison allumée, page qui dit « pas encore »", ECART, tel, montre, tiers,
         eteinte.replace("false", "true"), page),
        ("liaison éteinte, page qui ne le dit pas", ECART, tel, montre, tiers, eteinte,
         page.replace("pas encore en service", "en service")),
        ("« pas encore » dit pour l'Apple Watch seulement", ECART, tel, montre, tiers, eteinte,
         page.replace("pas encore en service", "relié").replace("Ailleurs", "Lien : pas encore en service")),
        ("page sans bloc Wear OS", ECART, tel, montre, tiers, eteinte, page.replace("Wear&nbsp;OS", "connectée")),
        ("liaison allumée et page à jour", OK, tel, montre, tiers, eteinte.replace("false", "true"),
         page.replace("pas encore en service", "en service")),
        ("pas un manifeste", INCONNU, "<?xml?>", montre, tiers, eteinte, page),
        ("manifeste sans <application>", INCONNU, tel, "<manifest></manifest>", tiers, eteinte, page),
        ("composants.json d'une autre forme", INCONNU, tel, montre, '{"tiers": []}', eteinte, page),
        ("composants.json vide", INCONNU, tel, montre, '{"composants": []}', eteinte, page),
        ("drapeau de la montre introuvable", INCONNU, tel, montre, tiers, "object LiaisonMontre {}", page),
        ("page sans la section", INCONNU, tel, montre, tiers, eteinte, '<section aria-labelledby="t-droits"></section>'),
    ]
    try:
        retour = rejouer("verifier-app-android", cas, verifier)
    finally:
        PERMISSIONS, TIERS_ADMIS = reelles
    # Les tables réelles : chaque permission et chaque composant a son mot, non vide.
    if any(not m for m in PERMISSIONS.values()) or any(not mot(n) for n in TIERS_ADMIS):
        print("selftest ÉCHEC : PERMISSIONS ou TIERS_ADMIS a un mot vide")
        retour = 1
    return retour


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--telephone", default=DEPOT + "app/src/main/AndroidManifest.xml")
    parser.add_argument("--montre", default=DEPOT + "montre/src/main/AndroidManifest.xml")
    parser.add_argument("--composants", default=DEPOT + "app/src/main/tiers/composants.json")
    parser.add_argument("--liaison", default=DEPOT + "partage/src/main/kotlin/fr/coprofirst/app/fonctions/"
                                                    "notifications/montre/LiaisonMontre.kt")
    parser.add_argument("--page", default=str(PAGE))
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    return conclure("verifier-app-android",
                    *verifier(args.telephone, args.montre, args.composants, args.liaison, args.page))


if __name__ == "__main__":
    sys.exit(main())
