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
#   5. la PR doit montrer ses checks : la poussée et l'ouverture faites avec le
#      GITHUB_TOKEN ne lancent pas la CI, mais l'événement pull_request du robot
#      crée bien ses runs, en ATTENTE D'APPROBATION (action_required : la politique
#      « first_time_contributors » du dépôt couvre github-actions[bot]). Sans
#      approbation, ils restent sans job, la PR paraît sans check et `depot` requis
#      bloque la fusion (coprofirst-site#63 : onze PR de suite, 10–11/11/2026). Le
#      robot approuve donc CES runs-là — même dépôt, sa branche, son commit, ouverts
#      par lui (filtre_en_attente) —, puis relit les checks sur la PR jusqu'à y voir
#      `depot` et `comptes` ; absents au bout des essais, le passage échoue et le
#      signale. Une relance par workflow_dispatch ne sert à rien : le rollup du
#      commit, que lit la PR, ignore ces suites (mesuré le 11/11/2026). Une PR déjà à
#      jour mais sans ses checks est reprise au passage suivant.
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

# checks_vus : combien des deux checks attendus (`depot`, requis, et `comptes`) la
# PR montre — ce que voit la protection de main.
checks_vus() {
  essayer gh pr view "$BRANCHE" --json statusCheckRollup \
    --jq '[.statusCheckRollup[] | select(.name == "depot" or .name == "comptes")] | length'
}

# filtre_en_attente <sha> : le filtre jq des runs que le robot a le droit
# d'approuver — ceux de SON événement pull_request, sur SA branche et SON commit,
# dans CE dépôt (jamais une fork). L'approbation protège du code d'un inconnu : ici
# le commit est celui que le robot vient d'écrire depuis main.
# Un run en attente d'approbation est TERMINÉ : `status` vaut `completed`, et c'est
# `conclusion` qui vaut `action_required` (relevé sur la PR coprofirst-site#82). Le
# paramètre `status=action_required` de la requête, lui, porte sur l'un ou l'autre.
# Le 11/11/2026, le filtre testait `.status` : il n'a rien trouvé en vrai.
filtre_en_attente() {
  printf '.workflow_runs[] | select(.event == "pull_request" and .conclusion == "action_required" and .head_sha == "%s" and .head_branch == "%s" and .head_repository.full_name == .repository.full_name and .actor.login == "github-actions[bot]") | .id' \
    "$1" "$BRANCHE"
}

# approuver_en_attente : approuve les runs du robot qui attendent sur la tête de la PR.
approuver_en_attente() {
  local sha ids id
  sha=$(essayer gh pr view "$BRANCHE" --json headRefOid --jq .headRefOid) || return 1
  ids=$(essayer gh api "repos/{owner}/{repo}/actions/runs?event=pull_request&status=action_required&head_sha=$sha" \
    --jq "$(filtre_en_attente "$sha")") || return 1
  for id in $ids; do
    essayer gh api -X POST "repos/{owner}/{repo}/actions/runs/$id/approve" >/dev/null || return 1
    echo "proposer-version : run $id approuvé (pull_request du robot sur $sha)"
  done
}

# obtenir_checks : jusqu'à ce que la PR montre ses checks, approuver ce qui attend
# (étape 5). VERIF_ATTENTES : l'attente avant chaque lecture — la première laisse à
# GitHub le temps de créer les runs (le selftest les met à zéro).
obtenir_checks() {
  local attentes n=0 vus
  attentes=(${VERIF_ATTENTES:-10 20 30 45})
  while :; do
    sleep "${attentes[$n]}"
    vus=$(checks_vus) || return 1
    if [ "${vus:-0}" -ge 2 ]; then
      echo "proposer-version : la PR montre ses checks (depot, comptes)"
      return 0
    fi
    if [ "$((n + 1))" -ge "${#attentes[@]}" ]; then
      echo "proposer-version : la PR ne montre toujours pas ses checks ($vus sur 2) — fusion bloquée (coprofirst-site#63)" >&2
      return 1
    fi
    approuver_en_attente || return 1
    n=$((n + 1))
  done
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
    local vus
    vus=$(checks_vus)
    if [ "${vus:-0}" -lt 2 ]; then
      echo "proposer-version : la PR porte déjà la version $version mais ne montre pas ses checks"
      obtenir_checks
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
  obtenir_checks
  echo "proposer-version : PR « version $version » à jour sur $BRANCHE"
}

