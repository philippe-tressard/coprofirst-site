#!/bin/bash
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# verifier-public.sh — ce que le PUBLIC reçoit sur https://coprofirst.fr est-il le commit
# déployé ? deployer.sh --verifier juge l'origine (le conteneur, par SSH) ; la périphérie
# de Cloudflare peut servir l'ancienne version un moment après un déploiement (20 s à
# 2 min, constaté le 14/10/2026), et l'origine seule disait OK pendant ce temps
# (coprofirst-site#131). deployer.sh l'appelle à la fin de chaque vérification.
#
# Lit, sans contourner le cache (c'est ce que voit le visiteur) : l'accueil (/) et la
# feuille commun.css à l'adresse exacte, empreinte ?v= comprise, que l'accueil du commit
# appelle. Chacune doit être octet pour octet celle du commit (Caddy pose no-transform :
# Cloudflare ne réécrit rien). Un écart est réessayé ESSAIS fois, ATTENTE secondes
# d'intervalle (6 × 30 s par défaut), le temps que la périphérie se renouvelle.
#
# Sortie : 0 identique ; 1 ÉCART qui persiste ; 2 INCONNU (adresse injoignable à chaque
# essai, commit ou feuille illisible) — jamais OK faute d'avoir lu (standards/04 §1).
#
#   bash scripts/verifier-public.sh COMMIT
#   bash scripts/verifier-public.sh --selftest   (une périphérie simulée, sans réseau)
set -uo pipefail

BASE="${BASE:-https://coprofirst.fr/}"
ESSAIS="${ESSAIS:-6}"
ATTENTE="${ATTENTE:-30}"

lire_url() { curl -fsS --max-time 15 "$1"; }
empreinte() { shasum -a 256 2>/dev/null | cut -d' ' -f1 || sha256sum | cut -d' ' -f1; }

# juger <adresse relative> <empreinte attendue> — un écart par ligne, code 0/1/2.
juger() {
  local chemin="$1" attendu="$2" i corps lu=0 servi=""
  for i in $(seq 1 "$ESSAIS"); do
    # pipefail (en tête) : une lecture en échec fait échouer l'affectation.
    if corps=$(lire_url "$BASE$chemin" | empreinte); then
      lu=1; servi="$corps"
      [ "$servi" = "$attendu" ] && { echo "  ok      public /$chemin"; return 0; }
    fi
    [ "$i" -lt "$ESSAIS" ] && sleep "$ATTENTE"
  done
  if [ "$lu" = 0 ]; then echo "  INCONNU public /$chemin (injoignable à chacun des $ESSAIS essais)"; return 2; fi
  echo "  ÉCART   public /$chemin (le public reçoit autre chose que le commit, après $ESSAIS essais)"
  return 1
}

# verifier <commit> — l'accueil et sa feuille commune ; le pire des deux codes.
verifier() {
  local commit="$1" css code=0 r
  local accueil; accueil=$(git show "$commit:site/index.html" 2>/dev/null) || { echo "  INCONNU public (site/index.html illisible dans $commit)"; return 2; }
  css=$(grep -o 'commun\.css?v=[0-9a-f]*' <<<"$accueil" | head -1)
  [ -n "$css" ] || { echo "  INCONNU public (l'accueil n'appelle pas commun.css?v=)"; return 2; }
  # L'empreinte du fichier lui-même : $(…) retirerait son saut de ligne final.
  juger "" "$(git show "$commit:site/index.html" | empreinte)"; r=$?; [ "$r" -gt "$code" ] && code=$r
  juger "$css" "$(git show "$commit:site/commun.css" | empreinte)"; r=$?; [ "$r" -gt "$code" ] && code=$r
  return "$code"
}

# --selftest : une « périphérie » en mémoire. Chaque adresse répond une suite de corps,
# un par essai ; « - » simule une adresse injoignable.
selftest() {
  local echecs=0 t; t=$(mktemp -d)
  ESSAIS=3; ATTENTE=0; BASE="https://site.example/"
  lire_url() {
    local f="$t/${1#"$BASE"}.reponses" n
    n=$(cat "$f.n" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$f.n"
    local r; r=$(sed -n "${n}p" "$f"); [ -z "$r" ] && r=$(tail -1 "$f")
    [ "$r" = "-" ] && return 22
    printf '%s' "$r"
  }
  cas() { # <libellé> <code attendu> <réponses, séparées par des espaces>
    local libelle="$1" attendu="$2"; shift 2
    rm -f "$t"/*.reponses "$t"/*.n; printf '%s\n' "$@" > "$t/page.reponses"
    juger page "$(printf 'neuf' | empreinte)" >/dev/null; local obtenu=$?
    if [ "$obtenu" = "$attendu" ]; then echo "  ok      $libelle → $obtenu"
    else echo "  ÉCHEC   $libelle → $obtenu, attendu $attendu"; echecs=$((echecs + 1)); fi
  }
  cas "périphérie à jour" 0 neuf
  cas "périphérie en retard, puis à jour" 0 ancien ancien neuf
  cas "périphérie en retard tout du long" 1 ancien ancien ancien
  cas "injoignable, puis à jour" 0 - neuf
  cas "injoignable à chaque essai" 2 - - -
  cas "injoignable puis en retard" 1 - ancien ancien
  # De bout en bout sur un vrai commit : l'empreinte attendue est celle du fichier, saut
  # de ligne final compris (une version tronquée ne serait jamais égale au public).
  local c; c=$(git rev-parse HEAD 2>/dev/null)
  if [ -n "$c" ]; then
    lire_url() { local f="${1#"$BASE"}"; f="${f%%\?*}"; git show "$c:site/${f:-index.html}"; }
    if verifier "$c" >/dev/null; then echo "  ok      commit $c servi tel quel → 0"
    else echo "  ÉCHEC   commit servi tel quel → non nul"; echecs=$((echecs + 1)); fi
  fi
  rm -rf "$t"
  [ "$echecs" -eq 0 ] && echo "verifier-public --selftest : OK" || { echo "verifier-public --selftest : $echecs ÉCHEC(S)"; return 1; }
}

case "${1:-}" in
  --selftest) selftest; exit $? ;;
  "") echo "Usage : bash scripts/verifier-public.sh COMMIT | --selftest" >&2; exit 2 ;;
  *) verifier "$1"; exit $? ;;
esac
