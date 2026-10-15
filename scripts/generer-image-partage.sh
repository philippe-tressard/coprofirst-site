#!/bin/bash
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# generer-image-partage.sh — photographie scripts/image-partage.html en
# site/partage.png (1200 × 630), l'image que montrent les réseaux sociaux et les
# messageries (balises og:image et twitter:image des pages du site).
#
#   bash scripts/generer-image-partage.sh
#
# À relancer quand le gabarit change, puis committer l'image. Il faut Chrome ou
# Edge, et Python avec Pillow ; la typographie est celle du poste (Georgia, polices
# système), comme pour un visiteur du site — l'image ne se reconstruit donc pas à
# l'octet près ailleurs.
set -euo pipefail

racine=$(git rev-parse --show-toplevel)
cd "$racine"

navigateur=""
for n in "${CHROME:-}" chromium chromium-browser google-chrome \
  "/c/Program Files/Google/Chrome/Application/chrome.exe" \
  "/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"; do
  [ -n "$n" ] && command -v "$n" >/dev/null 2>&1 && { navigateur="$n"; break; }
done
[ -n "$navigateur" ] || { echo "INCONNU : ni Chrome, ni Chromium, ni Edge (variable CHROME)" >&2; exit 2; }

gabarit="$racine/scripts/image-partage.html"
sortie="$racine/site/partage.png"
# Chemin Windows pour un navigateur Windows lancé depuis Git Bash
if command -v cygpath >/dev/null 2>&1; then
  gabarit="$(cygpath -m "$gabarit")"; sortie="$(cygpath -w "$sortie")"
fi

rm -f "$racine/site/partage.png"
# Le mode sans fenêtre retranche de la hauteur demandée celle d'une barre d'outils
# absente (constaté le 15/10/2026 : 1200 × 630 laissait une bande blanche de près
# de 100 px sous la page) : on photographie plus haut, puis on recadre.
"$navigateur" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
  --window-size=1200,800 --screenshot="$sortie" "file:///$gabarit" >/dev/null 2>&1

# Le contrôle porte sur le résultat, pas sur le code de retour du navigateur.
[ -s "$racine/site/partage.png" ] || { echo "ÉCHEC : aucune image produite" >&2; exit 1; }
python -c 'import sys; from PIL import Image; i = Image.open(sys.argv[1]); i.crop((0, 0, 1200, 630)).save(sys.argv[1], optimize=True)' "$sortie"
dims=$(od -An -tu1 -j16 -N8 "$racine/site/partage.png" | awk '{print $3*256+$4 "x" $7*256+$8}')
[ "$dims" = "1200x630" ] || { echo "ÉCHEC : image de $dims, attendu 1200x630" >&2; exit 1; }
echo "site/partage.png : 1200x630, $(wc -c < "$racine/site/partage.png") octets"