# Le selftest rejoue le script dans un dépôt jetable : un « origin » nu, un gh qui
# note ses appels, et une source de release locale à la place de l'API.
selftest() {
  local t echecs=0
  # Le gh simulé passe ses réponses par jq, comme `gh --jq` : sans jq, rien ne
  # se prouve.
  command -v jq >/dev/null || { echo "selftest : INCONNU — jq absent"; return 2; }
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
  # Un run en attente tel que l'API le rend : relevé sur la PR coprofirst-site#82 le
  # 11/11/2026 (run 43006428811, champs lus par le filtre), commit remplacé par celui
  # du gh simulé. Le jeu inventé auparavant portait `status: action_required` : le
  # selftest passait, le vrai passage ne trouvait rien. Les cas en dérivent tous.
  cat > "$t/run.json" <<'JSON'
{"id": 43006428811, "event": "pull_request", "status": "completed", "conclusion": "action_required", "head_sha": "cafe123", "head_branch": "auto/version-produit", "head_repository": {"full_name": "philippe-tressard/coprofirst-site"}, "repository": {"full_name": "philippe-tressard/coprofirst-site"}, "actor": {"login": "github-actions[bot]"}, "triggering_actor": {"login": "github-actions[bot]"}}
JSON
  # Le gh simulé note ses appels (MOCK_DIR/appels) et obéit à des drapeaux posés par
  # les cas : pr (une PR existe), checks (ce que rend chaque lecture des checks de la
  # PR, une ligne par lecture, puis 2 : les deux checks attendus), attente (les runs
  # en attente d'approbation, un id par ligne ; approuvé, il en sort), echec_une_fois
  # (la prochaine approbation échoue), echec_toujours (« pr create » échoue). La liste
  # des runs est rendue au format de l'API (run.json) et passée par le filtre --jq
  # du script : c'est lui qui choisit les runs à approuver, pas le gh simulé.
  cat > "$t/bin/gh" <<'MOCK'
#!/bin/bash
echo "gh $*" >> "$MOCK_DIR/appels"
if [ "$1 $2 $3" = "api -X POST" ]; then
  if [ -f "$MOCK_DIR/echec_une_fois" ]; then rm -f "$MOCK_DIR/echec_une_fois"; exit 1; fi
  id=$(echo "$4" | sed -n 's|.*/runs/\([0-9]*\)/approve|\1|p')
  grep -vx "$id" "$MOCK_DIR/attente" > "$MOCK_DIR/attente.suite" 2>/dev/null; mv "$MOCK_DIR/attente.suite" "$MOCK_DIR/attente"
  exit 0
fi
if [ "$1" = api ]; then
  [ "$3" = --jq ] || { echo "gh simulé : --jq attendu" >&2; exit 1; }
  touch "$MOCK_DIR/attente"
  jq -n --slurpfile r "$MOCK_DIR/run.json" --rawfile ids "$MOCK_DIR/attente" \
    '{workflow_runs: [$ids | split("\n")[] | select(. != "") | $r[0] + {id: tonumber}]}' | jq -r "$4"
  exit 0
fi
if [ "$1 $2" = "pr create" ] && [ -f "$MOCK_DIR/echec_toujours" ]; then exit 1; fi
[ "$1 $2" = "pr list" ] && [ -f "$MOCK_DIR/pr" ] && echo 7
if [ "$1 $2" = "pr view" ]; then
  case "$*" in *headRefOid*) echo cafe123; exit 0 ;; esac
  if [ -s "$MOCK_DIR/checks" ]; then
    head -1 "$MOCK_DIR/checks"; tail -n +2 "$MOCK_DIR/checks" > "$MOCK_DIR/checks.suite"; mv "$MOCK_DIR/checks.suite" "$MOCK_DIR/checks"
  else echo 2; fi
