#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
"""verifier-css.py — trois règles des feuilles de style que l'œil laisse passer.

1. CONTRASTES (coprofirst-site#37). Les couleurs sont des jetons de commun.css,
   redéfinis par le thème clair et par « contraste élevé » (prefers-contrast:
   more). Dans les quatre modes, chaque jeton de texte se lit sur chaque fond où
   il est posé (4,5:1, WCAG 1.4.3) ; en contraste élevé, le bord se voit sur les
   surfaces (3:1, WCAG 1.4.11). Le 23/10/2026 : --doux sur --peche à 4,45 en
   clair (la légende des avis de cette teinte), et --bord à 1,3 partout.
   La cascade est rejouée : `:root[data-theme="clair"]` l'emporte sur `:root`,
   même dans le bloc de contraste.

2. SURVOL ET APPUI (coprofirst-site#36). Un élément qui se déplace au survol
   (transform) et s'enfonce à l'appui (transform) : la seconde règle REMPLACE la
   première, et l'élément retombe en même temps qu'il s'enfonce. Il lui faut une
   règle `:hover:active` qui compose les deux.

3. FLOU (coprofirst-site#32). Un matériau translucide (backdrop-filter) a son
   repli plein sous « transparence réduite » (prefers-reduced-transparency).

  python3 scripts/verifier-css.py            0 conforme, 1 écart, 2 INCONNU
  python3 scripts/verifier-css.py --selftest
"""
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"

TEXTES = ["encre", "doux", "texte-2", "titre", "lien", "or-texte", "vert", "violet"]
FONDS = ["creme", "creme-2", "carte", "ciel", "menthe", "peche", "sable", "lilas"]
SURFACES = ["creme", "creme-2", "carte"]
SEUIL_TEXTE, SEUIL_BORD = 4.5, 3.0

RE_COMMENTAIRE = re.compile(r"/\*.*?\*/", re.S)
RE_JETON = re.compile(r"--([\w-]+)\s*:\s*(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3})\b")
RE_REGLE = re.compile(r"([^{}]+)\{([^{}]*)\}")
RE_TRANSFORM = re.compile(r"(?<![-\w])transform\s*:\s*(?!none)")
RACINE, CLAIR = ":root", ':root[data-theme="clair"]'
MEDIA_CONTRASTE = re.compile(r"@media\s*\(\s*prefers-contrast\s*:\s*more\s*\)\s*\{")
#  Un bloc dont la condition cite la transparence réduite (seule ou avec une autre).
MEDIA_TRANSPARENCE = re.compile(r"@media[^{]*prefers-reduced-transparency\s*:\s*reduce[^{]*\{")
RE_FLOU = re.compile(r"(?<![-\w])backdrop-filter\s*:\s*(?!none)")


class Inconnu(Exception):
    pass


def bloc_media(css: str, motif=MEDIA_CONTRASTE):
    """(css hors des blocs, contenu des blocs mis bout à bout) — accolades appariées."""
    dedans = []
    while (m := motif.search(css)):
        profondeur, i = 1, m.end()
        while profondeur and i < len(css):
            profondeur += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        if profondeur:
            raise Inconnu("bloc @media non refermé")
        dedans.append(css[m.end():i - 1])
        css = css[:m.start()] + css[i:]
    return css, "".join(dedans)


def jetons(css: str, selecteur: str) -> dict:
    """Les couleurs déclarées par la règle dont le sélecteur est exactement `selecteur`."""
    sortie = {}
    for sel, corps in RE_REGLE.findall(css):
        if sel.strip() == selecteur:
            sortie.update({k: v for k, v in RE_JETON.findall(corps)})
    return sortie


