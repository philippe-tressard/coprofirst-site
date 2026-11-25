#!/bin/bash
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# controles.sh — LA liste des contrôles hors réseau du dépôt, que le pre-commit et la
# CI appellent au lieu de les énumérer chacun (la liste vivait en cinq exemplaires,
# coprofirst-site#130). Ce que chaque contrôle vérifie : l'en-tête de son script.
#
#   bash scripts/controles.sh              les contrôles (pre-commit)
#   bash scripts/controles.sh --selftest   les selftests, puis les contrôles (CI)
#
# Les contrôles en ligne (concordance avec le produit et les apps) sont dans
# .github/workflows/comptes-demo.yml ; reuse lint et verifier-service.sh (Docker), dans
# ci.yml. Sortie : le premier code non nul d'un contrôle (1 écart, 2 INCONNU), 0 sinon.
set -uo pipefail

racine=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "INCONNU : pas un dépôt git"; exit 2; }
cd "$racine" || exit 2

# Les contrôles, dans l'ordre : « commande » ou « commande|option du selftest ».
# signaler-indexnow.sh se lance par son shebang : le bash et le sed du poste
# (coprofirst-site#128). Sans selftest propre, un script n'a pas de second champ.
CONTROLES=(
  "bash scripts/verifier-depot.sh|--selftest"
  "python3 scripts/verifier-referencement.py|--selftest"
  "python3 scripts/empreintes.py|--selftest"
  "python3 scripts/contenu-accueil.py|--selftest"
  "python3 scripts/verifier-css.py|--selftest"
  "python3 scripts/verifier-security-txt.py|--selftest"
  "python3 scripts/verifier-renvois.py|--selftest"
  "python3 scripts/signaler-echec-ci.py --verifier|--selftest"
  "scripts/signaler-indexnow.sh --selftest"
)
# Ceux qui n'ont qu'un selftest hors réseau (leur fichier ou leur source n'est pas ici).
SELFTESTS_SEULS=(
  "python3 scripts/verifier-avis.py --selftest"
  "python3 scripts/recuperer-avis.py --selftest"
  "python3 scripts/lecture_distante.py --selftest"
  "bash scripts/verifier-public.sh --selftest"
  # Le robot le rejoue avant chaque passage, mais une PR qui le change doit le
  # prouver avant la fusion, pas au passage suivant (coprofirst-site#63).
  "bash scripts/proposer-version.sh --selftest"
)

code=0
lancer() { # <commande…>
  local r
  "$@"; r=$?
  if [ "$r" -ne 0 ]; then echo "controles : ÉCHEC ($r) — $*" >&2; [ "$code" -eq 0 ] && code=$r; fi
}

if [ "${1:-}" = "--selftest" ]; then
  for c in "${CONTROLES[@]}"; do
    [[ "$c" == *"|"* ]] || continue
    commande=${c%%|*}; read -r -a mots <<< "${commande%% --*}"
    lancer "${mots[@]}" "${c##*|}"
  done
  for c in "${SELFTESTS_SEULS[@]}"; do read -r -a mots <<< "$c"; lancer "${mots[@]}"; done
fi
for c in "${CONTROLES[@]}"; do read -r -a mots <<< "${c%%|*}"; lancer "${mots[@]}"; done
[ "$code" -eq 0 ] && echo "controles : OK"
exit "$code"
