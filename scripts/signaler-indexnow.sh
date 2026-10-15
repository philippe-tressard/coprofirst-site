#!/bin/bash
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# signaler-indexnow.sh — annonce aux moteurs qui suivent IndexNow (Bing, Yandex,
# Seznam, Naver…, qui se les partagent) que les pages du sitemap ont changé, pour
# qu'ils les relisent sans attendre leur passage habituel. Google n'y participe pas.
#
#   bash scripts/signaler-indexnow.sh            après un déploiement
#   bash scripts/signaler-indexnow.sh --essai    affiche la requête, n'envoie rien
#
# ⚠️ Envoie la liste des adresses du site à api.indexnow.org : un geste vers un
# tiers, à lancer à la main, jamais depuis la CI ni depuis deployer.sh.
# La clé n'est pas un secret : le protocole exige qu'elle soit publiée, dans le
# fichier site/<clé>.txt, que les moteurs lisent pour prouver la propriété du site.
set -euo pipefail

racine=$(git rev-parse --show-toplevel)
cd "$racine"

cles=(site/*.txt)
cle=""
for f in "${cles[@]}"; do
  nom=$(basename "$f" .txt)
  [[ "$nom" =~ ^[0-9a-f]{32}$ ]] && [ "$(cat "$f")" = "$nom" ] && { cle="$nom"; break; }
done
[ -n "$cle" ] || { echo "INCONNU : aucune clé IndexNow (site/<32 hex>.txt) dans le dépôt" >&2; exit 2; }

# Les adresses : celles du sitemap, qui est vérifié contre les pages du site
mapfile -t adresses < <(grep -o '<loc>[^<]*</loc>' site/sitemap.xml | sed 's#</\?loc>##g')
[ "${#adresses[@]}" -gt 0 ] || { echo "INCONNU : sitemap.xml ne liste aucune adresse" >&2; exit 2; }

liste=$(printf '"%s",' "${adresses[@]}")
corps="{\"host\":\"coprofirst.fr\",\"key\":\"$cle\",\"keyLocation\":\"https://coprofirst.fr/$cle.txt\",\"urlList\":[${liste%,}]}"

if [ "${1:-}" = "--essai" ]; then echo "$corps"; exit 0; fi

# La clé doit être EN LIGNE avant l'envoi, sinon les moteurs rejettent la demande
curl -fsS "https://coprofirst.fr/$cle.txt" | grep -qx "$cle" \
  || { echo "REFUS : https://coprofirst.fr/$cle.txt ne sert pas la clé — déployer d'abord" >&2; exit 1; }

code=$(curl -sS -o /dev/null -w '%{http_code}' -X POST https://api.indexnow.org/indexnow \
  -H 'Content-Type: application/json; charset=utf-8' --data "$corps")
case "$code" in
  200|202) echo "IndexNow : ${#adresses[@]} adresses annoncées (HTTP $code)" ;;
  *) echo "ÉCHEC : IndexNow a répondu HTTP $code" >&2; exit 1 ;;
esac
