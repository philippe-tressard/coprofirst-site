#!/bin/bash
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# verifier-depot.sh — ce que Windows abîme sans un mot (standards/08 §3, standards/10) :
#   - un BOM UTF-8 en tête de fichier texte ;
#   - des fins de ligne CRLF dans un dépôt écrit en LF (.gitattributes) — sauf les
#     scripts .cmd, qui doivent au contraire être entièrement en CRLF ;
#   - un script .sh ou .py, ou un hook de .githooks/, sans bit d'exécution dans l'index
#     (Windows avale `chmod +x`) ;
#   - un script dont la syntaxe est fausse (`bash -n`) ;
#   - un script ou un hook qui écrit en dur le chemin d'un poste (le dossier Dev du PC,
#     vu de Windows ou de Git Bash, ou celui du Mac) : il ment sur l'autre poste. Le chemin se lit dans
#     ~/.claude/projets.json (.claude/env-report.sh criait « répertoire inattendu » à
#     chaque session sur le Mac, 05/11/2026) ;
#   - un nom de domaine qui n'est ni un vrai domaine du site (liste blanche) ni un nom
#     réservé (example.com, .test, .example, .invalid) : un hôte fictif inventé est
#     souvent le domaine d'un tiers (standards/03 §8 quater, 15/11/2026).
# Et ce que la page publiée doit à la loi et à ses visiteurs (standards/14 §3, §4, §9) :
#   - les pages Mentions légales et Confidentialité existent ;
#   - chaque page du site y renvoie, sans lien mort (`href="#"`), avec le même pied ;
#   - aucune ressource chargée depuis un autre site (police, script, traceur) : ni par
#     une page, ni par une feuille de style, ni par un script, ni par un SVG ; et la
#     politique de sécurité du contenu (CSP) du Caddyfile ne nomme que le site ;
#   - ni « ® » (la marque n'est qu'une demande), ni balisage d'avis (Review, Rating).
# Et ce qui tient les dépendances à jour (standards/07 §7 bis, coprofirst-site#127) :
#   - .github/dependabot.yml nomme chaque écosystème du dépôt (docker si un Dockerfile,
#     github-actions si un workflow, pip si un requirements*.txt) ;
#   - l'image Caddy ne s'écrit qu'au FROM du Dockerfile : un workflow la lit, il ne la
#     recopie pas (Dependabot ne monterait que l'une des deux).
# Lit l'INDEX git : en pre-commit, c'est ce qui va partir ; en CI, ce qui est parti.
#
# Usage : bash scripts/verifier-depot.sh            (sortie non nulle = écart)
#         bash scripts/verifier-depot.sh --selftest (la règle, sans dépôt)
set -uo pipefail

# Extensions qui ne sont pas du texte : aucune vérification d'encodage.
BINAIRES='\.(png|jpe?g|gif|webp|ico|pdf|woff2?)$'

# Un hôte fictif se prend dans un nom réservé, jamais dans un domaine qui existe
# (standards/03 §8 quater) : la vitrine donnait des adresses de résidence sous le
# domaine « exemple » point « fr », qui répond en DNS — un visiteur qui recopie
# l'exemple y envoie sa saisie (15/11/2026).
# Tout nom de domaine écrit dans un fichier versionné, sous l'un des suffixes publics
# ci-dessous, doit être un vrai domaine du site (DOMAINES_REELS, ou l'un de leurs
# sous-domaines) ou un nom réservé de la RFC 2606 (example.com/.org/.net). Les suffixes
# réservés de la RFC 6761 (.test, .example, .invalid, .localhost) ne sont pas dans
# SUFFIXES : ils passent d'office. `.sh` et `.site` n'y sont pas non plus : un nom de
# script et un attribut Python (args.site) les portent.
SUFFIXES='fr|com|org|net|eu|io|dev|app|info|ai|cloud|be|ch|de|uk|co|me|xyz'
# Liste blanche : chaque domaine réel que le site cite ou charge. Rien d'autre n'y entre.
DOMAINES_REELS='coprofirst\.fr|github\.com|githubusercontent\.com|apple\.com|schema\.org|sitemaps\.org|w3\.org|gnu\.org|fsf\.org|spdx\.org|sil\.org|cnil\.fr|cloudflare\.com|indexnow\.org|llmstxt\.org|contentsignals\.org|git-scm\.com|google\.com'
RESERVES='example\.(com|org|net)'

