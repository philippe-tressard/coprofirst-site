#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
"""contenu-accueil.py — site/contenu.json est extrait de site/index.html, et de lui seul.

L'application iOS présente CoproFirst avec le contenu de l'accueil, en écrans natifs
(coprofirst-site#42). Recopier les textes dans l'app les ferait diverger à la
première retouche du site : la source est index.html, contenu.json en est la
projection, écrite dans le dépôt par --ecrire et refusée par le contrôle dès
qu'elle diffère de ce que la page donne aujourd'hui.

Ce qui part dans le fichier, la page le DÉCLARE : un élément porte
`data-contenu="<id>"`. Cet identifiant est le contrat avec l'app (elle y accroche
ses icônes et son ordre) : il ne change pas quand un titre est retouché, et le
retirer casse les apps déjà installées.
  - une <section data-contenu> devient une section ;
  - un élément data-contenu dans une section devient un de ses éléments ;
  - une <img data-contenu> devient une image de la section ou de l'élément ;
  - le <footer> de la page devient la section « pied » (liens légaux, source) ;
  - `data-contenu-hors` écarte un bloc (le mot du créateur : hors de la page, il
    passerait pour un avis d'utilisateur) ; ce qui porte aria-hidden="true" est
    décoratif et ne part jamais.
Dans une section ou un élément : `titre` (premier h1/h2/h3, à défaut le premier
<b> d'un élément), `surtitre` (.surtitre), `textes` (chaque <p> et <small>
qui n'est pas fait de liens seulement),
`points` (chaque <li> qui ne contient pas d'élément), `liens` ({texte, adresse}),
`images` ({id, image, largeur, hauteur, description}). Un élément qui est un lien
porte son `adresse` ; un onglet qui le nomme (aria-labelledby), son `etiquette`.
Les adresses sont absolues ; les images, des chemins relatifs à contenu.json, qui
doivent exister dans site/. Un champ vide est omis. `format` change si un champ
change de sens ou disparaît ; un champ ajouté le laisse.

Ce dont l'app iOS dépend est FIGÉ dans CONTRAT_APP (coprofirst-site#66) : les `id`
des éléments qu'elle accroche à ses symboles, et ce qu'elle lit de chacun (`titre`,
`textes[0]` ; pour la section `demo`, aussi `textes[1]`, l'avertissement). Un `id`
retiré, renommé, ou un `textes[1]` déplacé fait échouer le contrôle (CONTRAT), et
--ecrire refuse d'écrire un tel fichier : l'app refuse un contenu incomplet et
garde sa dernière lecture, donc toutes les apps installées cesseraient de suivre le
site sans que personne le voie. Pareil changement se décide AVEC coprofirst-ios :
nouvelle version de l'app d'abord, ou `format: 2`. La liste est recopiée de
`ContenuVitrine.idsRequis` (CoproFirst/Entree/Contenu/ContenuVitrine.swift de
coprofirst-ios) ; elle se modifie des deux côtés ensemble.

  python3 scripts/contenu-accueil.py            contrôle (pre-commit, CI) : 0 à jour, 1 écart, 2 INCONNU
  python3 scripts/contenu-accueil.py --ecrire   réécrit site/contenu.json depuis index.html
  python3 scripts/contenu-accueil.py --selftest
"""
import difflib
import json
import re
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

SITE = Path(__file__).resolve().parent.parent / "site"
BASE = "https://coprofirst.fr/"
FORMAT = 1
OK, ECART, INCONNU = 0, 1, 2
VIDES = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
# Le contrat avec l'app iOS (coprofirst-ios#51, ContenuVitrine.idsRequis). Pour chaque
# section : le nombre de textes qu'elle doit porter (l'app lit textes[0], et pour la
# démo textes[1]) et les éléments requis, chacun avec un titre et textes[0].
CONTRAT_APP = {
    "heros": {"textes": 1, "elements": ()},
    "fonctions": {"textes": 1, "elements": ("demande", "documents", "point-syndic", "badges", "carnet", "communaute")},
    "demo": {"textes": 2, "elements": ("conseil-syndical", "coproprietaire", "locataire")},
}
IDENTIFIANT = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ESPACES = re.compile(r"[ \t\r\n]+")  # pas l'espace insécable : la typographie française la garde


