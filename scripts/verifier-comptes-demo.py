#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# verifier-comptes-demo.py — les comptes publiés par site/demo.html sont-ils ceux
# de la démonstration ?
#
# La page recopie à la main les identifiants et mots de passe de
# `api/app/demo/personnages.py` de CoproFirst (dépôt public, branche main). Si
# l'application change un compte, la page devient fausse sans que rien d'autre ne
# le signale : ce contrôle compare les deux, compte par compte.
#
# Pourquoi en CI et pas en pre-commit : la source vit dans un AUTRE dépôt, et la
# dérive naît là-bas. Un pre-commit ne la verrait qu'au prochain commit du site, et
# dépendrait du réseau à chaque commit. La CI le lance à chaque poussée ET chaque
# jour (.github/workflows/comptes-demo.yml) : c'est le passage quotidien qui
# attrape un changement fait côté application.
#
# Verdicts (standards/04 §1) : 0 = conforme, 1 = écart, 2 = INCONNU — source
# injoignable ou illisible, page sans compte lisible, forme du fichier source
# changée. Un INCONNU n'est jamais un vert.
#
# Ce qu'il ne couvre pas (standards/04 §12) : ce que la démo EN LIGNE accepte.
# Il compare la page au code de main ; une démo déployée d'une autre version, ou
# dont la base n'a pas été rechargée, peut encore différer.
#
# Usage : python3 scripts/verifier-comptes-demo.py
#         python3 scripts/verifier-comptes-demo.py --source CHEMIN_OU_URL --page CHEMIN
#         python3 scripts/verifier-comptes-demo.py --selftest
import argparse
import ast
import sys
import tempfile
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

URL_SOURCE = (
    "https://raw.githubusercontent.com/philippe-tressard/coprofirst/main/"
    "api/app/demo/personnages.py"
)
RACINE = Path(__file__).resolve().parent.parent
PAGE = RACINE / "site" / "demo.html"
OK, ECART, INCONNU = 0, 1, 2

# Les libellés des <dt> de la page, et ce qu'ils annoncent.
LIBELLES = {"Identifiant": "adresse", "Mot de passe": "mot_de_passe"}

# La règle de formation de l'adresse dans la source. Si elle change, l'adresse
# calculée ici ne serait plus celle de l'application : INCONNU plutôt qu'un faux vert.
ADRESSE_ATTENDUE = ast.dump(ast.parse('f"{self.code}@{DOMAINE}"', mode="eval").body)


class Illisible(Exception):
    """Une entrée ne se lit pas : le verdict est INCONNU, jamais OK."""


# ── La source : api/app/demo/personnages.py ─────────────────────────────────────


def _nom(noeud: ast.AST) -> str | None:
    if isinstance(noeud, ast.Name):
        return noeud.id
    if isinstance(noeud, ast.Attribute):
        return noeud.attr
    return None


def _chaine(appel: ast.Call, rang: int, mot_cle: str) -> str:
    """L'argument littéral d'un appel `Personnage(...)`, positionnel ou nommé."""
    valeur = next((k.value for k in appel.keywords if k.arg == mot_cle), None)
    if valeur is None and len(appel.args) > rang:
        valeur = appel.args[rang]
    if not (isinstance(valeur, ast.Constant) and isinstance(valeur.value, str)):
        raise Illisible(
            f"source : `{mot_cle}` n'est pas une chaîne littérale "
            f"(ligne {appel.lineno}) — le contrôle ne sait pas l'évaluer"
        )
    return valeur.value


