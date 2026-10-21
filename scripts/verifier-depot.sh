#!/bin/bash
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# verifier-depot.sh — ce que Windows abîme sans un mot (standards/08 §3, standards/10) :
#   - un BOM UTF-8 en tête de fichier texte ;
#   - des fins de ligne CRLF dans un dépôt écrit en LF (.gitattributes) — sauf les
#     scripts .cmd, qui doivent au contraire être entièrement en CRLF ;
#   - un script .sh ou .py, ou un hook de .githooks/, sans bit d'exécution dans l'index
#     (Windows avale `chmod +x`) ;
#   - un script dont la syntaxe est fausse (`bash -n`).
# Et ce que la page publiée doit à la loi et à ses visiteurs (standards/14 §3, §4, §9) :
#   - les pages Mentions légales et Confidentialité existent ;
#   - chaque page du site y renvoie, sans lien mort (`href="#"`), avec le même pied ;
#   - aucune ressource chargée depuis un autre site (police, script, traceur).
# Lit l'INDEX git : en pre-commit, c'est ce qui va partir ; en CI, ce qui est parti.
#
# Usage : bash scripts/verifier-depot.sh            (sortie non nulle = écart)
#         bash scripts/verifier-depot.sh --selftest (la règle, sans dépôt)
set -uo pipefail

# Extensions qui ne sont pas du texte : aucune vérification d'encodage.
BINAIRES='\.(png|jpe?g|gif|webp|ico|pdf|woff2?)$'