def modes(css: str) -> dict:
    """{mode: jetons} rejouant la cascade : spécificité d'abord (:root < :root[…]),
    puis l'ordre (le bloc de contraste vient après les thèmes)."""
    css = RE_COMMENTAIRE.sub("", css)
    hors, media = bloc_media(css)
    sombre, clair = jetons(hors, RACINE), jetons(hors, CLAIR)
    if not sombre or not clair:
        raise Inconnu("jetons :root ou thème clair introuvables dans commun.css")
    m_sombre, m_clair = jetons(media, RACINE), jetons(media, CLAIR)
    return {
        "sombre": sombre,
        "clair": {**sombre, **clair},
        "sombre, contraste élevé": {**sombre, **m_sombre},
        "clair, contraste élevé": {**sombre, **m_sombre, **clair, **m_clair},
    }


def luminance(hexa: str) -> float:
    h = hexa.lstrip("#")
    h = "".join(c * 2 for c in h) if len(h) == 3 else h
    canaux = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    canaux = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canaux]
    return 0.2126 * canaux[0] + 0.7152 * canaux[1] + 0.0722 * canaux[2]


def contraste(a: str, b: str) -> float:
    claire, sombre = sorted((luminance(a), luminance(b)), reverse=True)
    return (claire + 0.05) / (sombre + 0.05)


def ecarts_contrastes(css: str) -> list:
    ecarts = []
    for mode, t in modes(css).items():
        manque = [j for j in TEXTES + FONDS + ["bord"] if j not in t]
        if manque:
            raise Inconnu(f"{mode} : jetons absents {manque}")
        for texte in TEXTES:
            for fond in FONDS:
                r = contraste(t[texte], t[fond])
                if r < SEUIL_TEXTE:
                    ecarts.append(f"CONTRASTE  {mode} : --{texte} sur --{fond} = {r:.2f} (< {SEUIL_TEXTE})")
        if "contraste" in mode:
            for fond in SURFACES:
                r = contraste(t["bord"], t[fond])
                if r < SEUIL_BORD:
                    ecarts.append(f"BORD       {mode} : --bord sur --{fond} = {r:.2f} (< {SEUIL_BORD})")
    return ecarts


def ecarts_survol_appui(css: str, nom: str) -> list:
    """Sélecteurs déplacés au survol ET à l'appui sans règle `:hover:active`."""
    survol, appui, compose = set(), set(), set()
    for selecteurs, corps in RE_REGLE.findall(RE_COMMENTAIRE.sub("", css)):
        if not RE_TRANSFORM.search(corps):
            continue
        for s in selecteurs.split(","):
            s = s.strip()
            base = s.replace(":hover", "").replace(":active", "")
            if ":hover" in s and ":active" in s:
                compose.add(base)
            elif ":hover" in s:
                survol.add(base)
            elif ":active" in s:
                appui.add(base)
    return [f"APPUI      {nom} : {b} se déplace au survol et s'enfonce à l'appui sans règle "
            f"{b}:hover:active — l'appui annule le survol" for b in sorted((survol & appui) - compose)]


def ecarts_transparence(css: str, nom: str) -> list:
    """Un matériau flouté (backdrop-filter) sans fond plein sous « transparence
    réduite » : le visiteur qui l'a demandé lit encore à travers (#32)."""
    hors, media = bloc_media(RE_COMMENTAIRE.sub("", css), MEDIA_TRANSPARENCE)
    floutes = {s.strip() for sels, corps in RE_REGLE.findall(hors) if RE_FLOU.search(corps)
               for s in sels.split(",")}
    replis = {s.strip() for sels, corps in RE_REGLE.findall(media)
              if re.search(r"backdrop-filter\s*:\s*none", corps) for s in sels.split(",")}
    return [f"FLOU       {nom} : {s} est flouté sans repli @media (prefers-reduced-transparency: "
            "reduce) qui pose backdrop-filter:none" for s in sorted(floutes - replis)]


def feuilles(site: Path):
    """(nom, texte) de chaque feuille du site, et des <style> des pages."""
    for f in sorted(site.glob("*.css")):
        yield f.name, f.read_text(encoding="utf-8")
    for p in sorted(site.glob("*.html")):
        for i, bloc in enumerate(re.findall(r"<style>(.*?)</style>", p.read_text(encoding="utf-8"), re.S)):
            yield f"{p.name} <style> {i + 1}", bloc