def comptes_source(texte: str) -> dict[str, str]:
    """Fonction PURE : {adresse: mot de passe} des personnages déclarés."""
    try:
        arbre = ast.parse(texte)
    except SyntaxError as e:
        raise Illisible(f"source : Python illisible ({e.msg}, ligne {e.lineno})")
    domaine = None
    for n in arbre.body:
        cibles = n.targets if isinstance(n, ast.Assign) else [n.target] if isinstance(n, ast.AnnAssign) else []
        if any(_nom(c) == "DOMAINE" for c in cibles):
            if isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
                domaine = n.value.value
    if not domaine:
        raise Illisible("source : constante DOMAINE introuvable")
    formations = [
        f for c in ast.walk(arbre) if isinstance(c, ast.ClassDef) and c.name == "Personnage"
        for f in c.body if isinstance(f, ast.FunctionDef) and f.name == "adresse"
    ]
    retours = [r.value for f in formations for r in ast.walk(f) if isinstance(r, ast.Return)]
    if len(retours) != 1 or ast.dump(retours[0]) != ADRESSE_ATTENDUE:
        raise Illisible("source : Personnage.adresse ne se forme plus en code@DOMAINE")
    comptes: dict[str, str] = {}
    for n in ast.walk(arbre):
        if isinstance(n, ast.Call) and _nom(n.func) == "Personnage":
            adresse = f"{_chaine(n, 0, 'code')}@{domaine}"
            if adresse in comptes:
                raise Illisible(f"source : {adresse} déclaré deux fois")
            comptes[adresse] = _chaine(n, 1, "mot_de_passe")
    # Cas zéro (standards/04 §2) : aucun personnage ne prouve rien
    if not comptes:
        raise Illisible("source : aucun appel Personnage(...) — rien à comparer")
    return comptes


# ── La page : les <code> des listes .identifiants de site/demo.html ─────────────