# hotes_inconnus <chemin> — fonction PURE : un domaine hors liste blanche par ligne.
hotes_inconnus() {
  grep -oiE "\b([a-z0-9-]+\.)+($SUFFIXES)\b" "$1" | tr 'A-Z' 'a-z' | sort -u \
    | grep -vE "^([a-z0-9-]+\.)*($DOMAINES_REELS|$RESERVES)$"
}

# Ressource tierce (standards/14 §4 : ni police externe ni traceur, donc pas de bandeau).
# Une page la charge par une balise (juger_page) ; une feuille par url() ou @import ;
# un SVG par href ; un script par tout appel réseau — fetch, import, sendBeacon,
# WebSocket, .src = — d'une adresse absolue : un script du site n'a aucune raison d'en
# écrire une (un lien vit dans la page). Les coches de commun.css, en URI data:, portent
# « http://www.w3.org » dans leur texte sans rien charger : les motifs les épargnent.
# Jusqu'au 23/11/2026, seules les pages étaient lues (coprofirst-site#121).
TIERS_CSS='url\([[:space:]]*["'"'"']?(https?:)?//|@import[[:space:]]+(url\()?[[:space:]]*["'"'"']?(https?:)?//'
TIERS_JS='["'"'"'`](https?:)?//[a-z0-9]'
TIERS_SVG='href="(https?:)?//'
# La marque n'est qu'une demande (n° 5307183) : « ® » serait une fausse mention
# d'enregistrement. Le jour où elle est enregistrée (rendez-vous coprofirst#1804),
# MARQUE_ENREGISTREE passe à oui et la règle tombe.
MARQUE_ENREGISTREE=non
SYMBOLE_R='®|&reg;|&#0*174;|&#x0*ae;'
# Les avis sont choisis par l'éditeur parmi les 4 et 5 étoiles : une note balisée
# tromperait les moteurs (CLAUDE.md, Référencement). Aucun type ni propriété d'avis.
BALISES_AVIS='[Aa]ggregateRating|reviewCount|ratingValue|reviewRating|schema\.org/(Review|Rating)\b|"(Review|Rating)"'

# juger_publie <chemin> — fonction PURE : ce qu'un fichier servi (site/) ne doit pas
# porter, quel que soit son type. Un écart par ligne.
juger_publie() {
  local f="$1"
  case "$f" in
    *.css) grep -Eiq "$TIERS_CSS" "$f" && echo "TIERS    $f (url() ou @import vers un autre site)" ;;
    *.js|*.mjs) grep -Eiq "$TIERS_JS" "$f" && echo "TIERS    $f (adresse absolue dans un script : tout chargement reste sur le site)" ;;
    *.svg) grep -Eiq "$TIERS_SVG" "$f" && echo "TIERS    $f (href vers un autre site)" ;;
  esac
  [[ "$f" =~ $BINAIRES ]] && return 0
  if [ "$MARQUE_ENREGISTREE" = non ]; then
    grep -Eiq "$SYMBOLE_R" "$f" && echo "MARQUE   $f (® : la marque n'est qu'une demande, n° 5307183)"
  fi
  grep -Eq "$BALISES_AVIS" "$f" && echo "AVIS     $f (balisage d'avis ou de note : jamais sur ces avis choisis)"
  return 0
}

# csp_du_caddyfile — la valeur de Content-Security-Policy que pose le Caddyfile.
csp_du_caddyfile() { sed -n 's/.*Content-Security-Policy "\(.*\)".*/\1/p' deploiement/Caddyfile | head -1; }

