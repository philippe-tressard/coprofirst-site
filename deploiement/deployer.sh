#!/bin/bash
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# deployer.sh — publie le site du commit courant sur l'instance Oracle, puis
# vérifie que chaque fichier servi est octet pour octet celui du dépôt.
#
#   bash deploiement/deployer.sh            déployer HEAD (déjà poussé sur origin)
#   bash deploiement/deployer.sh --verifier vérifier seulement, sans déployer
#
# Ne déploie que ce qui est committé ET poussé : la page en ligne est toujours
# une version que l'on retrouve sur GitHub. Accès : la clé dédiée à l'instance,
# et elle seule (BatchMode, IdentitiesOnly) — jamais d'autre clé ni identifiant.
set -euo pipefail

HOTE=ubuntu@158.178.197.236
CLE="$HOME/.ssh/id_ed25519_coprofirst_demo"
DISTANT='~/coprofirst-site'
SSH=(ssh -i "$CLE" -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=15 "$HOTE")

racine=$(git rev-parse --show-toplevel)
cd "$racine"
commit=$(git rev-parse HEAD)

deployer() {
  if [ -n "$(git status --porcelain -- site deploiement)" ]; then
    echo "REFUS : site/ ou deploiement/ ont des modifications non committées." >&2; exit 1
  fi
  git fetch -q origin
  if ! git merge-base --is-ancestor "$commit" origin/main; then
    echo "REFUS : $commit n'est pas sur origin/main — pousser d'abord." >&2; exit 1
  fi
  echo "Déploiement de ${commit:0:7} sur $HOTE…"
  # Arborescence remplacée en bloc, puis image reconstruite : rien ne survit d'un
  # déploiement précédent, rien ne se modifie à la main sur le serveur.
  git archive --format=tar "$commit" site deploiement | "${SSH[@]}" "
    set -e
    rm -rf $DISTANT.nouveau && mkdir -p $DISTANT.nouveau
    tar -x -C $DISTANT.nouveau
    echo $commit > $DISTANT.nouveau/COMMIT
    rm -rf $DISTANT && mv $DISTANT.nouveau $DISTANT
    cd $DISTANT && docker compose -f deploiement/compose.yaml up -d --build --remove-orphans
    docker image prune -f >/dev/null"
}

# verifier — compare l'empreinte de chaque fichier de site/ (dans le commit) à celle
# que le conteneur sert. Un fichier injoignable compte comme écart : un contrôle
# qui n'a pas pu lire ne dit pas OK.
verifier() {
  local attendu servi ecarts=0 n=0
  # Le commit réellement en ligne, pas celui du poste : --verifier juge le serveur.
  commit=$("${SSH[@]}" "cat $DISTANT/COMMIT" 2>/dev/null) || { echo "INCONNU : aucun déploiement trouvé sur $HOTE"; return 2; }
  git cat-file -e "$commit^{commit}" 2>/dev/null || { echo "INCONNU : commit en ligne $commit absent du clone (git fetch ?)"; return 2; }
  echo "Vérification du commit en ligne ${commit:0:7} :"
  attendu=$(git ls-tree -r --name-only "$commit" -- site | while read -r f; do
    printf '%s %s\n' "$(git show "$commit:$f" | sha256sum | cut -d' ' -f1)" "${f#site/}"
  done)
  [ -n "$attendu" ] || { echo "INCONNU : aucun fichier sous site/ dans $commit"; return 2; }
  servi=$(echo "$attendu" | cut -d' ' -f2 | "${SSH[@]}" '
    set -o pipefail
    for i in $(seq 1 20); do curl -fsS -o /dev/null http://127.0.0.1:8080/ && break; sleep 1; done
    while read -r f; do
      e=$(curl -fsS "http://127.0.0.1:8080/$f" | sha256sum | cut -d" " -f1) || e=injoignable
      echo "$e $f"
    done')
  while read -r empreinte f; do
    n=$((n + 1))
    if grep -qxF "$empreinte $f" <<<"$servi"; then echo "  ok      $f"
    else echo "  ÉCART   $f"; ecarts=$((ecarts + 1)); fi
  done <<<"$attendu"
  # La racine sert bien index.html
  if [ "$("${SSH[@]}" 'curl -fsS http://127.0.0.1:8080/ | sha256sum | cut -d" " -f1')" = \
       "$(git show "$commit:site/index.html" | sha256sum | cut -d' ' -f1)" ]; then echo "  ok      / → index.html"
  else echo "  ÉCART   / ne sert pas index.html"; ecarts=$((ecarts + 1)); fi
  if [ "$ecarts" -gt 0 ]; then echo "verifier : $ecarts écart(s) sur $n fichiers"; return 1; fi
  echo "verifier : OK — $n fichiers servis identiques au commit ${commit:0:7}"
}

[ "${1:-}" = "--verifier" ] || deployer
verifier
