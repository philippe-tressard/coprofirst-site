#!/bin/bash
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# proposer-version.sh — la PR « version » : la dernière release de CoproFirst, écrite
# dans l'accueil, proposée à la fusion (coprofirst-site#51).
#
# CoproFirst publie une dizaine de releases par jour : la mettre à jour à la main ne
# tient pas le rythme. Lancé chaque heure par .github/workflows/version-produit.yml :
#   1. part de main, lance `version-produit.py --ecrire` (page ET lastmod), puis
#      `contenu-accueil.py --ecrire` : contenu.json est la projection de la page, et
#      la CI refuse une page qu'il ne rend plus (coprofirst-site#42) ;
#   2. rien n'a changé → rien ; sinon un commit sur la branche du robot, BRANCHE ;
#   3. la branche porte déjà exactement ce contenu → rien (pas une CI par heure pour
#      rien) ; sinon elle est reconstruite depuis main et poussée (--force-with-lease :
#      le robot seul y écrit, et une branche refaite reste à jour avec main, ce
#      qu'exige la protection) ;
#   4. la PR est ouverte, ou son titre suit la nouvelle version ;
#   5. la CI est relancée sur la branche : un push du GITHUB_TOKEN ne déclenche
#      aucun workflow, et le check requis `depot` ne viendrait jamais.
# La fusion reste celle de Philippe (champ `fusion` de projets.json), le déploiement
# aussi : la PR ouverte EST le signal du retard.
#
# Usage : bash scripts/proposer-version.sh           (en CI : GH_TOKEN, git configuré)
#         bash scripts/proposer-version.sh --selftest (dépôt jetable, gh simulé)
set -euo pipefail
BRANCHE="${BRANCHE:-auto/version-produit}"
RACINE=$(cd "$(dirname "$0")/.." && pwd)