# juger_csp <valeur> — fonction PURE : la politique ne nomme que le site lui-même. Toute
# source autre que 'self' et 'none' est un écart, sauf deux, déclarées : 'unsafe-inline'
# dans style-src (les attributs style= des pages) et data: dans img-src (les coches de
# commun.css). Une CSP élargie avec le CSS laisserait passer ce que TIERS refuse.
juger_csp() {
  [ -n "$1" ] || { echo "CSP      (aucune politique dans le Caddyfile)"; return 0; }
  local d nom s
  local -a sources
  while IFS= read -r d; do
    read -r nom d <<< "$d"
    [ -n "${nom:-}" ] || continue
    read -r -a sources <<< "$d"
    for s in ${sources[@]+"${sources[@]}"}; do
      case "$nom:$s" in
        *:"'self'"|*:"'none'"|style-src:"'unsafe-inline'"|img-src:data:) ;;
        *) echo "CSP      $nom $s (admis : 'self', 'none' ; 'unsafe-inline' en style-src, data: en img-src)" ;;
      esac
    done
  done < <(tr ';' '\n' <<< "$1")
  grep -q 'default-src' <<< "$1" || echo "CSP      (default-src absent : une source non nommée serait admise)"
  return 0
}

# juger_dependances <racine> — fonction PURE : Dependabot couvre chaque écosystème, et
# aucun workflow ne recopie l'image du Dockerfile.
juger_dependances() {
  local r="$1" d="$1/.github/dependabot.yml" eco
  for eco in docker github-actions pip; do
    case "$eco" in
      docker) [ -n "$(find "$r" -name Dockerfile -not -path '*/.git/*' -not -path '*/maquettes/*' | head -1)" ] || continue ;;
      github-actions) grep -qs 'uses:' "$r"/.github/workflows/*.yml || continue ;;
      pip) [ -n "$(find "$r" -name 'requirements*.txt' -not -path '*/.git/*' | head -1)" ] || continue ;;
    esac
    grep -qsE "package-ecosystem: *\"?$eco\"?" "$d" \
      || echo "DEPENDANCES .github/dependabot.yml ne suit pas « $eco » (présent dans le dépôt)"
  done
  grep -lsE 'caddy:[0-9]' "$r"/.github/workflows/*.yml | while read -r f; do
    echo "DEPENDANCES ${f#"$r"/} recopie l'image Caddy : la lire au FROM de deploiement/Dockerfile"
  done
  return 0
}

# juger_branchement <racine> — fonction PURE : chaque scripts/verifier-* est lancé par
# scripts/controles.sh ou par un workflow. Un contrôle écrit et jamais lancé ne protège
# rien (standards/05 §2 ; coprofirst-site#130).
juger_branchement() {
  local r="$1" f nom
  for f in "$r"/scripts/verifier-*; do
    [ -f "$f" ] || continue
    nom=${f##*/}
    grep -qsF "scripts/$nom" "$r/scripts/controles.sh" "$r"/.github/workflows/*.yml \
      || echo "BRANCHE  scripts/$nom n'est lancé ni par scripts/controles.sh ni par un workflow"
  done
  return 0
}

# juger_fichier <chemin> <mode git> — fonction PURE : lit le fichier, n'écrit rien.
# Écrit un écart par ligne ; rien si le fichier est conforme.
juger_fichier() {
  local f="$1" mode="$2"
  [[ "$f" =~ $BINAIRES ]] && return 0
  [ -f "$f" ] || return 0
  if [ "$(head -c 3 "$f" | od -An -tx1 | tr -d ' \n')" = "efbbbf" ]; then
    echo "BOM      $f"
  fi
  # Compter les octets CR : le grep de Git Bash retire le CR avant de comparer
  if [[ "$f" == *.cmd ]]; then
    # Autant de CR que de LF : chaque ligne finit en CRLF (cmd.exe lit mal le LF seul)
    [ "$(tr -cd '\r' < "$f" | wc -c)" -eq "$(tr -cd '\n' < "$f" | wc -c)" ] || echo "LF       $f (un script .cmd s'écrit en CRLF)"
  elif [ "$(tr -cd '\r' < "$f" | wc -c)" -gt 0 ]; then
    echo "CRLF     $f"
  fi
  # Les hooks git n'ont pas d'extension, mais s'exécutent comme les scripts
  if [[ "$f" == *.sh || "$f" == *.py || "$f" == .githooks/* ]]; then
    [ "$mode" = "100755" ] || echo "MODE     $f ($mode, attendu 100755 : git update-index --chmod=+x $f)"
  fi
  # Les crochets empêchent le motif de se trouver lui-même dans ce fichier.
  if [[ "$f" == *.sh || "$f" == *.py || "$f" == *.cmd || "$f" == *.mjs || "$f" == .githooks/* || "$f" == .claude/* ]]; then
    grep -qE '/[c]/Dev/|[A-Za-z]:[\\]+Dev[\\]|/Volumes/Data/[D]ev/' "$f" && echo "POSTE    $f (chemin d'un poste écrit en dur : le lire dans ~/.claude/projets.json)"
  fi
  # maquettes/ : archives jamais servies, qu'on ne corrige pas (CLAUDE.md du site).
  if [[ "$f" != maquettes/* ]]; then
    local h
    for h in $(hotes_inconnus "$f"); do
      echo "HOTE     $f ($h : domaine hors liste blanche — un hôte fictif se prend dans example.com, .test, .example ou .invalid ; un vrai domaine du site s'ajoute à DOMAINES_REELS)"
    done
  fi
  # Un script Python prouve sa syntaxe par son --selftest, lancé en CI
  if [[ "$f" == *.sh || "$f" == .githooks/* ]]; then
    bash -n "$f" 2>/dev/null || echo "SYNTAXE  $f (bash -n)"
  fi
}

# juger_page <chemin> — fonction PURE : les règles d'une page HTML publiée.
juger_page() {
  local f="$1"
  grep -q 'href="#"' "$f" && echo "LIEN     $f (href=\"#\" : lien qui ne mène nulle part)"
  grep -q 'href="/\?mentions-legales.html"' "$f" || echo "MENTIONS $f (pas de lien vers mentions-legales.html)"
  grep -q 'href="/\?confidentialite.html"' "$f" || echo "CONFID   $f (pas de lien vers confidentialite.html)"
  # Le thème sombre par défaut vit dans theme.js (chargé avant la feuille de style, sans
  # quoi la page clignote) et dans l'interrupteur de l'en-tête : sans l'un ou l'autre,
  # un visiteur reste coincé dans un thème qu'il n'a pas choisi.
  # (en absolu « /theme.js » dans 404.html, qui répond aussi aux adresses profondes)
  grep -q '<script src="/\?theme.js' "$f" || echo "THEME    $f (theme.js non chargé)"
  grep -q 'data-bascule-theme' "$f" || echo "THEME    $f (pas d'interrupteur de thème)"
  # Ressource tierce : <script src>, <link href>, <img src>, url() ou @import vers http(s).
  # Un <link rel="canonical"> ou « alternate » désigne une adresse, il ne charge rien :
  # il est écarté (une balise par ligne, comme dans les pages du site).
  grep -Eiv '<link rel="(canonical|alternate)"' "$f" \
    | grep -Eiq '<(script|img|iframe)[^>]* src="(https?:)?//|<link[^>]* href="(https?:)?//|url\((["'"'"'])?(https?:)?//|@import' \
    && echo "TIERS    $f (ressource chargée depuis un autre site)"
  # Les deux prises d'une capture, une par thème (coprofirst-site#33), vont par paire ;
  # la claire porte loading="lazy" : une image en display:none se télécharge, sauf lazy.
  local claires sombres
  claires=$(grep -c 'class="vue-clair"' "$f" || true)
  sombres=$(grep -c 'class="vue-sombre"' "$f" || true)
  [ "$claires" = "$sombres" ] || echo "CAPTURE  $f ($claires prise(s) claire(s), $sombres sombre(s) : elles vont par paire)"
  grep 'class="vue-clair"' "$f" | grep -qv 'loading="lazy"' \
    && echo "CAPTURE  $f (prise claire sans loading=\"lazy\" : elle se télécharge même cachée)"
  return 0
}

# pied <chemin> — le pied de page, sans la marque de la page courante.
pied() { sed -n '/<footer>/,/<\/footer>/p' "$1" | sed 's/ aria-current="page"//'; }

# juger_site — les pages obligatoires existent, chaque page est conforme, et toutes
# portent le même pied de page (un site statique sans build le recopie : ce contrôle
# empêche les copies de diverger).
juger_site() {
  local f ref=""
  for f in site/mentions-legales.html site/confidentialite.html; do
    [ -f "$f" ] || echo "MANQUE   $f (page obligatoire)"
  done
  for f in site/*.html; do
    [ -f "$f" ] || continue
    juger_page "$f"
    if [ -z "$ref" ]; then ref="$f"
    elif [ "$(pied "$f")" != "$(pied "$ref")" ]; then echo "PIED     $f (pied de page différent de $ref)"; fi
  done
}

selftest() {
  local t; t=$(mktemp -d)
  printf 'ok\n' > "$t/bon.html"
  printf '\xef\xbb\xbfok\n' > "$t/bom.html"
  printf 'ok\r\n' > "$t/crlf.css"
  printf '@echo off\r\nexit /b 0\r\n' > "$t/bon.cmd"
  printf '@echo off\nexit /b 0\n' > "$t/lf.cmd"
  printf '#!/bin/bash\necho ok\n' > "$t/bon.sh"
  printf '#!/bin/bash\nif then\n' > "$t/faux.sh"
  printf '\x89PNG\r\n' > "$t/image.png"
  printf '#!/usr/bin/env python3\n' > "$t/outil.py"
  # Les chemins des cas fautifs s'assemblent, sinon ce fichier se refuserait lui-même.
  local d=Dev
  printf '#!/bin/bash\nA=/c/%s/Projet\n' "$d" > "$t/poste-bash.sh"
  printf 'racine = r"C:\\%s\\Projet"\n' "$d" > "$t/poste-win.py"
  printf 'const r = "/Volumes/Data/%s/Projet";\n' "$d" > "$t/poste-mac.mjs"
  # Hôtes : le domaine tiers s'assemble aussi, pour que ce fichier passe son propre contrôle.
  local tld=fr
  printf '<li>75015-les-tilleuls.exemple.%s</li>\n' "$tld" > "$t/hote-tiers.html"
  printf 'courriel = "a.g@exemple.%s"\n' "$tld" > "$t/hote-courriel.py"
  printf '<li>Residence-Des-Chenes.%s</li>\n' "FR" > "$t/hote-majuscules.html"
  printf 'https://api.github.com.evil.example/x https://coprofirst.fr.exemple.%s/\n' "$tld" > "$t/hote-imite.py"
  printf '%s\n' '<a href="https://demo.coprofirst.fr/">démo</a> <a href="https://www.cnil.fr/">CNIL</a>' \
    'https://raw.githubusercontent.com/x https://apps.apple.com/fr/app/x' \
    '<li>75015-les-tilleuls.example.com</li> vous@example.org h.example.net' \
    'residence.test site.invalid fonts.example localhost' \
    'bash deployer.sh ; args.site ; self.site' > "$t/hote-admis.html"
  local echecs=0
  verifie() { # <attendu> <fichier> <mode>
    local obtenu; obtenu=$(juger_fichier "$t/$2" "$3" | awk '{print $1}' | tr '\n' ' ')
    if [ "$obtenu" = "$1" ]; then echo "  ok      $2 → «$1»"; else echo "  ÉCHEC   $2 → «${obtenu}», attendu «$1»"; echecs=$((echecs + 1)); fi
  }
  verifie "" bon.html 100644
  verifie "BOM " bom.html 100644
  verifie "CRLF " crlf.css 100644
  verifie "" bon.cmd 100644
  verifie "LF " lf.cmd 100644
  verifie "" bon.sh 100755
  verifie "MODE " bon.sh 100644
  verifie "SYNTAXE " faux.sh 100755
  verifie "" image.png 100644
  verifie "" outil.py 100755
  verifie "MODE " outil.py 100644
  verifie "POSTE " poste-bash.sh 100755
  verifie "POSTE " poste-win.py 100755
  verifie "POSTE " poste-mac.mjs 100644
  verifie "HOTE " hote-tiers.html 100644
  verifie "HOTE " hote-courriel.py 100755
  verifie "HOTE " hote-majuscules.html 100644
  verifie "HOTE " hote-imite.py 100755
  verifie "" hote-admis.html 100644
  # Règles d'une page publiée
  local theme='<script src="theme.js?v=1"></script><button data-bascule-theme></button>'
  local liens='<a href="mentions-legales.html">M</a><a href="confidentialite.html">C</a>'"$theme"
  printf '%s
' "<footer>$liens</footer>" > "$t/bonne.html"
  printf '%s
' '<a href="#">x</a>' "$liens" > "$t/morte.html"
  printf '%s
' '<a href="mentions-legales.html">M</a>' > "$t/sans-confid.html"
  printf '%s
' "$liens" '<link rel="stylesheet" href="https://fonts.example/f.css">' > "$t/police.html"
  printf '%s
' "$liens" '<script src="//traceur.example/t.js"></script>' > "$t/traceur.html"
  printf '%s
' "$liens" '<a href="https://github.com/x">code</a>' > "$t/lien-sortant.html"
  printf '%s
' '<a href="mentions-legales.html">M</a><a href="confidentialite.html">C</a>' > "$t/sans-theme.html"
  printf '%s
' "$liens" '<link rel="canonical" href="https://coprofirst.fr/">' > "$t/canonique.html"
  printf '%s
' "$liens" '<link rel="canonical" href="https://coprofirst.fr/">' '<link rel="stylesheet" href="https://fonts.example/f.css">' > "$t/canonique-et-police.html"
  page() { # <attendu> <fichier>
    local obtenu; obtenu=$(juger_page "$t/$2" | awk '{print $1}' | tr '
' ' ')
    if [ "$obtenu" = "$1" ]; then echo "  ok      $2 → «$1»"; else echo "  ÉCHEC   $2 → «${obtenu}», attendu «$1»"; echecs=$((echecs + 1)); fi
  }
  page "" bonne.html
  page "LIEN " morte.html
  page "CONFID THEME THEME " sans-confid.html
  page "TIERS " police.html
  page "TIERS " traceur.html
  page "" lien-sortant.html
  page "THEME THEME " sans-theme.html
  printf '%s
' '<a href="mentions-legales.html">M</a><a href="confidentialite.html">C</a><script src="/theme.js?v=1"></script><button data-bascule-theme></button>' > "$t/theme-absolu.html"
  page "" theme-absolu.html
  printf '%s\n' '<footer><a href="/mentions-legales.html">M</a><a href="/confidentialite.html">C</a></footer><script src="/theme.js?v=1"></script><button data-bascule-theme></button>' > "$t/pied-absolu.html"
  page "" pied-absolu.html
  page "" canonique.html
  page "TIERS " canonique-et-police.html
  local paire='<img class="vue-sombre" src="a-sombre.jpg"><img class="vue-clair" src="a.jpg" loading="lazy">'
  printf '%s\n' "$liens" "$paire" > "$t/capture-paire.html"
  printf '%s\n' "$liens" '<img class="vue-clair" src="a.jpg" loading="lazy">' > "$t/capture-sans-sombre.html"
  printf '%s\n' "$liens" '<img class="vue-sombre" src="a-sombre.jpg"><img class="vue-clair" src="a.jpg">' > "$t/capture-sans-lazy.html"
  page "" capture-paire.html
  page "CAPTURE " capture-sans-sombre.html
  page "CAPTURE " capture-sans-lazy.html
  # Fichiers servis : feuilles, scripts, SVG (coprofirst-site#121), marque, avis.
  publie() { # <attendu> <fichier>
    local obtenu; obtenu=$(juger_publie "$t/$2" | awk '{print $1}' | tr '\n' ' ')
    if [ "$obtenu" = "$1" ]; then echo "  ok      $2 → «$1»"; else echo "  ÉCHEC   $2 → «${obtenu}», attendu «$1»"; echecs=$((echecs + 1)); fi
  }
  printf '%s\n' ".a{background:url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'%3E\")}" '.b{background:url(captures/a.jpg)}' > "$t/coche.css"
  printf '%s\n' '@import url("https://tiers.example/x.css");' > "$t/import.css"
  printf '%s\n' '@import "//tiers.example/x.css";' > "$t/import-nu.css"
  printf '%s\n' '@font-face{font-family:F;src:url(https://cdn.example/f.woff2)}' > "$t/police.css"
  printf '%s\n' "const r = await fetch('avis.json', { cache: 'no-cache' }); // https://exemple sans guillemet" > "$t/local.js"
  printf '%s\n' 'fetch("https://tiers.example/collect");' > "$t/collecte.js"
  printf '%s\n' "navigator.sendBeacon(\`//tiers.example/b\`, d);" > "$t/balise.js"
  printf '%s\n' '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>' > "$t/logo.svg"
  printf '%s\n' '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://tiers.example/i.png"/></svg>' > "$t/image-tierce.svg"
  printf '%s\n' '<p>CoproFirst — demande de marque n° 5307183</p>' > "$t/marque.html"
  printf '%s\n' '<p>CoproFirst®</p>' > "$t/marque-r.html"
  printf '%s\n' '<p>CoproFirst&reg;</p>' > "$t/marque-entite.html"
  printf '%s\n' '{"@type": "AggregateRating", "ratingValue": 5}' > "$t/note.json"
  printf '%s\n' '<div itemscope itemtype="https://schema.org/Review">' > "$t/avis-micro.html"
  printf '%s\n' '{"@type": ["Thing", "Review"]}' > "$t/avis-ld.html"
  publie "" coche.css
  publie "TIERS " import.css
  publie "TIERS " import-nu.css
  publie "TIERS " police.css
  publie "" local.js
  publie "TIERS " collecte.js
  publie "TIERS " balise.js
  publie "" logo.svg
  publie "TIERS " image-tierce.svg
  publie "" marque.html
  publie "MARQUE " marque-r.html
  publie "MARQUE " marque-entite.html
  publie "AVIS " note.json
  publie "AVIS " avis-micro.html
  publie "AVIS " avis-ld.html
  # La CSP : celle du Caddyfile passe ; chaque élargissement est refusé.
  csp() { # <attendu> <valeur>
    local obtenu; obtenu=$(juger_csp "$2" | awk '{print $1}' | tr '\n' ' ')
    if [ "$obtenu" = "$1" ]; then echo "  ok      csp « ${2:0:40}… » → «$1»"; else echo "  ÉCHEC   csp « $2 » → «${obtenu}», attendu «$1»"; echecs=$((echecs + 1)); fi
  }
  local base="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'"
  csp "" "$base"
  csp "CSP " "$base; font-src 'self' https://cdn.example"
  csp "CSP " "default-src 'self'; script-src 'self' 'unsafe-inline'"
  csp "CSP " "default-src 'self'; img-src 'self' data: *"
  csp "CSP " "script-src 'self'"
  csp "CSP " ""
  # Dependabot et l'image Caddy (coprofirst-site#127) : un dépôt jetable par cas.
  depend() { # <attendu> <racine>
    local obtenu; obtenu=$(juger_dependances "$2" | awk '{print $1}' | tr '\n' ' ')
    if [ "$obtenu" = "$1" ]; then echo "  ok      dépendances ${2##*/} → «$1»"; else echo "  ÉCHEC   dépendances ${2##*/} → «${obtenu}», attendu «$1»"; echecs=$((echecs + 1)); fi
  }
  local r
  for r in complet sans-docker sans-dependabot recopie; do
    mkdir -p "$t/$r/deploiement" "$t/$r/.github/workflows"
    printf 'FROM caddy:2@sha256:0\n' > "$t/$r/deploiement/Dockerfile"
    printf 'steps:\n  - uses: actions/checkout@0\n  - run: docker run "$(sed -n s/^FROM.//p deploiement/Dockerfile)"\n' > "$t/$r/.github/workflows/ci.yml"
    printf 'updates:\n  - package-ecosystem: docker\n  - package-ecosystem: "github-actions"\n' > "$t/$r/.github/dependabot.yml"
  done
  printf 'updates:\n  - package-ecosystem: github-actions\n' > "$t/sans-docker/.github/dependabot.yml"
  rm "$t/sans-dependabot/.github/dependabot.yml"
  printf '  - run: docker run caddy:2@sha256:0 caddy validate\n' >> "$t/recopie/.github/workflows/ci.yml"
  depend "" "$t/complet"
  depend "DEPENDANCES " "$t/sans-docker"
  depend "DEPENDANCES DEPENDANCES " "$t/sans-dependabot"
  depend "DEPENDANCES " "$t/recopie"
  printf 'reuse==1\n' > "$t/complet/.github/requirements-ci.txt"
  depend "DEPENDANCES " "$t/complet"
  # Branchement des contrôles (coprofirst-site#130).
  mkdir -p "$t/branche/scripts" "$t/branche/.github/workflows"
  : > "$t/branche/scripts/verifier-a.sh"; : > "$t/branche/scripts/verifier-b.py"
  printf 'bash scripts/verifier-a.sh\n' > "$t/branche/scripts/controles.sh"
  printf '  run: python3 scripts/verifier-b.py\n' > "$t/branche/.github/workflows/x.yml"
  local obtenu; obtenu=$(juger_branchement "$t/branche" | awk '{print $1}' | tr '\n' ' ')
  [ "$obtenu" = "" ] && echo "  ok      contrôles branchés → «»" || { echo "  ÉCHEC   contrôles branchés → «$obtenu»"; echecs=$((echecs + 1)); }
  : > "$t/branche/scripts/verifier-c.py"
  obtenu=$(juger_branchement "$t/branche" | awk '{print $1}' | tr '\n' ' ')
  [ "$obtenu" = "BRANCHE " ] && echo "  ok      contrôle jamais lancé → «BRANCHE »" || { echo "  ÉCHEC   contrôle jamais lancé → «$obtenu»"; echecs=$((echecs + 1)); }
  rm -rf "$t"
  [ "$echecs" -eq 0 ] && echo "selftest : OK" || { echo "selftest : $echecs ÉCHEC(S)"; return 1; }
}

if [ "${1:-}" = "--selftest" ]; then selftest; exit $?; fi

racine=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "INCONNU : pas un dépôt git"; exit 2; }
cd "$racine" || exit 2
# --csp : la politique du Caddyfile, que verifier-service.sh compare à celle servie.
if [ "${1:-}" = "--csp" ]; then csp_du_caddyfile; exit 0; fi
nb=$(git ls-files | wc -l)
# Cas zéro : un index vide ne prouve rien (standards/04 §2)
[ "$nb" -gt 0 ] || { echo "INCONNU : aucun fichier dans l'index — rien n'a été vérifié"; exit 2; }

ecarts=$(git ls-files -s | while read -r mode _ _ f; do
           juger_fichier "$f" "$mode"
           [[ "$f" == site/* && -f "$f" ]] && juger_publie "$f"
         done; juger_site; juger_csp "$(csp_du_caddyfile)"; juger_dependances "$racine"; juger_branchement "$racine")
if [ -n "$ecarts" ]; then
  echo "$ecarts"
  echo "verifier-depot : $(echo "$ecarts" | wc -l) écart(s) sur $nb fichiers"
  exit 1
fi
echo "verifier-depot : OK ($nb fichiers)"