class Noeud:
    def __init__(self, balise, attributs):
        self.balise, self.attr, self.enfants = balise, dict(attributs), []


class Arbre(HTMLParser):
    """Un arbre minimal : la page est écrite à la main et ferme ses balises."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.racine = Noeud("#document", [])
        self.pile = [self.racine]

    def handle_starttag(self, balise, attributs):
        noeud = Noeud(balise, attributs)
        self.pile[-1].enfants.append(noeud)
        if balise not in VIDES:
            self.pile.append(noeud)

    def handle_startendtag(self, balise, attributs):
        self.pile[-1].enfants.append(Noeud(balise, attributs))

    def handle_endtag(self, balise):
        for i in range(len(self.pile) - 1, 0, -1):
            if self.pile[i].balise == balise:
                del self.pile[i:]
                return

    def handle_data(self, donnees):
        self.pile[-1].enfants.append(donnees)


def noeuds(n):
    yield n
    for e in n.enfants:
        if isinstance(e, Noeud):
            yield from noeuds(e)


def cache(n):
    return n.attr.get("aria-hidden") == "true" or "data-contenu-hors" in n.attr


def texte(n, sans_liens=False):
    morceaux = []

    def lire(x):
        if isinstance(x, str):
            morceaux.append(x)
        elif x.balise == "br":
            morceaux.append(" ")
        elif not cache(x) and x.balise not in ("script", "style") and not (sans_liens and x.balise == "a"):
            for e in x.enfants:
                lire(e)

    lire(n)
    return ESPACES.sub(" ", "".join(morceaux)).strip(" \t\r\n")


def classes(n):
    return n.attr.get("class", "").split()


def contient_element(n):
    return any("data-contenu" in d.attr and d.balise != "img" for d in noeuds(n) if d is not n)


class Lecture:
    """Projection d'une page : (contenu, écarts). Fonction pure, ne lit que `html` et `site`."""

    def __init__(self, html, site):
        arbre = Arbre()
        arbre.feed(html)
        self.racine, self.site, self.ecarts = arbre.racine, site, []
        self.par_id = {n.attr["id"]: n for n in noeuds(self.racine) if "id" in n.attr}

    def portee(self, ident, quoi):
        return {"id": ident, "_quoi": quoi, "_b": None}

    def parcourir(self, n, p, dans_texte=False, element_permis=True):
        for e in n.enfants:
            if isinstance(e, Noeud) and not cache(e):
                self.noeud(e, p, dans_texte, element_permis)

    def noeud(self, n, p, dans_texte, element_permis):
        if n.balise == "img":
            if "data-contenu" in n.attr:
                self.image(n, p)
            return
        if "data-contenu" in n.attr:
            if not element_permis:
                self.ecarts.append(f"IMBRIQUE {p['_quoi']} : élément {n.attr['data-contenu']!r} dans un élément")
                return
            self.element(n, p)
            return
        if n.balise == "a" and n.attr.get("href"):
            t = texte(n)
            if t:
                p.setdefault("liens", []).append({"texte": t, "adresse": urljoin(BASE, n.attr["href"])})
        if "surtitre" in classes(n) and "surtitre" not in p:
            p["surtitre"] = texte(n)
            return
        if n.balise in ("h1", "h2", "h3") and "titre" not in p:
            p["titre"] = texte(n)
            return
        if n.balise == "b" and p["_b"] is None:
            p["_b"] = texte(n)
        if not dans_texte and (n.balise in ("p", "small") or (n.balise == "li" and not contient_element(n))):
            t = texte(n)
            # Une rangée de boutons (<p> fait de liens seulement) part dans `liens`, pas dans `textes`
            if t and texte(n, sans_liens=True):
                p.setdefault("points" if n.balise == "li" else "textes", []).append(t)
            dans_texte = True
        self.parcourir(n, p, dans_texte, element_permis)

    def image(self, n, p):
        src = n.attr.get("src", "")
        chemin = src.split("?", 1)[0]
        if re.match(r"^([a-z]+:|/)", chemin) or ".." in chemin.split("/"):
            self.ecarts.append(f"IMAGE    {p['_quoi']} : {src!r} n'est pas un chemin relatif du site")
        elif not (self.site / chemin).is_file():
            self.ecarts.append(f"IMAGE    {p['_quoi']} : {chemin} n'existe pas dans site/")
        img = {"id": n.attr["data-contenu"], "image": src}
        for cle, attr in (("largeur", "width"), ("hauteur", "height")):
            if n.attr.get(attr, "").isdigit():
                img[cle] = int(n.attr[attr])
        if n.attr.get("alt"):
            img["description"] = ESPACES.sub(" ", n.attr["alt"]).strip()
        p.setdefault("images", []).append(img)

    def element(self, n, section):
        e = self.portee(n.attr["data-contenu"], f"{section['_quoi']} › {n.attr['data-contenu']}")
        if n.balise == "a" and n.attr.get("href"):
            e["adresse"] = urljoin(BASE, n.attr["href"])
        onglet = self.par_id.get(n.attr.get("aria-labelledby", ""))
        if onglet is not None:
            e["etiquette"] = texte(onglet)
        self.parcourir(n, e, element_permis=False)
        section.setdefault("elements", []).append(e)

    def section(self, n, ident):
        s = self.portee(ident, ident)
        s["_b"] = False  # le repli sur <b> ne vaut que pour un élément
        self.parcourir(n, s)
        return s

    def lire(self):
        sections = []
        for n in noeuds(self.racine):
            if n.balise == "section" and "data-contenu" in n.attr and not cache(n):
                sections.append(self.section(n, n.attr["data-contenu"]))
            elif n.balise == "footer":
                sections.append(self.section(n, "pied"))
        if not any(s["id"] != "pied" for s in sections):
            self.ecarts.append("VIDE     aucune <section data-contenu> dans index.html")
        self.valider(sections, "la page")
        for s in sections:
            self.valider(s.get("elements", []), s["id"])
            self.valider(s.get("images", []) + [i for e in s.get("elements", []) for i in e.get("images", [])], f"images de {s['id']}")
        return {"format": FORMAT, "adresse": BASE, "langue": "fr", "sections": [nettoyer(s) for s in sections]}, self.ecarts

    def valider(self, liste, ou):
        vus = set()
        for x in liste:
            if not IDENTIFIANT.match(x["id"]):
                self.ecarts.append(f"ID       {ou} : {x['id']!r} (minuscules, chiffres et tirets)")
            if x["id"] in vus:
                self.ecarts.append(f"DOUBLON  {ou} : {x['id']!r} deux fois")
            vus.add(x["id"])
            if "_quoi" in x and x["id"] != "pied" and "titre" not in x and not x.get("_b"):
                self.ecarts.append(f"TITRE    {x['_quoi']} : ni titre ni <b>")