proposer() {
  cd "$RACINE"
  git fetch -q origin main
  git switch -q -C "$BRANCHE" origin/main
  python3 scripts/version-produit.py --ecrire
  python3 scripts/contenu-accueil.py --ecrire
  if git diff --quiet; then
    echo "proposer-version : l'accueil affiche déjà la dernière release — rien à proposer"
    return 0
  fi
  local version
  version=$(sed -n 's/.*<b>Version \([0-9.]*\)<\/b>.*/\1/p' site/index.html | head -1)
  [ -n "$version" ] || { echo "INCONNU : version illisible dans site/index.html"; return 2; }
  git commit -q -am "chore(version) : version affichée $version, la dernière release de CoproFirst" \
    -m "Écrit par scripts/proposer-version.sh (workflow version-produit.yml, coprofirst-site#51)."
  if git fetch -q origin "$BRANCHE" 2>/dev/null \
     && [ "$(git rev-parse 'HEAD^{tree}')" = "$(git rev-parse 'FETCH_HEAD^{tree}')" ] \
     && git merge-base --is-ancestor origin/main FETCH_HEAD; then
    echo "proposer-version : la PR porte déjà la version $version — rien à pousser"
    return 0
  fi
  git push -q --force-with-lease origin "HEAD:refs/heads/$BRANCHE"
  local titre="chore(version) : version affichée $version, la dernière release de CoproFirst"
  if [ -n "$(gh pr list --head "$BRANCHE" --state open --json number --jq '.[].number')" ]; then
    gh pr edit "$BRANCHE" --title "$titre" >/dev/null
  else
    gh pr create --base main --head "$BRANCHE" --title "$titre" --body "La dernière release de CoproFirst, écrite par \`version-produit.py --ecrire\` (page et \`lastmod\`). Branche refaite depuis \`main\` à chaque nouvelle release : la fusionner, puis \`bash deploiement/deployer.sh\`.

Ouverte par \`.github/workflows/version-produit.yml\` (coprofirst-site#51)." >/dev/null
  fi
  gh workflow run ci.yml --ref "$BRANCHE"
  gh workflow run comptes-demo.yml --ref "$BRANCHE"
  echo "proposer-version : PR « version $version » à jour sur $BRANCHE"
}

# Le selftest rejoue le script dans un dépôt jetable : un « origin » nu, un gh qui
# note ses appels, et une source de release locale à la place de l'API.
selftest() {
  local t echecs=0
  t=$(mktemp -d)
  trap 'rm -rf "$t"' RETURN
  git init -q --bare "$t/origin.git"
  git clone -q "$t/origin.git" "$t/clone" 2>/dev/null
  mkdir -p "$t/clone/scripts" "$t/clone/site" "$t/bin"
  cp "$RACINE/scripts/version-produit.py" "$RACINE/scripts/lecture_distante.py" "$RACINE/scripts/proposer-version.sh" \
    "$RACINE/scripts/contenu-accueil.py" "$t/clone/scripts/"
  printf '<section data-contenu="heros"><h1>Accueil</h1><ul><li data-version-produit><a href="x"><b>Version 1.0.0</b> · 01/01/2026</a></li></ul></section>\n' > "$t/clone/site/index.html"
  python3 "$t/clone/scripts/contenu-accueil.py" --ecrire >/dev/null
  printf '<urlset><url><loc>https://coprofirst.fr/</loc><lastmod>2026-01-01</lastmod></url></urlset>\n' > "$t/clone/site/sitemap.xml"
  printf '#!/bin/bash\necho "gh $*" >> "%s/appels"\n[ "$1 $2" = "pr list" ] && [ -f "%s/pr" ] && echo 7\n[ "$1 $2" = "pr create" ] && touch "%s/pr"\nexit 0\n' "$t" "$t" "$t" > "$t/bin/gh"
  chmod +x "$t/bin/gh"
  # version-produit.py lit la release dans --source : le selftest l'impose par un
  # python3 qui l'ajoute, le reste du script étant celui qui tourne en CI.
  printf '#!/bin/bash\nif [ "${1:-}" = scripts/version-produit.py ]; then shift; exec %s scripts/version-produit.py --source "%s/release.json" "$@"; fi\nexec %s "$@"\n' \
    "$(command -v python3)" "$t" "$(command -v python3)" > "$t/bin/python3"
  chmod +x "$t/bin/python3"
  (
    cd "$t/clone" && git -c user.name=t -c user.email=t@t commit -q --allow-empty -m init \
      && git add -A && git -c user.name=t -c user.email=t@t commit -q -m site && git push -q origin HEAD:main 2>/dev/null
  )
  passe() { # <libellé> <tag> <appels gh exigés, séparés par ;> <absents (motif) ou ->
    printf '{"tag_name": "%s", "published_at": "2026-11-05T17:01:00Z"}' "$2" > "$t/release.json"
    : > "$t/appels"
    local sortie
    sortie=$(cd "$t/clone" && PATH="$t/bin:$PATH" GIT_AUTHOR_NAME=r GIT_AUTHOR_EMAIL=r@r GIT_COMMITTER_NAME=r GIT_COMMITTER_EMAIL=r@r \
      bash scripts/proposer-version.sh 2>&1) || { echo "  ÉCHEC   $1 : sortie non nulle — $sortie"; echecs=$((echecs + 1)); return; }
    local exige
    while IFS= read -r -d ';' exige; do
      [ -z "$exige" ] || grep -qF "$exige" "$t/appels" || {
        echo "  ÉCHEC   $1 : appels gh « $(tr '\n' '|' < "$t/appels") », manque « $exige »"; echecs=$((echecs + 1)); return; }
    done <<< "$3;"
    if [ "$4" != "-" ] && grep -qE "$4" "$t/appels"; then
      echo "  ÉCHEC   $1 : appel gh inattendu /$4/"; echecs=$((echecs + 1)); return
    fi
    echo "  ok      $1"
  }
  passe "nouvelle release → PR ouverte, CI relancée" v1.1.0 "gh pr create;gh workflow run ci.yml;gh workflow run comptes-demo.yml" "pr edit"
  passe "même release → rien" v1.1.0 "" "pr |workflow"
  passe "release suivante → PR mise à jour, CI relancée" v1.2.0 "gh pr edit;gh workflow run ci.yml" "pr create"
  local contenu
  contenu=$(git -C "$t/origin.git" show "auto/version-produit:site/index.html")
  case "$contenu" in *"Version 1.2.0"*) echo "  ok      la branche porte 1.2.0" ;;
    *) echo "  ÉCHEC   la branche ne porte pas 1.2.0"; echecs=$((echecs + 1)) ;; esac
  case "$(git -C "$t/origin.git" show "auto/version-produit:site/contenu.json")" in *"Version 1.2.0"*)
    echo "  ok      contenu.json suit la page" ;;
    *) echo "  ÉCHEC   contenu.json ne porte pas 1.2.0 : la CI de la PR refuserait la page"; echecs=$((echecs + 1)) ;; esac
  case "$(git -C "$t/origin.git" show "auto/version-produit:site/sitemap.xml")" in *"<lastmod>2026-01-01"*)
    echo "  ÉCHEC   lastmod de l'accueil pas avancé"; echecs=$((echecs + 1)) ;; *) echo "  ok      lastmod avancé" ;; esac
  [ "$echecs" -eq 0 ] && echo "selftest : OK" || { echo "selftest : $echecs ÉCHEC(S)"; return 1; }
}

if [ "${1:-}" = "--selftest" ]; then selftest; exit $?; fi
proposer