# juger_fichier <chemin> <mode git> — fonction PURE : lit le fichier, n'écrit rien.
# Écrit un écart par ligne ; rien si le fichier est conforme.
juger_fichier() {
  local f="$1" mode="$2"
  [[ "$f" =~ $BINAIRES ]] && return 0
  [ -f "$f" ] || return 0
  if [ "$(head -c 3 "$f" | od -An -tx1 | tr -d ' \n')" = "efbbbf" ]; then
    echo "BOM      $f"
  fi
  # Compter les octets CR : le grep de Git Bash retire le CR avant de comparer
  if [[ "$f" == *.cmd ]]; then
    # Autant de CR que de LF : chaque ligne finit en CRLF (cmd.exe lit mal le LF seul)
    [ "$(tr -cd '\r' < "$f" | wc -c)" -eq "$(tr -cd '\n' < "$f" | wc -c)" ] || echo "LF       $f (un script .cmd s'écrit en CRLF)"
  elif [ "$(tr -cd '\r' < "$f" | wc -c)" -gt 0 ]; then
    echo "CRLF     $f"
  fi
  # Les hooks git n'ont pas d'extension, mais s'exécutent comme les scripts
  if [[ "$f" == *.sh || "$f" == *.py || "$f" == .githooks/* ]]; then
    [ "$mode" = "100755" ] || echo "MODE     $f ($mode, attendu 100755 : git update-index --chmod=+x $f)"
  fi
  # Un script Python prouve sa syntaxe par son --selftest, lancé en CI
  if [[ "$f" == *.sh || "$f" == .githooks/* ]]; then
    bash -n "$f" 2>/dev/null || echo "SYNTAXE  $f (bash -n)"
  fi
}

# juger_page <chemin> — fonction PURE : les règles d'une page HTML publiée.
juger_page() {
  local f="$1"
  grep -q 'href="#"' "$f" && echo "LIEN     $f (href=\"#\" : lien qui ne mène nulle part)"
  grep -q 'href="mentions-legales.html"' "$f" || echo "MENTIONS $f (pas de lien vers mentions-legales.html)"
  grep -q 'href="confidentialite.html"' "$f" || echo "CONFID   $f (pas de lien vers confidentialite.html)"
  # Le thème sombre par défaut vit dans theme.js (chargé avant la feuille de style, sans
  # quoi la page clignote) et dans l'interrupteur de l'en-tête : sans l'un ou l'autre,
  # un visiteur reste coincé dans un thème qu'il n'a pas choisi.
  # (en absolu « /theme.js » dans 404.html, qui répond aussi aux adresses profondes)
  grep -q '<script src="/\?theme.js' "$f" || echo "THEME    $f (theme.js non chargé)"
  grep -q 'data-bascule-theme' "$f" || echo "THEME    $f (pas d'interrupteur de thème)"
  # Ressource tierce : <script src>, <link href>, <img src>, url() ou @import vers http(s).
  # Un <link rel="canonical"> ou « alternate » désigne une adresse, il ne charge rien :
  # il est écarté (une balise par ligne, comme dans les pages du site).
  grep -Eiv '<link rel="(canonical|alternate)"' "$f" \
    | grep -Eiq '<(script|img|iframe)[^>]* src="(https?:)?//|<link[^>]* href="(https?:)?//|url\((["'"'"'])?(https?:)?//|@import' \
    && echo "TIERS    $f (ressource chargée depuis un autre site)"
  return 0
}

# pied <chemin> — le pied de page, sans la marque de la page courante.
pied() { sed -n '/<footer>/,/<\/footer>/p' "$1" | sed 's/ aria-current="page"//'; }

# juger_site — les pages obligatoires existent, chaque page est conforme, et toutes
# portent le même pied de page (un site statique sans build le recopie : ce contrôle
# empêche les copies de diverger).
juger_site() {
  local f ref=""
  for f in site/mentions-legales.html site/confidentialite.html; do
    [ -f "$f" ] || echo "MANQUE   $f (page obligatoire)"
  done
  for f in site/*.html; do
    [ -f "$f" ] || continue
    juger_page "$f"
    if [ -z "$ref" ]; then ref="$f"
    elif [ "$(pied "$f")" != "$(pied "$ref")" ]; then echo "PIED     $f (pied de page différent de $ref)"; fi
  done
}

selftest() {
  local t; t=$(mktemp -d)
  printf 'ok\n' > "$t/bon.html"
  printf '\xef\xbb\xbfok\n' > "$t/bom.html"
  printf 'ok\r\n' > "$t/crlf.css"
  printf '@echo off\r\nexit /b 0\r\n' > "$t/bon.cmd"
  printf '@echo off\nexit /b 0\n' > "$t/lf.cmd"
  printf '#!/bin/bash\necho ok\n' > "$t/bon.sh"
  printf '#!/bin/bash\nif then\n' > "$t/faux.sh"
  printf '\x89PNG\r\n' > "$t/image.png"
  printf '#!/usr/bin/env python3\n' > "$t/outil.py"
  local echecs=0
  verifie() { # <attendu> <fichier> <mode>
    local obtenu; obtenu=$(juger_fichier "$t/$2" "$3" | awk '{print $1}' | tr '\n' ' ')
    if [ "$obtenu" = "$1" ]; then echo "  ok      $2 → «$1»"; else echo "  ÉCHEC   $2 → «$obtenu», attendu «$1»"; echecs=$((echecs + 1)); fi
  }
  verifie "" bon.html 100644
  verifie "BOM " bom.html 100644
  verifie "CRLF " crlf.css 100644
  verifie "" bon.cmd 100644
  verifie "LF " lf.cmd 100644
  verifie "" bon.sh 100755
  verifie "MODE " bon.sh 100644
  verifie "SYNTAXE " faux.sh 100755
  verifie "" image.png 100644
  verifie "" outil.py 100755
  verifie "MODE " outil.py 100644
  # Règles d'une page publiée
  local theme='<script src="theme.js?v=1"></script><button data-bascule-theme></button>'
  local liens='<a href="mentions-legales.html">M</a><a href="confidentialite.html">C</a>'"$theme"
  printf '%s
' "<footer>$liens</footer>" > "$t/bonne.html"
  printf '%s
' '<a href="#">x</a>' "$liens" > "$t/morte.html"
  printf '%s
' '<a href="mentions-legales.html">M</a>' > "$t/sans-confid.html"
  printf '%s
' "$liens" '<link rel="stylesheet" href="https://fonts.example/f.css">' > "$t/police.html"
  printf '%s
' "$liens" '<script src="//traceur.example/t.js"></script>' > "$t/traceur.html"
  printf '%s
' "$liens" '<a href="https://github.com/x">code</a>' > "$t/lien-sortant.html"
  printf '%s
' '<a href="mentions-legales.html">M</a><a href="confidentialite.html">C</a>' > "$t/sans-theme.html"
  printf '%s
' "$liens" '<link rel="canonical" href="https://coprofirst.fr/">' > "$t/canonique.html"
  printf '%s
' "$liens" '<link rel="canonical" href="https://coprofirst.fr/">' '<link rel="stylesheet" href="https://fonts.example/f.css">' > "$t/canonique-et-police.html"
  page() { # <attendu> <fichier>
    local obtenu; obtenu=$(juger_page "$t/$2" | awk '{print $1}' | tr '
' ' ')
    if [ "$obtenu" = "$1" ]; then echo "  ok      $2 → «$1»"; else echo "  ÉCHEC   $2 → «$obtenu», attendu «$1»"; echecs=$((echecs + 1)); fi
  }
  page "" bonne.html
  page "LIEN " morte.html
  page "CONFID THEME THEME " sans-confid.html
  page "TIERS " police.html
  page "TIERS " traceur.html
  page "" lien-sortant.html
  page "THEME THEME " sans-theme.html
  printf '%s
' '<a href="mentions-legales.html">M</a><a href="confidentialite.html">C</a><script src="/theme.js?v=1"></script><button data-bascule-theme></button>' > "$t/theme-absolu.html"
  page "" theme-absolu.html
  page "" canonique.html
  page "TIERS " canonique-et-police.html
  rm -rf "$t"
  [ "$echecs" -eq 0 ] && echo "selftest : OK" || { echo "selftest : $echecs ÉCHEC(S)"; return 1; }
}

if [ "${1:-}" = "--selftest" ]; then selftest; exit $?; fi

racine=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "INCONNU : pas un dépôt git"; exit 2; }
cd "$racine" || exit 2
nb=$(git ls-files | wc -l)
# Cas zéro : un index vide ne prouve rien (standards/04 §2)
[ "$nb" -gt 0 ] || { echo "INCONNU : aucun fichier dans l'index — rien n'a été vérifié"; exit 2; }

ecarts=$(git ls-files -s | while read -r mode _ _ f; do juger_fichier "$f" "$mode"; done; juger_site)
if [ -n "$ecarts" ]; then
  echo "$ecarts"
  echo "verifier-depot : $(echo "$ecarts" | wc -l) écart(s) sur $nb fichiers"
  exit 1
fi
echo "verifier-depot : OK ($nb fichiers)"