def nettoyer(p):
    if "titre" not in p and p.get("_b"):
        p["titre"] = p["_b"]
    sortie = {}
    for cle in ("id", "etiquette", "surtitre", "titre", "adresse", "textes", "points", "liens", "images"):
        if p.get(cle):
            sortie[cle] = p[cle]
    if p.get("elements"):
        sortie["elements"] = [nettoyer(e) for e in p["elements"]]
    return sortie


def ecarts_contrat(contenu, contrat):
    """Les écarts entre ce que la page donne et ce que l'app iOS lit (CONTRAT_APP)."""
    ecarts = []

    def verifier(quoi, noeud, textes):
        if noeud is None:
            ecarts.append(f"CONTRAT  {quoi} : absent — l'app iOS l'exige, à décider avec coprofirst-ios")
            return
        if not noeud.get("titre"):
            ecarts.append(f"CONTRAT  {quoi} : plus de titre — l'app iOS le lit")
        if len(noeud.get("textes", [])) < textes:
            ecarts.append(f"CONTRAT  {quoi} : textes[{textes - 1}] absent — l'app iOS le lit")

    sections = {s.get("id"): s for s in contenu.get("sections", [])}
    for sid, regle in (contrat or {}).items():
        section = sections.get(sid)
        verifier(f"section {sid}", section, regle["textes"])
        if section is None:
            continue
        elements = {e.get("id"): e for e in section.get("elements", [])}
        for eid in regle["elements"]:
            verifier(f"{sid}/{eid}", elements.get(eid), 1)
    return ecarts


