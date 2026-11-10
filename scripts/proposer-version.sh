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
#      aucun workflow, et le check requis `depot` ne viendrait jamais. Une PR déjà
#      à jour mais SANS check (relance perdue) reçoit la sienne au passage suivant :
#      la PR du robot ne reste pas bloquée (coprofirst-site#63).
# Tout appel à GitHub est tenté trois fois (essayer) : un 500, un 504 ou un push
# refusé passagers ne doivent pas ouvrir un ticket « CI rouge » ; l'échec qui dure,
# lui, fait échouer le passage et le signale.
# La fusion reste celle de Philippe (champ `fusion` de projets.json), le déploiement
# aussi : la PR ouverte EST le signal du retard.
#
# Usage : bash scripts/proposer-version.sh           (en CI : GH_TOKEN, git configuré)
#         bash scripts/proposer-version.sh --selftest (dépôt jetable, gh simulé)
set -euo pipefail
BRANCHE="${BRANCHE:-auto/version-produit}"
RACINE=$(cd "$(dirname "$0")/.." && pwd)

# essayer <commande…> : jusqu'à trois essais, avec une attente entre eux
# (ESSAI_ATTENTES, en secondes ; le selftest la met à zéro). Rend l'échec du dernier.
essayer() {
  local n=0 attentes
  attentes=(${ESSAI_ATTENTES:-5 15})
  until "$@"; do
    if [ "$n" -ge "${#attentes[@]}" ]; then
      echo "proposer-version : échec après $((n + 1)) essais : $*" >&2
      return 1
    fi
    echo "proposer-version : essai $((n + 1)) raté (${1} ${2:-}…), nouvel essai dans ${attentes[$n]} s" >&2
    sleep "${attentes[$n]}"
    n=$((n + 1))
  done
}

lancer_ci() {
  essayer gh workflow run ci.yml --ref "$BRANCHE"
  essayer gh workflow run comptes-demo.yml --ref "$BRANCHE"
}

