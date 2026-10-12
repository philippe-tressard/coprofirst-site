#!/bin/bash
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# verifier-depot.sh — ce que Windows abîme sans un mot (standards/08 §3, standards/10) :
#   - un BOM UTF-8 en tête de fichier texte ;
#   - des fins de ligne CRLF dans un dépôt écrit en LF (.gitattributes) ;
#   - un script .sh ou un hook de .githooks/ sans bit d'exécution dans l'index
#     (Windows avale `chmod +x`) ;
#   - un script dont la syntaxe est fausse (`bash -n`).
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
  if [ "$(tr -cd '\r' < "$f" | wc -c)" -gt 0 ]; then
    echo "CRLF     $f"
  fi
  # Les hooks git n'ont pas d'extension, mais s'exécutent comme les scripts
  if [[ "$f" == *.sh || "$f" == .githooks/* ]]; then
    [ "$mode" = "100755" ] || echo "MODE     $f ($mode, attendu 100755 : git update-index --chmod=+x $f)"
    bash -n "$f" 2>/dev/null || echo "SYNTAXE  $f (bash -n)"
  fi
}

selftest() {
  local t; t=$(mktemp -d)
  printf 'ok\n' > "$t/bon.html"
  printf '\xef\xbb\xbfok\n' > "$t/bom.html"
  printf 'ok\r\n' > "$t/crlf.css"
  printf '#!/bin/bash\necho ok\n' > "$t/bon.sh"
  printf '#!/bin/bash\nif then\n' > "$t/faux.sh"
  printf '\x89PNG\r\n' > "$t/image.png"
  local echecs=0
  verifie() { # <attendu> <fichier> <mode>
    local obtenu; obtenu=$(juger_fichier "$t/$2" "$3" | awk '{print $1}' | tr '\n' ' ')
    if [ "$obtenu" = "$1" ]; then echo "  ok      $2 → «$1»"; else echo "  ÉCHEC   $2 → «$obtenu», attendu «$1»"; echecs=$((echecs + 1)); fi
  }
  verifie "" bon.html 100644
  verifie "BOM " bom.html 100644
  verifie "CRLF " crlf.css 100644
  verifie "" bon.sh 100755
  verifie "MODE " bon.sh 100644
  verifie "SYNTAXE " faux.sh 100755
  verifie "" image.png 100644
  rm -rf "$t"
  [ "$echecs" -eq 0 ] && echo "selftest : OK" || { echo "selftest : $echecs ÉCHEC(S)"; return 1; }
}

if [ "${1:-}" = "--selftest" ]; then selftest; exit $?; fi

racine=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "INCONNU : pas un dépôt git"; exit 2; }
cd "$racine" || exit 2
nb=$(git ls-files | wc -l)
# Cas zéro : un index vide ne prouve rien (standards/04 §2)
[ "$nb" -gt 0 ] || { echo "INCONNU : aucun fichier dans l'index — rien n'a été vérifié"; exit 2; }

ecarts=$(git ls-files -s | while read -r mode _ _ f; do juger_fichier "$f" "$mode"; done)
if [ -n "$ecarts" ]; then
  echo "$ecarts"
  echo "verifier-depot : $(echo "$ecarts" | wc -l) écart(s) sur $nb fichiers"
  exit 1
fi
echo "verifier-depot : OK ($nb fichiers)"
