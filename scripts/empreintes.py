#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
"""empreintes.py — l'adresse de chaque feuille de style, script et capture porte l'empreinte de son contenu.

Cloudflare fait garder les .css et .js 4 h par le navigateur (Cache-Control
max-age=14400), le HTML 5 min. Sans empreinte, un déploiement qui change le HTML
et le JS sert le nouveau HTML avec l'ancien script : le 20/10/2026, la section des
avis restait masquée chez qui avait visité le site (coprofirst-site#6). Avec
`accueil.js?v=<empreinte>`, l'adresse change quand le fichier change, et le
navigateur charge la nouvelle version ; le serveur ignore la requête après « ? ».
Les captures du héros (.jpg, scripts/generer-captures.mjs) suivent la même règle :
une capture refaite garde son nom, son adresse change.

L'empreinte : les 8 premiers caractères hexadécimaux du sha256 du fichier, écrite
dans le dépôt (et non posée au déploiement) pour que le site servi reste octet
pour octet celui du commit (deploiement/deployer.sh --verifier).

  python3 scripts/empreintes.py            contrôle (pre-commit, CI) : 0 à jour, 1 écart
  python3 scripts/empreintes.py --ecrire   met les empreintes à jour dans site/*.html
  python3 scripts/empreintes.py --selftest
"""
import hashlib
import re
import sys
import tempfile
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"
# href="x.css", src="x.js" ou src="x.jpg", locaux (ni schéma ni //), relatifs ou absolus
# (« /x.css », dans 404.html qui répond aussi aux adresses profondes), avec ou sans ?v=…
REFERENCE = re.compile(r'(?P<attr>href|src)="(?P<fichier>/?[^"?#:/][^"?#:]*\.(?:css|js|jpg))(?:\?v=(?P<v>[^"]*))?"')


def empreinte(fichier: Path) -> str:
    return hashlib.sha256(fichier.read_bytes()).hexdigest()[:8]


def juger(site: Path) -> tuple[list[str], dict[Path, str]]:
    """Fonction PURE : (écarts, {page: texte corrigé}). Ne modifie rien."""
    ecarts, corriges = [], {}
    for page in sorted(site.glob("*.html")):
        texte = page.read_text(encoding="utf-8")

        def remplacer(m):
            cible = site / m["fichier"].lstrip("/")
            if not cible.is_file():
                ecarts.append(f"ABSENT   {page.name} : {m['fichier']} n'existe pas")
                return m[0]
            v = empreinte(cible)
            if m["v"] != v:
                ecarts.append(f"VERSION  {page.name} : {m['fichier']}?v={m['v'] or '(rien)'} → attendu ?v={v}")
            return f'{m["attr"]}="{m["fichier"]}?v={v}"'

        nouveau = REFERENCE.sub(remplacer, texte)
        if nouveau != texte:
            corriges[page] = nouveau
    return ecarts, corriges


def principal(site: Path, ecrire: bool) -> int:
    ecarts, corriges = juger(site)
    if ecrire:
        for page, texte in corriges.items():
            page.write_text(texte, encoding="utf-8", newline="\n")
            print(f"empreintes mises à jour : {page.name}")
        ecarts = [e for e in ecarts if not e.startswith("VERSION")]
    for e in ecarts:
        print(e)
    if ecarts:
        if not ecrire:
            print("empreintes : à jour avec  python3 scripts/empreintes.py --ecrire")
        return 1
    if not ecrire:
        print("empreintes : OK")
    return 0


def selftest() -> int:
    echecs = 0
    with tempfile.TemporaryDirectory() as t:
        site = Path(t)
        (site / "a.js").write_text("un", encoding="utf-8")
        (site / "b.css").write_text("deux", encoding="utf-8")
        (site / "d").mkdir()
        (site / "d" / "c.jpg").write_bytes(b"trois")
        va, vb, vc = empreinte(site / "a.js"), empreinte(site / "b.css"), empreinte(site / "d" / "c.jpg")
        cas = [
            ("à jour", f'<link href="b.css?v={vb}"><script src="a.js?v={va}"></script>', []),
            ("sans empreinte", '<script src="a.js"></script>', ["VERSION"]),
            ("empreinte périmée", '<link href="b.css?v=00000000">', ["VERSION"]),
            ("fichier absent", '<script src="c.js"></script>', ["ABSENT"]),
            ("capture dans un dossier, à jour", f'<img src="d/c.jpg?v={vc}">', []),
            ("capture sans empreinte", '<img src="d/c.jpg">', ["VERSION"]),
            ("adresse absolue, à jour", f'<link href="/b.css?v={vb}">', []),
            ("adresse absolue sans empreinte", '<script src="/a.js"></script>', ["VERSION"]),
            ("adresse protocolaire ignorée", '<script src="//x.fr/a.js"></script>', []),
            ("adresses externes et autres types ignorés",
             '<a href="https://x.fr/a.js">x</a><img src="logo.svg"><a href="avis.json">j</a>', []),
        ]
        for nom, html, attendu in cas:
            (site / "p.html").write_text(html, encoding="utf-8")
            obtenu = [e.split()[0] for e in juger(site)[0]]
            ok = obtenu == attendu
            echecs += not ok
            print(f"  {'ok     ' if ok else 'ÉCHEC  '} {nom} → {obtenu}")
        # --ecrire corrige, puis le contrôle passe ; le contenu change → l'empreinte suit
        (site / "p.html").write_text('<script src="a.js"></script>', encoding="utf-8")
        principal(site, ecrire=True)
        ok1 = juger(site)[0] == [] and f"a.js?v={va}" in (site / "p.html").read_text(encoding="utf-8")
        (site / "a.js").write_text("un modifié", encoding="utf-8")
        ok2 = [e.split()[0] for e in juger(site)[0]] == ["VERSION"]
        for nom, ok in (("--ecrire met à jour", ok1), ("fichier modifié, empreinte périmée", ok2)):
            echecs += not ok
            print(f"  {'ok     ' if ok else 'ÉCHEC  '} {nom}")
    print("selftest : OK" if echecs == 0 else f"selftest : {echecs} ÉCHEC(S)")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if args == ["--selftest"]:
        sys.exit(selftest())
    if args not in ([], ["--ecrire"]):
        print("Usage : python3 scripts/empreintes.py [--ecrire | --selftest]")
        sys.exit(1)
    sys.exit(principal(SITE, ecrire=args == ["--ecrire"]))