fi
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
  # lancer <tag> : un passage du robot sur la release <tag>, attentes à zéro.
  lancer() {
    printf '{"tag_name": "%s", "published_at": "2026-11-05T17:01:00Z"}' "$1" > "$t/release.json"
    : > "$t/appels"
    (cd "$t/clone" && PATH="$t/bin:$PATH" MOCK_DIR="$t" ESSAI_ATTENTES="0 0" VERIF_ATTENTES="0 0 0 0" \
      GIT_AUTHOR_NAME=r GIT_AUTHOR_EMAIL=r@r GIT_COMMITTER_NAME=r GIT_COMMITTER_EMAIL=r@r bash scripts/proposer-version.sh 2>&1)
  }
  # echoue <libellé> <tag> : le passage doit échouer (le ticket « CI rouge » s'ouvre).
  echoue() {
    if lancer "$2" >/dev/null; then echo "  ÉCHEC   $1 : le passage aurait dû échouer"; echecs=$((echecs + 1))
    else echo "  ok      $1"; fi
  }
  # compte <libellé> <motif> <n> : la dernière exécution a fait n appels gh <motif>.
  compte() {
    case "$(grep -c "$2" "$t/appels")" in "$3") echo "  ok      $1" ;;
      *) echo "  ÉCHEC   $1 : $(tr '\n' '|' < "$t/appels")"; echecs=$((echecs + 1)) ;; esac
  }
  # attend <ids…> : la PR ne montre d'abord aucun check, et ces runs attendent.
  attend() { echo 0 > "$t/checks"; printf '%s\n' "$@" > "$t/attente"; }
  passe() { # <libellé> <tag> <appels gh exigés, séparés par ;> <absents (motif) ou ->
    local sortie
    sortie=$(lancer "$2") || { echo "  ÉCHEC   $1 : sortie non nulle — $sortie"; echecs=$((echecs + 1)); return; }
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
  # coprofirst-site#63 : les runs pull_request du robot attendent une approbation ;
  # sans elle la PR reste sans check et la fusion bloquée.
  attend 111 222
  passe "nouvelle release → PR ouverte, runs du robot approuvés" v1.1.0 "gh pr create;runs/111/approve;runs/222/approve" "pr edit|workflow run"
  passe "même release, PR ouverte → rien" v1.1.0 "" "pr create|pr edit|approve"
  attend 333
  passe "release suivante → PR mise à jour, runs approuvés" v1.2.0 "gh pr edit;runs/333/approve" "pr create"
  # La branche est poussée mais la PR manque : création refusée au passage précédent
  # (réglage Actions désactivé, 06/11/2026) ou PR fermée. Le contenu identique ne
  # doit pas faire conclure qu'il n'y a « rien à faire ».
  rm -f "$t/pr"
  attend 444
  passe "branche déjà poussée, PR absente → PR créée" v1.2.0 "gh pr create;runs/444/approve" "-"
  local contenu
  contenu=$(git -C "$t/origin.git" show "auto/version-produit:site/index.html")
  case "$contenu" in *"Version 1.2.0"*) echo "  ok      la branche porte 1.2.0" ;;
    *) echo "  ÉCHEC   la branche ne porte pas 1.2.0"; echecs=$((echecs + 1)) ;; esac
  case "$(git -C "$t/origin.git" show "auto/version-produit:site/contenu.json")" in *"Version 1.2.0"*)
    echo "  ok      contenu.json suit la page" ;;
    *) echo "  ÉCHEC   contenu.json ne porte pas 1.2.0 : la CI de la PR refuserait la page"; echecs=$((echecs + 1)) ;; esac
  case "$(git -C "$t/origin.git" show "auto/version-produit:site/sitemap.xml")" in *"<lastmod>2026-01-01"*)
    echo "  ÉCHEC   lastmod de l'accueil pas avancé"; echecs=$((echecs + 1)) ;; *) echo "  ok      lastmod avancé" ;; esac
  # Une PR à jour mais sans ses checks (approbation ratée au passage précédent) est
  # reprise ; une approbation refusée une fois est retentée ; des checks jamais vus
  # et un échec qui dure font échouer le passage, qui ouvre le ticket.
  attend 555
  printf '0\n0\n' > "$t/checks"
  passe "PR à jour sans ses checks → runs approuvés" v1.2.0 "runs/555/approve" "pr create|pr edit"
  attend 666
  touch "$t/echec_une_fois"
  passe "approbation refusée une fois → retentée" v1.3.0 "gh pr edit" "pr create"
  compte "approbation retentée : deux appels" "runs/666/approve" 2
  attend
  printf '0\n0\n0\n0\n0\n' > "$t/checks"
  echoue "checks jamais vus sur la PR → passage en échec" v1.4.0
  rm -f "$t/checks" "$t/attente" "$t/pr"
  touch "$t/echec_toujours"
  echoue "échec qui dure → passage en échec (le ticket s'ouvre)" v1.5.0
  rm -f "$t/echec_toujours"
  # Le filtre des runs approuvables, sur des variantes du run réel : seul le run du
  # robot en attente, sur sa branche, son commit et ce dépôt, passe — jamais celui
  # d'une fork, ni un run déjà joué.
  local ids
  ids=$(jq -c '. as $r | {workflow_runs: [
      $r + {id: 1},
      $r + {id: 2, head_repository: {full_name: "intrus/coprofirst-site"}},
      $r + {id: 3, head_sha: "beef456"},
      $r + {id: 4, head_branch: "autre"},
      $r + {id: 5, actor: {login: "inconnu"}},
      $r + {id: 6, event: "push"},
      $r + {id: 7, conclusion: "success"}
    ]}' "$t/run.json" | jq -r "$(filtre_en_attente cafe123)" | tr '\n' ' ')
  if [ "$ids" = "1 " ]; then echo "  ok      seul le run du robot en attente est approuvable (fork, autre commit, autre branche, autre auteur, run joué écartés)"
  else echo "  ÉCHEC   filtre des runs approuvables : « $ids », attendu « 1 »"; echecs=$((echecs + 1)); fi
  [ "$echecs" -eq 0 ] && echo "selftest : OK" || { echo "selftest : $echecs ÉCHEC(S)"; return 1; }
}

if [ "${1:-}" = "--selftest" ]; then selftest; exit $?; fi
proposer
