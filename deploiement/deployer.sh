#!/bin/bash
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# deployer.sh — publie le site du commit courant sur l'instance Oracle, puis
# vérifie que chaque fichier servi est octet pour octet celui du dépôt.
#
#   bash deploiement/deployer.sh               déployer HEAD (déjà poussé) et site/avis.json
#   bash deploiement/deployer.sh --garder-avis déployer HEAD en gardant les avis déjà en ligne
#   bash deploiement/deployer.sh --verifier    vérifier seulement, sans déployer
#
# Ne déploie que ce qui est committé ET poussé : la page en ligne est toujours
# une version que l'on retrouve sur GitHub. Une exception, voulue : site/avis.json,
# l'export des avis de l'application, n'est PAS versionné (un accord retiré ne doit
# pas survivre dans l'historique public — coprofirst-site#6). Il part du poste,
# après scripts/verifier-avis.py ; sans lui, le déploiement refuse, sauf
# --garder-avis. Accès : la clé dédiée à l'instance, et elle seule (BatchMode,
# IdentitiesOnly) — jamais d'autre clé ni identifiant.
set -euo pipefail

HOTE=ubuntu@158.178.197.236
CLE="$HOME/.ssh/id_ed25519_coprofirst_demo"
DISTANT='~/coprofirst-site'
SSH=(ssh -i "$CLE" -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=15 "$HOTE")

racine=$(git rev-parse --show-toplevel)
cd "$racine"
commit=$(git rev-parse HEAD)
AVIS=site/avis.json

deployer() {
  if [ -n "$(git status --porcelain -- site deploiement)" ]; then
    echo "REFUS : site/ ou deploiement/ ont des modifications non committées." >&2; exit 1
  fi
  git fetch -q origin
  if ! git merge-base --is-ancestor "$commit" origin/main; then
    echo "REFUS : $commit n'est pas sur origin/main — pousser d'abord." >&2; exit 1
  fi
  local garder="${1:-}"
  if [ -z "$garder" ]; then
    if [ ! -f "$AVIS" ]; then
      echo "REFUS : $AVIS absent. Dans l'application : Communauté → ⭐ Avis → « Exporter les avis" >&2
      echo "  retenus pour coprofirst.fr », puis copier avis-coprofirst-AAAA-MM-JJ.json en $AVIS." >&2
      echo "  Pour déployer sans toucher aux avis en ligne : --garder-avis." >&2
      exit 1
    fi
    python3 scripts/verifier-avis.py --fichier "$AVIS" || { echo "REFUS : $AVIS non conforme (ci-dessus)." >&2; exit 1; }
    if grep -q '"avis": *\[ *\]' "$AVIS"; then echo "Attention : aucun avis dans $AVIS — la section des avis sera masquée."; fi
  fi
  echo "Déploiement de ${commit:0:7} sur $HOTE…"
  # Le commit, plus l'export des avis (non versionné) ajouté à l'archive.
  archive=$(mktemp)
  trap 'rm -f "$archive"' EXIT
  git archive --format=tar -o "$archive" "$commit" site deploiement
  if [ -z "$garder" ]; then tar --append -f "$archive" "$AVIS"; fi
  # Arborescence remplacée en bloc, puis image reconstruite : rien ne survit d'un
  # déploiement précédent (sauf avis.json avec --garder-avis), rien ne se modifie à
  # la main sur le serveur.
  "${SSH[@]}" "
    set -e
    rm -rf $DISTANT.nouveau && mkdir -p $DISTANT.nouveau
    tar -x -C $DISTANT.nouveau
    if [ -n '$garder' ]; then
      [ -f $DISTANT/$AVIS ] && cp $DISTANT/$AVIS $DISTANT.nouveau/$AVIS || echo 'Aucun avis en ligne à garder.'
    fi
    echo $commit > $DISTANT.nouveau/COMMIT
    rm -rf $DISTANT && mv $DISTANT.nouveau $DISTANT
    cd $DISTANT && docker compose -f deploiement/compose.yaml up -d --build --remove-orphans
    docker image prune -f >/dev/null" < "$archive"
}

# verifier_avis — avis.json n'est pas dans le commit : on compare ce que le conteneur
# sert à l'export du poste (ou, à défaut, à celui déposé sur le serveur), et on le
# soumet à scripts/verifier-avis.py. Écrit « ok »/« ÉCART »/« INCONNU » ; rend 0, 1 ou 2.
verifier_avis() {
  local servi attendu source t r=0
  t=$(mktemp)
  if ! "${SSH[@]}" "curl -fsS http://127.0.0.1:8080/avis.json" > "$t" 2>/dev/null; then
    if "${SSH[@]}" "test -f $DISTANT/$AVIS"; then echo "  ÉCART   avis.json (déposé mais pas servi)"; rm -f "$t"; return 1; fi
    echo "  ok      avis.json absent du serveur (section des avis masquée)"; rm -f "$t"; return 0
  fi
  servi=$(sha256sum < "$t" | cut -d' ' -f1)
  if [ -f "$AVIS" ]; then source="l'export du poste"; attendu=$(sha256sum < "$AVIS" | cut -d' ' -f1)
  else source="celui déposé sur le serveur"; attendu=$("${SSH[@]}" "sha256sum < $DISTANT/$AVIS" 2>/dev/null | cut -d' ' -f1) || attendu=""; fi
  if [ -z "$attendu" ]; then echo "  INCONNU avis.json (aucune référence à comparer)"; r=2
  elif [ "$servi" = "$attendu" ]; then echo "  ok      avis.json (identique à $source)"
  else echo "  ÉCART   avis.json (différent de $source)"; r=1; fi
  python3 scripts/verifier-avis.py --fichier "$t" >/dev/null || { echo "  ÉCART   avis.json servi non conforme (scripts/verifier-avis.py)"; r=1; }
  rm -f "$t"
  return $r
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
  local etat_avis=0
  verifier_avis || etat_avis=$?
  [ "$etat_avis" -eq 1 ] && ecarts=$((ecarts + 1))
  if [ "$ecarts" -gt 0 ]; then echo "verifier : $ecarts écart(s) sur $n fichiers et avis.json"; return 1; fi
  if [ "$etat_avis" -eq 2 ]; then echo "verifier : INCONNU — $n fichiers identiques au commit ${commit:0:7}, avis.json non vérifié"; return 2; fi
  echo "verifier : OK — $n fichiers servis identiques au commit ${commit:0:7}, et avis.json"
}

case "${1:-}" in
  --verifier) ;;
  --garder-avis) deployer garder ;;
  "") deployer ;;
  *) echo "Usage : bash deploiement/deployer.sh [--garder-avis | --verifier]" >&2; exit 1 ;;
esac
verifier