def serialiser(contenu):
    return json.dumps(contenu, ensure_ascii=False, indent=1) + "\n"


def juger(site, contrat=CONTRAT_APP):
    """(verdict, écarts, texte attendu de contenu.json). Ne modifie rien."""
    try:
        html = (site / "index.html").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return INCONNU, [f"INCONNU  index.html illisible : {e}"], None
    contenu, ecarts = Lecture(html, site).lire()
    ecarts += ecarts_contrat(contenu, contrat)
    attendu = serialiser(contenu)
    try:
        actuel = (site / "contenu.json").read_text(encoding="utf-8")
    except FileNotFoundError:
        actuel = None
        ecarts.append("ABSENT   site/contenu.json")
    except (OSError, UnicodeDecodeError) as e:
        return INCONNU, ecarts + [f"INCONNU  contenu.json illisible : {e}"], attendu
    if actuel is not None and actuel != attendu:
        diff = list(difflib.unified_diff(actuel.splitlines(), attendu.splitlines(), "contenu.json", "index.html", n=0, lineterm=""))
        ecarts.append("DIVERGE  site/contenu.json ne rend plus index.html :\n" + "\n".join(diff[:30]))
    return (ECART if ecarts else OK), ecarts, attendu


def principal(site, ecrire, contrat=CONTRAT_APP):
    verdict, ecarts, attendu = juger(site, contrat)
    structurels = [e for e in ecarts if not e.startswith(("ABSENT", "DIVERGE"))]
    if ecrire and attendu is not None and not structurels and verdict != INCONNU:
        (site / "contenu.json").write_text(attendu, encoding="utf-8", newline="\n")
        print("contenu.json réécrit depuis index.html")
        return OK
    for e in ecarts:
        print(e)
    if verdict == OK:
        print("contenu-accueil : OK")
    elif not structurels:
        print("contenu-accueil : à jour avec  python3 scripts/contenu-accueil.py --ecrire")
    return verdict


PAGE_TEST = """<html><body><header><nav><a href="#x">hors section</a></nav></header>
<section class="heros" data-contenu="heros"><h1>La copro, <span>enfin.</span></h1>
 <p class="chapo">Un texte&nbsp;!</p><p><span aria-hidden="true">* </span>Précision.</p>
 <p class="actions"><a href="demo.html">Essayer →</a></p>
 <img data-contenu="capture" src="c.jpg?v=1" width="10" height="20" alt="Une capture">
 <img src="decor.jpg"></section>
<section id="f" data-contenu="fonctions"><div class="tete"><span class="surtitre">Fonctions</span><h2>Titre</h2><p>Sous-titre</p></div>
 <article data-contenu="demande"><h3>Demande</h3><p>Trois temps.</p><div aria-hidden="true"><p>décor</p></div></article>
 <div role="tab" id="t-a">Onglet A</div>
 <div data-contenu="panneau" aria-labelledby="t-a"><h3>Panneau</h3><ul><li>un</li><li>deux</li></ul></div>
 <ul><li><a data-contenu="role" href="demo.html#cs"><b>Conseil</b><small>Bilan</small></a></li></ul>
 <ul><li>point de section</li></ul>
 <figure data-contenu-hors><p>Le mot du créateur</p></figure></section>
<section data-contenu="avis" aria-hidden="true"><h2>masquée</h2></section>
<footer><p>Marque<br>déposée</p><nav><a href="/mentions-legales.html">Mentions</a></nav></footer></body></html>"""