proposer() {
  cd "$RACINE"
  essayer git fetch -q origin main
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
  # « Rien à faire » exige les deux : la branche porte ce contenu ET la PR est
  # ouverte. Une branche poussée sans PR (création refusée, PR fermée) se reprend.
  local pr deja=non
  pr=$(essayer gh pr list --head "$BRANCHE" --state open --json number --jq '.[].number')
  if git fetch -q origin "$BRANCHE" 2>/dev/null \
     && [ "$(git rev-parse 'HEAD^{tree}')" = "$(git rev-parse 'FETCH_HEAD^{tree}')" ] \
     && git merge-base --is-ancestor origin/main FETCH_HEAD; then
    deja=oui
  fi
  if [ "$deja" = oui ] && [ -n "$pr" ]; then
    local checks
    checks=$(essayer gh pr view "$BRANCHE" --json statusCheckRollup --jq '.statusCheckRollup | length')
    if [ "${checks:-0}" = 0 ]; then
      echo "proposer-version : la PR porte déjà la version $version mais n'a aucun check — CI relancée"
      lancer_ci
    else
      echo "proposer-version : la PR porte déjà la version $version — rien à pousser"
    fi
    return 0
  fi
  [ "$deja" = oui ] || essayer git push -q --force-with-lease origin "HEAD:refs/heads/$BRANCHE"
  local titre="chore(version) : version affichée $version, la dernière release de CoproFirst"
  if [ -n "$pr" ]; then
    essayer gh pr edit "$BRANCHE" --title "$titre" >/dev/null
  else
    essayer gh pr create --base main --head "$BRANCHE" --title "$titre" --body "La dernière release de CoproFirst, écrite par \`version-produit.py --ecrire\` (page et \`lastmod\`). Branche refaite depuis \`main\` à chaque nouvelle release : la fusionner, puis \`bash deploiement/deployer.sh\`.

Ouverte par \`.github/workflows/version-produit.yml\` (coprofirst-site#51)." >/dev/null
  fi
  lancer_ci
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
  # Une page qui tient le contrat de l'app iOS (CONTRAT_APP de contenu-accueil.py,
  # coprofirst-site#66) : sans elle, `contenu-accueil.py --ecrire` refuse d'écrire.
  {
    printf '<section data-contenu="heros"><h1>Accueil</h1><p>Texte.</p><ul><li data-version-produit><a href="x"><b>Version 1.0.0</b> · 01/01/2026</a></li></ul></section>\n'
    printf '<section data-contenu="fonctions"><h2>Fonctions</h2><p>Texte.</p>'
    for id in demande documents point-syndic badges carnet communaute; do
      printf '<article data-contenu="%s"><h3>%s</h3><p>Texte.</p></article>' "$id" "$id"
    done
    printf '</section>\n<section data-contenu="demo"><h2>Démo</h2><p>Chapeau.</p><p>Avertissement.</p>'
    for id in conseil-syndical coproprietaire locataire; do
      printf '<article data-contenu="%s"><h3>%s</h3><p>Texte.</p></article>' "$id" "$id"
    done
    printf '</section>\n'
  } > "$t/clone/site/index.html"
  python3 "$t/clone/scripts/contenu-accueil.py" --ecrire >/dev/null
  printf '<urlset><url><loc>https://coprofirst.fr/</loc><lastmod>2026-01-01</lastmod></url></urlset>\n' > "$t/clone/site/sitemap.xml"
  # Le gh simulé note ses appels (MOCK_DIR/appels) et obéit à des drapeaux posés par
  # les cas : pr (une PR existe), checks (nombre de checks), echec_une_fois (la
  # prochaine « workflow run » échoue), echec_toujours (« pr create » échoue).
  cat > "$t/bin/gh" <<'MOCK'
#!/bin/bash
echo "gh $*" >> "$MOCK_DIR/appels"
if [ "$1 $2" = "workflow run" ] && [ -f "$MOCK_DIR/echec_une_fois" ]; then rm -f "$MOCK_DIR/echec_une_fois"; exit 1; fi
if [ "$1 $2" = "pr create" ] && [ -f "$MOCK_DIR/echec_toujours" ]; then exit 1; fi
[ "$1 $2" = "pr list" ] && [ -f "$MOCK_DIR/pr" ] && echo 7
[ "$1 $2" = "pr view" ] && { cat "$MOCK_DIR/checks" 2>/dev/null || echo 2; }
[ "$1 $2" = "pr create" ] && touch "$MOCK_DIR/pr"
exit 0
MOCK
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
    sortie=$(cd "$t/clone" && PATH="$t/bin:$PATH" MOCK_DIR="$t" ESSAI_ATTENTES="0 0" GIT_AUTHOR_NAME=r GIT_AUTHOR_EMAIL=r@r GIT_COMMITTER_NAME=r GIT_COMMITTER_EMAIL=r@r \
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
  passe "même release, PR ouverte → rien" v1.1.0 "" "pr create|pr edit|workflow"
  passe "release suivante → PR mise à jour, CI relancée" v1.2.0 "gh pr edit;gh workflow run ci.yml" "pr create"
  # La branche est poussée mais la PR manque : création refusée au passage précédent
  # (réglage Actions désactivé, 06/11/2026) ou PR fermée. Le contenu identique ne
  # doit pas faire conclure qu'il n'y a « rien à faire ».
  rm -f "$t/pr"
  passe "branche déjà poussée, PR absente → PR créée" v1.2.0 "gh pr create;gh workflow run ci.yml" "-"
  local contenu
  contenu=$(git -C "$t/origin.git" show "auto/version-produit:site/index.html")
  case "$contenu" in *"Version 1.2.0"*) echo "  ok      la branche porte 1.2.0" ;;
    *) echo "  ÉCHEC   la branche ne porte pas 1.2.0"; echecs=$((echecs + 1)) ;; esac
  case "$(git -C "$t/origin.git" show "auto/version-produit:site/contenu.json")" in *"Version 1.2.0"*)
    echo "  ok      contenu.json suit la page" ;;
    *) echo "  ÉCHEC   contenu.json ne porte pas 1.2.0 : la CI de la PR refuserait la page"; echecs=$((echecs + 1)) ;; esac
  case "$(git -C "$t/origin.git" show "auto/version-produit:site/sitemap.xml")" in *"<lastmod>2026-01-01"*)
    echo "  ÉCHEC   lastmod de l'accueil pas avancé"; echecs=$((echecs + 1)) ;; *) echo "  ok      lastmod avancé" ;; esac
  # coprofirst-site#63 : une PR à jour mais sans check reçoit sa CI ; une relance qui
  # échoue une fois est retentée ; un échec qui dure fait échouer le passage.
  echo 0 > "$t/checks"
  passe "PR à jour sans aucun check → CI relancée" v1.2.0 "gh workflow run ci.yml;gh workflow run comptes-demo.yml" "pr create|pr edit"
  rm -f "$t/checks"
  touch "$t/echec_une_fois"
  passe "relance de la CI refusée une fois → retentée" v1.3.0 "gh pr edit" "pr create"
  case "$(grep -c 'gh workflow run ci.yml' "$t/appels")" in 2) echo "  ok      relance retentée : deux appels" ;;
    *) echo "  ÉCHEC   relance non retentée : $(tr '\n' '|' < "$t/appels")"; echecs=$((echecs + 1)) ;; esac
  rm -f "$t/pr"
  touch "$t/echec_toujours"
  if (cd "$t/clone" && PATH="$t/bin:$PATH" MOCK_DIR="$t" ESSAI_ATTENTES="0 0" GIT_AUTHOR_NAME=r GIT_AUTHOR_EMAIL=r@r GIT_COMMITTER_NAME=r GIT_COMMITTER_EMAIL=r@r \
       bash scripts/proposer-version.sh >/dev/null 2>&1); then
    echo "  ÉCHEC   un échec qui dure doit faire échouer le passage"; echecs=$((echecs + 1))
  else
    echo "  ok      échec qui dure → passage en échec (le ticket s'ouvre)"
  fi
  rm -f "$t/echec_toujours"
  [ "$echecs" -eq 0 ] && echo "selftest : OK" || { echo "selftest : $echecs ÉCHEC(S)"; return 1; }
}

if [ "${1:-}" = "--selftest" ]; then selftest; exit $?; fi
proposer