def juger(site: Path) -> list:
    commun = site / "commun.css"
    if not commun.is_file():
        raise Inconnu(f"{commun} introuvable")
    ecarts = ecarts_contrastes(commun.read_text(encoding="utf-8"))
    for nom, texte in feuilles(site):
        ecarts += ecarts_survol_appui(texte, nom) + ecarts_transparence(texte, nom)
    return ecarts


def selftest() -> list:
    echecs = []
    base = (":root{" + "".join(f"--{j}:#000;" for j in TEXTES) + "".join(f"--{f}:#fff;" for f in FONDS)
            + "--bord:#eee}" + ':root[data-theme="clair"]{--bord:#ddd}')
    if [e for e in ecarts_contrastes(base) if e.startswith("CONTRASTE")]:
        echecs.append("contraste : un texte noir sur blanc est refusé à tort")
    if not any("--doux sur --peche" in e for e in ecarts_contrastes(base + ':root[data-theme="clair"]{--doux:#999}')):
        echecs.append("contraste : --doux #999 sur blanc (2,8) n'est pas refusé")
    if not any("BORD" in e and "clair, contraste" in e for e in ecarts_contrastes(base)):
        echecs.append("contraste : un bord #ddd sur blanc en contraste élevé n'est pas refusé")
    #  La cascade : le :root du bloc de contraste ne bat pas le thème clair hors bloc.
    media = "@media (prefers-contrast:more){:root{--bord:#555}}"
    if not any("clair, contraste" in e for e in ecarts_contrastes(base + media)):
        echecs.append("contraste : :root du bloc l'emporte à tort sur :root[data-theme=clair]")
    media = '@media (prefers-contrast:more){:root{--bord:#555}:root[data-theme="clair"]{--bord:#555}}'
    if ecarts_contrastes(base + media):
        echecs.append("contraste : un bord #555 dans les deux thèmes est refusé à tort")
    try:
        modes(":root{--a:#000}")
        echecs.append("contraste : un thème clair absent ne rend pas INCONNU")
    except Inconnu:
        pass
    fautif = "@media (hover:hover){.r:hover{transform:translateY(-2px)}}.r:active{transform:scale(.98)}"
    if not ecarts_survol_appui(fautif, "t"):
        echecs.append("appui : .r:hover + .r:active sans composition n'est pas refusé")
    if ecarts_survol_appui(fautif + ".r:hover:active{transform:translateY(-2px) scale(.98)}", "t"):
        echecs.append("appui : la composition :hover:active est refusée à tort")
    if ecarts_survol_appui(".b:active{transform:scale(.97)}.b:hover{background:red}", "t"):
        echecs.append("appui : un survol sans transform est refusé à tort")
    if ecarts_survol_appui(fautif.replace("scale(.98)", "none"), "t"):
        echecs.append("appui : transform:none (mouvement réduit) est compté à tort")
    flou = "header{backdrop-filter:blur(20px)}"
    if not ecarts_transparence(flou, "t"):
        echecs.append("flou : un backdrop-filter sans repli n'est pas refusé")
    repli = "@media (prefers-reduced-transparency:reduce),(prefers-contrast:more){header{backdrop-filter:none}}"
    if ecarts_transparence(flou + repli, "t"):
        echecs.append("flou : le repli (condition double) est refusé à tort")
    return echecs


if __name__ == "__main__":
    # La console Windows est en cp1252 : sans cela, « é » fait tomber le contrôle.
    sys.stdout.reconfigure(encoding="utf-8")
    if "--selftest" in sys.argv:
        e = selftest()
        print("\n".join(e) if e else "verifier-css : autotest OK")
        sys.exit(1 if e else 0)
    try:
        ecarts = juger(SITE)
    except (Inconnu, OSError) as exc:
        print(f"verifier-css : INCONNU — {exc}")
        sys.exit(2)
    for e in ecarts:
        print(e)
    print(f"verifier-css : {'OK' if not ecarts else f'{len(ecarts)} écart(s)'}")
    sys.exit(1 if ecarts else 0)