def selftest():
    echecs = 0

    def verifie(nom, ok):
        nonlocal echecs
        echecs += not ok
        print(f"  {'ok     ' if ok else 'ÉCHEC  '} {nom}")

    with tempfile.TemporaryDirectory() as t:
        site = Path(t)
        (site / "c.jpg").write_bytes(b"x")
        (site / "index.html").write_text(PAGE_TEST, encoding="utf-8")
        contenu, ecarts = Lecture(PAGE_TEST, site).lire()
        s = {x["id"]: x for x in contenu["sections"]}
        h, f = s.get("heros", {}), s.get("fonctions", {})
        el = {e["id"]: e for e in f.get("elements", [])}
        verifie("page conforme : aucun écart", ecarts == [])
        verifie("sections dans l'ordre, masquée exclue, pied compris", list(s) == ["heros", "fonctions", "pied"])
        verifie("titre sans balise, insécable gardée", h.get("titre") == "La copro, enfin." and h.get("textes", [""])[0] == "Un texte\xa0!")
        verifie("texte décoratif écarté, rangée de liens hors des textes", h.get("textes") == ["Un texte\xa0!", "Précision."])
        verifie("lien absolu", h.get("liens") == [{"texte": "Essayer →", "adresse": BASE + "demo.html"}])
        verifie("seule l'image déclarée part", h.get("images") == [{"id": "capture", "image": "c.jpg?v=1", "largeur": 10, "hauteur": 20, "description": "Une capture"}])
        verifie("surtitre, titre, texte de section", (f.get("surtitre"), f.get("titre"), f.get("textes")) == ("Fonctions", "Titre", ["Sous-titre"]))
        verifie("élément : titre et texte, décor exclu", el.get("demande") == {"id": "demande", "titre": "Demande", "textes": ["Trois temps."]})
        verifie("élément : étiquette de l'onglet, points", el.get("panneau") == {"id": "panneau", "etiquette": "Onglet A", "titre": "Panneau", "points": ["un", "deux"]})
        verifie("élément lien : adresse, titre tiré du <b>", el.get("role") == {"id": "role", "titre": "Conseil", "adresse": BASE + "demo.html#cs", "textes": ["Bilan"]})
        verifie("points de section ; li d'élément et bloc hors exclus", f.get("points") == ["point de section"])
        verifie("pied : <br> en espace, lien légal", s.get("pied") == {"id": "pied", "textes": ["Marque déposée"], "liens": [{"texte": "Mentions", "adresse": BASE + "mentions-legales.html"}]})

        def codes(html):
            (site / "index.html").write_text(html, encoding="utf-8")
            return sorted({e.split()[0] for e in juger(site, None)[1]})

        verifie("contenu.json absent → ABSENT", codes(PAGE_TEST) == ["ABSENT"])
        verifie("--ecrire, puis contrôle conforme", principal(site, ecrire=True, contrat=None) == OK and juger(site, None)[0] == OK)
        verifie("page retouchée, fichier non suivi → DIVERGE", codes(PAGE_TEST.replace("Trois temps.", "Quatre temps.")) == ["DIVERGE"])
        verifie("image absente → IMAGE", "IMAGE" in codes(PAGE_TEST.replace('src="c.jpg', 'src="d.jpg')))
        verifie("image externe → IMAGE", "IMAGE" in codes(PAGE_TEST.replace('src="c.jpg', 'src="https://x.fr/c.jpg')))
        verifie("identifiant en double → DOUBLON", "DOUBLON" in codes(PAGE_TEST.replace('data-contenu="panneau"', 'data-contenu="demande"')))
        verifie("identifiant mal formé → ID", "ID" in codes(PAGE_TEST.replace('data-contenu="panneau"', 'data-contenu="Panneau A"')))
        verifie("élément sans titre → TITRE", "TITRE" in codes(PAGE_TEST.replace("<h3>Demande</h3>", "")))
        verifie("élément dans un élément → IMBRIQUE", "IMBRIQUE" in codes(PAGE_TEST.replace("<p>Trois temps.</p>", '<p data-contenu="x">Trois temps.</p>')))
        verifie("aucune section → VIDE", "VIDE" in codes("<html><body><footer><p>x</p></footer></body></html>"))
        (site / "index.html").write_text(PAGE_TEST.replace("<h3>Demande</h3>", ""), encoding="utf-8")
        avant = (site / "contenu.json").read_text(encoding="utf-8")
        verifie("--ecrire refuse une page fautive", principal(site, ecrire=True, contrat=None) == ECART and (site / "contenu.json").read_text(encoding="utf-8") == avant)
        (site / "index.html").unlink()
        verifie("index.html absent → INCONNU, jamais OK", juger(site, None)[0] == INCONNU)
        # Le contrat avec l'app iOS : chaque cas fautif doit être refusé (coprofirst-site#66).
        contrat = {"heros": {"textes": 2, "elements": ()}, "fonctions": {"textes": 1, "elements": ("demande",)}}

        def contrat_sur(html):
            (site / "index.html").write_text(html, encoding="utf-8")
            return [e for e in juger(site, contrat)[1] if e.startswith("CONTRAT")]

        def refuse(html, fragment):
            return any(fragment in e for e in contrat_sur(html))

        verifie("contrat tenu → aucun écart CONTRAT", contrat_sur(PAGE_TEST) == [])
        verifie("id requis retiré → CONTRAT", refuse(PAGE_TEST.replace('data-contenu="demande"', ""), "fonctions/demande : absent"))
        verifie("id requis renommé → CONTRAT", refuse(PAGE_TEST.replace('data-contenu="demande"', 'data-contenu="demandes"'), "fonctions/demande : absent"))
        verifie("section requise retirée → CONTRAT", refuse(PAGE_TEST.replace('data-contenu="heros"', ""), "section heros : absent"))
        verifie("titre de l'élément perdu → CONTRAT", refuse(PAGE_TEST.replace("<h3>Demande</h3>", "<p>Demande</p>"), "fonctions/demande : plus de titre"))
        verifie("textes[1] déplacé → CONTRAT", refuse(PAGE_TEST.replace("Précision.", ""), "section heros : textes[1] absent"))
        (site / "index.html").write_text(PAGE_TEST, encoding="utf-8")
        principal(site, ecrire=True, contrat=None)
        avant = (site / "contenu.json").read_text(encoding="utf-8")
        (site / "index.html").write_text(PAGE_TEST.replace('data-contenu="demande"', ""), encoding="utf-8")
        verifie("--ecrire refuse un contenu qui perd un id requis", principal(site, ecrire=True, contrat=contrat) == ECART and (site / "contenu.json").read_text(encoding="utf-8") == avant)
    print("selftest : OK" if echecs == 0 else f"selftest : {echecs} ÉCHEC(S)")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if args == ["--selftest"]:
        sys.exit(selftest())
    if args not in ([], ["--ecrire"]):
        print("Usage : python3 scripts/contenu-accueil.py [--ecrire | --selftest]")
        sys.exit(1)
    sys.exit(principal(SITE, ecrire=args == ["--ecrire"]))
