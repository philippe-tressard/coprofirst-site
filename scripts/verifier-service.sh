#!/bin/bash
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# verifier-service.sh — l'image du site SE COMPORTE-T-ELLE comme le Caddyfile le
# promet ? Construit l'image (deploiement/Dockerfile), la démarre, et l'interroge :
#   - page et 404 : code, en-têtes de sécurité, Cache-Control no-transform, pas de
#     Server, et le corps octet pour octet celui du dépôt (index.html, 404.html) ;
#   - compression : gzip quand le navigateur l'accepte — page,
#     feuille de style, 404 —, jamais sur une image JPEG, et rien sans
#     Accept-Encoding (c'est ce que reçoit deployer.sh --verifier) ;
#   - www.coprofirst.fr redirige vers coprofirst.fr.
# Un Caddyfile peut être valide (caddy validate) et ne pas faire ce qu'on croit :
# l'ordre de `encode` et de `header` en est l'exemple — encode s'abstient devant
# no-transform si l'en-tête est posé trop tôt. Seul le comportement le dit.
#
# En CI seulement : le poste n'a pas Docker. Sortie 0 conforme, 1 écart,
# 2 INCONNU (Docker absent, conteneur muet).
#
#   bash scripts/verifier-service.sh
set -uo pipefail

racine=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "INCONNU : pas un dépôt git"; exit 2; }
cd "$racine" || exit 2
command -v docker >/dev/null 2>&1 || { echo "INCONNU : Docker absent — rien n'a été vérifié"; exit 2; }

PORT=18080
IMAGE=coprofirst-site:verification
t=$(mktemp -d)
conteneur=""
nettoyer() { [ -n "$conteneur" ] && docker rm -f "$conteneur" >/dev/null 2>&1; rm -rf "$t"; }
trap nettoyer EXIT

docker build -q -f deploiement/Dockerfile -t "$IMAGE" . >/dev/null \
  || { echo "ÉCART : l'image ne se construit pas (Caddyfile invalide ?)"; exit 1; }
conteneur=$(docker run -d -p "127.0.0.1:$PORT:8080" "$IMAGE") || { echo "INCONNU : le conteneur ne démarre pas"; exit 2; }
for _ in $(seq 1 40); do curl -s -o /dev/null "http://127.0.0.1:$PORT/" && break; sleep 0.25; done
curl -s -o /dev/null "http://127.0.0.1:$PORT/" || { echo "INCONNU : le conteneur ne répond pas"; docker logs "$conteneur" | tail -5; exit 2; }

ecarts=0
ecart() { echo "  ÉCART   $1"; ecarts=$((ecarts + 1)); }

# demander <nom> <chemin> [options curl…] — en-têtes dans $t/<nom>.h, corps dans $t/<nom>.c
demander() {
  local nom=$1 chemin=$2; shift 2
  curl -s -D "$t/$nom.h" -o "$t/$nom.c" "$@" "http://127.0.0.1:$PORT$chemin"
  tr -d '\r' < "$t/$nom.h" > "$t/$nom.hh"
}
code() { head -1 "$t/$1.hh" | cut -d' ' -f2; }
entete() { grep -i "^$2:" "$t/$1.hh" | head -1 | cut -d' ' -f2-; }
empreinte() { sha256sum < "$1" | cut -d' ' -f1; }

# securite <nom> — les en-têtes que toute réponse doit porter
securite() {
  local nom=$1 e
  for e in Content-Security-Policy Strict-Transport-Security X-Content-Type-Options Referrer-Policy Permissions-Policy; do
    [ -n "$(entete "$nom" "$e")" ] || ecart "$nom : en-tête $e absent"
  done
  case "$(entete "$nom" Cache-Control)" in *no-transform*) ;; *) ecart "$nom : Cache-Control sans no-transform" ;; esac
  [ -z "$(entete "$nom" Server)" ] || ecart "$nom : en-tête Server présent"
}

# corps <nom> <fichier du dépôt> [gzip] — le corps (décompressé si gzip) est le fichier
corps() {
  local nom=$1 attendu=$2 recu="$t/$1.c"
  if [ "${3:-}" = gzip ]; then gzip -dc < "$t/$1.c" > "$t/$1.d" 2>/dev/null || { ecart "$nom : corps gzip illisible"; return; }; recu="$t/$1.d"; fi
  [ "$(empreinte "$recu")" = "$(empreinte "$attendu")" ] || ecart "$nom : corps différent de $attendu"
}

# encodage <nom> <attendu : gzip ou vide>
encodage() {
  local recu; recu=$(entete "$1" Content-Encoding)
  [ "$recu" = "$2" ] || ecart "$1 : Content-Encoding « ${recu:-aucun} », attendu « ${2:-aucun} »"
}

css=$(grep -o 'commun\.css?v=[0-9a-f]*' site/index.html | head -1)
jpg=$(grep -o 'captures/[a-z-]*\.jpg?v=[0-9a-f]*' site/index.html | head -1)

demander page /
[ "$(code page)" = 200 ] || ecart "page : code $(code page), attendu 200"
securite page; encodage page ""; corps page site/index.html

demander page-gzip / -H "Accept-Encoding: gzip"
securite page-gzip; encodage page-gzip gzip; corps page-gzip site/index.html gzip

demander css-gzip "/$css" -H "Accept-Encoding: gzip"
encodage css-gzip gzip; corps css-gzip site/commun.css gzip

demander image-gzip "/$jpg" -H "Accept-Encoding: gzip"
encodage image-gzip ""; corps image-gzip "site/${jpg%%\?*}"

demander introuvable /nexistepas
[ "$(code introuvable)" = 404 ] || ecart "introuvable : code $(code introuvable), attendu 404"
securite introuvable; encodage introuvable ""; corps introuvable site/404.html

demander introuvable-gzip /a/b/x -H "Accept-Encoding: gzip"
[ "$(code introuvable-gzip)" = 404 ] || ecart "introuvable-gzip : code $(code introuvable-gzip), attendu 404"
securite introuvable-gzip; encodage introuvable-gzip gzip; corps introuvable-gzip site/404.html gzip

demander www / -H "Host: www.coprofirst.fr"
case "$(code www)" in 301|308) ;; *) ecart "www : code $(code www), attendu une redirection permanente" ;; esac
[ "$(entete www Location)" = "https://coprofirst.fr/" ] || ecart "www : Location « $(entete www Location) »"

if [ "$ecarts" -gt 0 ]; then echo "verifier-service : $ecarts écart(s)"; exit 1; fi
echo "verifier-service : OK (page, feuille de style, image, 404 profonde, www ; avec et sans compression)"