class _Lecteur(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocs: list[dict[str, str]] = []
        self._bloc: dict[str, str] | None = None
        self._libelle: str | None = None
        self._texte: list[str] | None = None

    def handle_starttag(self, balise, attributs):
        if balise == "dl" and "identifiants" in (dict(attributs).get("class") or "").split():
            self._bloc, self._libelle = {}, None
        elif self._bloc is not None and balise in ("dt", "code"):
            self._texte = []

    def handle_data(self, donnees):
        if self._texte is not None:
            self._texte.append(donnees)

    def handle_endtag(self, balise):
        if self._bloc is None:
            return
        if balise in ("dt", "code") and self._texte is not None:
            texte, self._texte = "".join(self._texte).strip(), None
            if balise == "dt":
                if texte not in LIBELLES:
                    raise Illisible(f"page : libellé inattendu « {texte} » (ligne {self.getpos()[0]})")
                self._libelle = texte
            else:
                cle = LIBELLES.get(self._libelle or "")
                if cle is None or cle in self._bloc:
                    raise Illisible(f"page : <code> sans libellé propre (ligne {self.getpos()[0]})")
                self._bloc[cle] = texte
        elif balise == "dl":
            self.blocs.append(self._bloc)
            self._bloc = None


def comptes_page(texte: str) -> dict[str, str]:
    """Fonction PURE : {adresse: mot de passe} des comptes publiés par la page."""
    lecteur = _Lecteur()
    lecteur.feed(texte)
    lecteur.close()
    comptes: dict[str, str] = {}
    for bloc in lecteur.blocs:
        if set(bloc) != set(LIBELLES.values()) or not all(bloc.values()):
            raise Illisible(f"page : liste .identifiants incomplète ({bloc})")
        if bloc["adresse"] in comptes:
            raise Illisible(f"page : {bloc['adresse']} publié deux fois")
        comptes[bloc["adresse"]] = bloc["mot_de_passe"]
    # Cas zéro : une page dont la structure a changé ne publie « aucun écart »
    if not comptes:
        raise Illisible("page : aucune liste .identifiants lisible")
    return comptes


# ── La décision ─────────────────────────────────────────────────────────────────


def comparer(source: dict[str, str], page: dict[str, str]) -> list[str]:
    """Fonction PURE : un écart par ligne ; liste vide = la page dit vrai."""
    ecarts = []
    for adresse in sorted(source.keys() | page.keys()):
        if adresse not in page:
            ecarts.append(f"MANQUE   {adresse} (compte de l'application absent de la page)")
        elif adresse not in source:
            ecarts.append(f"EN TROP  {adresse} (publié, mais absent de l'application)")
        elif page[adresse] != source[adresse]:
            ecarts.append(
                f"MDP      {adresse} : la page publie « {page[adresse]} », "
                f"l'application attend « {source[adresse]} »"
            )
    return ecarts


# ── Les entrées ─────────────────────────────────────────────────────────────────


def lire(origine: str) -> str:
    """Le texte d'un fichier local ou d'une URL https, sans jeton. Illisible sinon."""
    try:
        if origine.startswith("https://"):
            requete = urllib.request.Request(origine, headers={"User-Agent": "coprofirst-site-ci"})
            with urllib.request.urlopen(requete, timeout=30) as reponse:
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


# ── Autotest ────────────────────────────────────────────────────────────────────


def _source_type(comptes: dict[str, str], domaine: str = "demo.coprofirst.fr") -> str:
    """Une source de la FORME de personnages.py (arguments positionnels, propriété
    adresse), pour des comptes donnés — standards/04 §22 : la fixture décrit le réel."""
    personnages = "".join(
        f'        Personnage(\n            "{code}",\n            "{mdp}",\n'
        f'            prenom="Sophie",\n            nom="Delmas",\n        ),\n'
        for code, mdp in ((a.split("@")[0], m) for a, m in comptes.items())
    )
    return (
        f'DOMAINE = "{domaine}"\n\n@dataclass(frozen=True)\nclass Personnage:\n'
        "    code: str\n    mot_de_passe: str\n\n    @property\n"
        '    def adresse(self) -> str:\n        return f"{self.code}@{DOMAINE}"\n\n'
        "PERSONNAGES: dict[str, Personnage] = {\n    p.code: p\n    for p in (\n"
        f"{personnages}    )\n}}\n"
    )


def _page_type(comptes: dict[str, str]) -> str:
    """Une page de la forme de demo.html : un <dl class="identifiants"> par compte."""
    return "".join(
        f'<dl class="identifiants">\n<div><dt>Identifiant</dt><dd><code>{a}</code>'
        f'<button class="copier"><span>Copier</span></button></dd></div>\n'
        f"<div><dt>Mot de passe</dt><dd><code>{m}</code></dd></div>\n</dl>\n"
        for a, m in comptes.items()
    )


def _verdict(source: str, page: str) -> str:
    """Les étiquettes du verdict, comme le contrôle les produirait."""
    try:
        ecarts = comparer(comptes_source(source), comptes_page(page))
    except Illisible:
        return "INCONNU"
    return " ".join(e.split("  ")[0].strip() for e in ecarts)


def selftest() -> int:
    A = {"user-cs@demo.coprofirst.fr": "PSWD-a1", "user-loc@demo.coprofirst.fr": "PSWD-b1"}
    sans_loc = {k: v for k, v in A.items() if "loc" not in k}
    avec_intrus = {**A, "user-x@demo.coprofirst.fr": "PSWD-x1"}
    autre_mdp = {**A, "user-cs@demo.coprofirst.fr": "PSWD-a2"}
    source = _source_type(A)
    cas = [
        ("conforme", source, _page_type(A), ""),
        ("compte manquant", source, _page_type(sans_loc), "MANQUE"),
        ("mot de passe divergent", source, _page_type(autre_mdp), "MDP"),
        ("compte en trop", source, _page_type(avec_intrus), "EN TROP"),
        ("arguments nommés", source.replace('"user-cs",', 'code="user-cs",')
         .replace('"PSWD-a1",', 'mot_de_passe="PSWD-a1",'), _page_type(A), ""),
        ("autre domaine", _source_type(A, "demo.exemple.fr"), _page_type(A), "EN TROP MANQUE EN TROP MANQUE"),
        ("source sans personnage (cas zéro)", _source_type({}), _page_type(A), "INCONNU"),
        ("source sans DOMAINE", source.replace("DOMAINE = ", "AUTRE = "), _page_type(A), "INCONNU"),
        ("adresse formée autrement", source.replace("{self.code}@", "{self.code}.x@"), _page_type(A), "INCONNU"),
        ("mot de passe calculé", source.replace('"PSWD-a1"', 'secret()'), _page_type(A), "INCONNU"),
        ("source illisible", source + "\n)(", _page_type(A), "INCONNU"),
        ("page sans liste (cas zéro)", source, "<p>Bientôt.</p>", "INCONNU"),
        ("page sans mot de passe", source, _page_type(A).replace("<dt>Mot de passe</dt>", ""), "INCONNU"),
        ("page, libellé changé", source, _page_type(A).replace("Mot de passe", "Code"), "INCONNU"),
    ]
    # La page RÉELLE (standards/04 §13, §22) : sa structure se lit, et une altération
    # s'y voit. La source est fabriquée à partir de la page même, pour ne pas
    # recopier les comptes une troisième fois.
    reelle = PAGE.read_text(encoding="utf-8")
    publies = comptes_page(reelle)
    adresse, mdp = next(iter(publies.items()))
    source_reelle = _source_type(publies)
    cas += [
        (f"demo.html réelle ({len(publies)} comptes)", source_reelle, reelle, ""),
        ("demo.html, mot de passe altéré", source_reelle,
         reelle.replace(f"<code>{mdp}</code>", f"<code>{mdp}0</code>", 1), "MDP"),
        ("demo.html, compte retiré", source_reelle,
         reelle.replace(f"<code>{adresse}</code>", "<code>autre@demo.coprofirst.fr</code>", 1), "EN TROP MANQUE"),
    ]
    echecs = 0
    for nom, src, page, attendu in cas:
        obtenu = _verdict(src, page)
        echecs += obtenu != attendu
        print(f"  {'ok   ' if obtenu == attendu else 'ÉCHEC'}   {nom} : «{obtenu}»"
              + ("" if obtenu == attendu else f", attendu «{attendu}»"))
    # Les entrées : un fichier absent ou mal encodé est INCONNU, jamais vide
    with tempfile.TemporaryDirectory() as t:
        latin = Path(t, "latin1.py")
        latin.write_bytes("DOMAINE = 'é'".encode("latin-1"))
        for nom, chemin in (("fichier absent", str(Path(t, "absent.py"))), ("fichier non UTF-8", str(latin))):
            try:
                lire(chemin)
                echecs += 1
                print(f"  ÉCHEC   {nom} : lu sans erreur, attendu INCONNU")
            except Illisible:
                print(f"  ok      {nom} : «INCONNU»")
    print("selftest : OK" if echecs == 0 else f"selftest : {echecs} ÉCHEC(S)")
    return OK if echecs == 0 else ECART


def main() -> int:
    for flux in (sys.stdout, sys.stderr):
        flux.reconfigure(encoding="utf-8")  # Windows : la console n'est pas en UTF-8
    parseur = argparse.ArgumentParser(description="Les comptes de demo.html sont-ils ceux de la démo ?")
    parseur.add_argument("--selftest", action="store_true")
    parseur.add_argument("--source", default=URL_SOURCE, help="fichier ou URL https de personnages.py")
    parseur.add_argument("--page", default=str(PAGE), help="la page publiée (site/demo.html)")
    options = parseur.parse_args()
    if options.selftest:
        return selftest()
    try:
        source = comptes_source(lire(options.source))
        page = comptes_page(lire(options.page))
    except Illisible as e:
        print(f"INCONNU : {e} — rien n'a été comparé")
        return INCONNU
    ecarts = comparer(source, page)
    if ecarts:
        print("\n".join(ecarts))
        print(f"verifier-comptes-demo : {len(ecarts)} écart(s) — corriger site/demo.html "
              f"d'après {options.source}")
        return ECART
    print(f"verifier-comptes-demo : OK ({len(page)} comptes, source : {options.source})")
    return OK


if __name__ == "__main__":
    sys.exit(main())
