<!--
SPDX-FileCopyrightText: 2026 Philippe TRESSARD
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# CLAUDE.md — CoproFirst-Site

## ⚠️ Socle commun d'abord

Bonnes pratiques valables pour tous les projets : `~/.claude/standards/`
(routage : `~/.claude/CLAUDE.md` §1). Ce fichier ne contient que l'instanciation
CoproFirst-Site. **Toute modification d'écran suit la skill globale
`emil-design-eng`** — demandé explicitement par l'utilisateur (12/10/2026).

## Stack et état

- **Site statique** : HTML, CSS et JavaScript sans dépendance ni étape de build.
  `site/index.html` (accueil), `site/demo.html` (comptes de la démo),
  `site/mentions-legales.html`, `site/confidentialite.html`, `site/404.html` (servie
  par le Caddyfile sur toute adresse inconnue, avec le code 404 et les mêmes en-têtes
  de sécurité — `noindex`, hors du sitemap, ressources de l'en-tête en absolu) ; styles partagés dans
  `site/commun.css` (jetons de couleur : thème **sombre par défaut**, clair au
  choix du visiteur par l'interrupteur de l'en-tête, sans égard pour le thème de son
  système — demande du 21/10/2026 ; `site/theme.js`, chargé dans `<head>` avant la
  feuille, pose `data-theme` et mémorise le choix dans `localStorage`
  `coprofirst-theme`, ce que dit `confidentialite.html` ; `verifier-depot.sh` exige
  script et interrupteur dans chaque page. Une surface s'écrit `var(--carte)`, un
  texte bleu `var(--lien)`, jamais `#fff` ni `--bleu` en dur), ceux des pages de texte dans
  `site/document.css`, ceux de l'accueil dans `site/accueil.css`, les scripts
  dans `site/accueil.js` et `site/demo.js` (pas de script en ligne : la CSP n'admet
  que `'self'`). Le héros montre des **captures réelles** de la démo
  (`site/captures/`, refaites par `node scripts/generer-captures.mjs` après chaque
  version promue — le script affiche la version photographiée, lue au pied de
  l'application : la démo se met à jour la nuit, et peut encore servir la
  précédente juste après une promotion) et la **dernière version publiée** (`scripts/version-produit.py
  --ecrire`, jamais à la main). Un site
  sans build recopie l'en-tête et le pied dans chaque page : `verifier-depot.sh`
  exige que les pieds soient identiques.
- **Domaine** : `coprofirst.fr`, acheté le 13/10/2026. **Contact public** :
  `contact@coprofirst.fr`, un alias vérifié le 13/10/2026 (courriel reçu), au pied
  de la page. **Démo** :
  `demo.coprofirst.fr` — un sous-domaine, parce qu'il ne coûte rien de plus et ne
  demande aucune modification de l'application (arbitrage du 12/10/2026 :
  « possible techniquement sans surcoût »).
- **Hébergement** : Oracle Cloud (instance `coprofirst-demo`, Paris), comme la démo.
  En ligne depuis le 13/10/2026 : conteneur Caddy sur `127.0.0.1:8080`, derrière le
  tunnel Cloudflare (`coprofirst.fr`, `www` redirigé par Caddy) ; le port 80 est
  réservé à la démo. Le Caddyfile est validé à la construction de l'image (un
  Caddyfile invalide laisse l'ancien conteneur servir) et en CI. **Déployer** : `bash deploiement/deployer.sh` (HEAD poussé
  seulement, plus `site/avis.json` qui n'est pas versionné — voir Avis
  d'utilisateurs —, puis comparaison octet par octet de ce qui est servi ;
  `--verifier` pour le seul contrôle). Jamais de geste à la main sur le serveur.
- **Dépôt** : `philippe-tressard/coprofirst-site`, **public**, sous
  AGPL-3.0-or-later comme l'application (accord de l'utilisateur, 13/10/2026).
  Les commits portent l'adresse *noreply* de GitHub, réglée dans la configuration
  **locale** du clone : l'adresse globale du poste est personnelle, et GitHub
  refuse de la publier (GH007).
- `maquettes/` garde les dix propositions qui ont mené à la page ; `E` est la
  version retenue. Ce sont des archives : on ne les corrige pas.

## Ce qui est propre à ce projet

- **Le produit décrit est CoproFirst**, dont le code vit dans `C:\Dev\5hostachy`
  (dépôt `philippe-tressard/coprofirst`). Toute affirmation sur une
  fonctionnalité se vérifie dans son `README.md` ou son manuel avant d'être écrite
  ici. Vocabulaire de l'application : « Bailleur (mandataire) » pour l'agence ou
  le gestionnaire, « Aidant » pour la délégation en lecture.
- **Marque** : « CoproFirst — demande de marque n° 5307183 », jamais ® tant
  qu'elle n'est pas enregistrée (`MARQUE.md` de coprofirst). Le logo est sous
  `LicenseRef-CoproFirst-Logo`, hors de l'AGPL : il reste dans son fichier, jamais
  recopié en ligne dans le HTML.
- **Avis d'utilisateurs** (coprofirst-site#6, depuis le 20/10/2026 ; les
  témoignages fictifs sont retirés) : `site/avis.json` est l'export de l'onglet
  ⭐ Avis de l'application (« Exporter les avis retenus pour coprofirst.fr »,
  `avis-coprofirst-AAAA-MM-JJ.json`, installé en `site/avis.json`). Il n'est
  **pas versionné** (`.gitignore`) : un accord retiré ne doit pas survivre dans
  l'historique public. `deploiement/deployer.sh` va chercher **seul** le plus
  récent des `avis-coprofirst-*.json` des Téléchargements (`(1)` compris,
  `scripts/recuperer-avis.py`), le vérifie dans un fichier temporaire, l'installe,
  puis **efface les exports** des Téléchargements (copies de données
  personnelles) ; `--export CHEMIN` impose un fichier. Il l'envoie avec le commit,
  après `scripts/verifier-avis.py`, et **refuse sans lui** (`--garder-avis` reprend
  celui déjà en ligne, pour un déploiement d'un autre poste). Depuis PowerShell ou
  d'un double-clic : `.\deploiement\deployer.cmd` (mêmes options), qui cherche Git
  Bash ; il est en CRLF (`.gitattributes`), ce que `verifier-depot.sh` exige. À refaire **après chaque
  export** : un auteur qui retire son accord ne sort du site qu'au redéploiement.
  `accueil.js` les rend ; sans avis valide, la section et son lien restent masqués,
  **jamais** d'exemple à la place. Durée maximale de publication : **deux ans**
  après la date de l'avis, tenue à l'affichage et refusée au déploiement. Un nom de
  résidence dans le texte est admis ; le nom complet d'une personne, non (il se
  relit avant de retenir l'avis). La mention sous la section (L111-7-2, D111-17 du
  Code de la consommation) et `confidentialite.html#t-avis` disent comment ils
  sont choisis : les changer ensemble. Un texte long est coupé à cinq lignes avec
  « Lire la suite » (choix de Philippe, 20/10/2026) : le bouton ne paraît que si
  le texte déborde, jamais dans les copies `inert` de la boucle, et une carte
  dépliée met le défilement en pause.
- **Le mot du créateur** (section IA de l'accueil) : l'avis de l'éditeur, écrit en
  dur dans `index.html`, **jamais** parmi les avis d'utilisateurs (pratique
  commerciale trompeuse) — `verifier-avis.py` refuse un avis signé « Philippe T. »
  dans l'export : ne pas le retenir dans l'application (choix du 20/10/2026).
- **Aucune police externe, aucun traceur** : c'est ce qui dispense de bandeau de
  consentement (`standards/14` §4). Un ajout de ce type rouvre la question. La
  police des titres, **Fraunces** (OFL-1.1), est servie par le site lui-même
  (`site/polices/`, déclarée dans `REUSE.toml` et créditée aux mentions légales).
- **Référencement** : le site est ouvert à tous les robots, moteurs **et** assistants
  IA, entraînement compris (`site/robots.txt`, demande du 15/10/2026). Les données
  structurées ne balisent **jamais** les avis (`Review`, `AggregateRating`) : ce
  sont des avis sur son propre produit, choisis par l'éditeur parmi les 4 et 5
  étoiles — une note moyenne tirée d'eux tromperait, et Google écarte ces avis
  « auto-publiés » (décision du 20/10/2026, coprofirst-site#6).
  La FAQ de l'accueil porte son balisage schema.org en microdonnées, sur le texte
  visible : aucune copie à tenir à jour. L'image de partage se refait par
  `bash scripts/generer-image-partage.sh`. ⚠️ Cloudflare sert aussi son propre
  `robots.txt` géré (préambule *Content Signals*) et peut bloquer les robots IA à
  la périphérie, quoi que dise le fichier du dépôt : cela se règle dans son tableau
  de bord, pas ici.

- **La démo** est ouverte depuis le 14/10/2026. On y entre **par le formulaire de
  connexion** de `demo.coprofirst.fr`, avec trois comptes publics (CS,
  copropriétaire, locataire) que publie `site/demo.html` ; l'administrateur n'en est
  pas un (coprofirst#1932). Ces identifiants viennent de
  `api/app/demo/personnages.py` de CoproFirst : **s'ils y changent, `demo.html` doit
  suivre** — `scripts/verifier-comptes-demo.py` le vérifie chaque jour en CI (voir
  Contrôles).

- **Mentions légales** : éditeur particulier, **à titre non professionnel**, sans
  adresse publiée (LCEN — choix de l'utilisateur, 13/10/2026 : l'adresse est
  connue de l'hébergeur). Si CoproFirst devient une activité commerciale, l'adresse
  doit y figurer. Contact : `contact@coprofirst.fr`, jamais l'adresse personnelle.

## Contrôles

`bash scripts/verifier-depot.sh` — encodage (BOM), fins de ligne (CRLF), bits
d'exécution et syntaxe des scripts. Il tourne en `pre-commit`
(`git config core.hooksPath .githooks`, à armer une fois par clone) et en CI, avec
`reuse lint`.

`python3 scripts/verifier-referencement.py` — chaque page a son adresse canonique
(`https://coprofirst.fr/…`), ses balises Open Graph, un `<h1>` et aucun `noindex` ;
ses blocs JSON-LD se lisent ; `site/sitemap.xml` liste **exactement** les pages, et
chaque `lastmod` est au moins la date du dernier commit de sa page (**l'avancer**
quand on modifie une page) ;
`robots.txt` désigne le sitemap et ne ferme aucun robot ; les liens de `llms.txt`
mènent à des fichiers du site. Les pages d'erreur (`PAGES_D_ERREUR` : `404.html`) sont
nommées, et suivent la règle inverse : `noindex` obligatoire, ni canonique ni sitemap. En `pre-commit` et en CI, avec `--selftest`. **Une page
ajoutée** se déclare donc dans le sitemap (et dans `llms.txt`), avec ses balises de
tête recopiées d'une page voisine.

`python3 scripts/verifier-avis.py` — `site/avis.json` a la forme de l'export
(clés en **liste blanche** : une donnée ajoutée côté application ne part pas sans
décision), des notes de 4 ou 5, des dates de moins de deux ans, des auteurs
« Prénom N. » autres que l'éditeur, et aucun courriel ni téléphone dans un texte.
Sortie 0 conforme, 1 écart, 2 INCONNU ; `--selftest`, `--fichier`. Le fichier n'étant
pas versionné, c'est `deployer.sh` qui le lance (avant l'envoi, puis sur ce que le
serveur sert) ; la CI ne joue que le `--selftest`. Ses règles de forme et la durée
sont aussi celles de `avisValide` dans `site/accueil.js`.

`python3 scripts/recuperer-avis.py --selftest` — le choix de l'export par
`deployer.sh` : le plus récent gagne, `(1)` compris ; identique, rien n'est
installé ; refusé ou plus ancien, `site/avis.json` reste intact et l'export est
gardé ; jamais d'autre fichier effacé. En CI.

`python3 scripts/empreintes.py` — chaque `href="…css"`, `src="…js"` et
`src="…jpg"` (captures) des pages porte `?v=` + les 8 premiers caractères du sha256 du fichier : Cloudflare fait
garder CSS et JS **4 h** par le navigateur (le HTML 5 min), et sans empreinte un
déploiement sert le nouveau HTML avec l'ancien script (avis masqués le
20/10/2026). **Après toute modification d'un CSS, d'un JS ou d'une capture :**
`python3 scripts/empreintes.py --ecrire`. En `pre-commit` et en CI, avec
`--selftest`. Écrite dans le dépôt, pas au déploiement : le site servi reste
celui du commit.

`python3 scripts/verifier-comptes-demo.py` — les identifiants et mots de passe des
listes `.identifiants` de `site/demo.html` sont exactement ceux de
`api/app/demo/personnages.py` de CoproFirst (branche `main`, lu sur
raw.githubusercontent.com sans jeton). Sortie 0 conforme, 1 écart, **2 INCONNU**
(source injoignable, page ou source illisible) ; `--selftest`, `--source`, `--page`.
**En CI seulement** (`.github/workflows/comptes-demo.yml`, à chaque poussée et
chaque jour à 06:17 UTC), pas en pre-commit : la dérive naît dans l'autre dépôt, et
le réseau ne doit pas conditionner un commit. Il compare la page au code de `main`,
pas à la démo déployée. ⚠️ GitHub suspend un workflow planifié après 60 jours sans
activité du dépôt.

`python3 scripts/version-produit.py` — l'élément `<li data-version-produit>` du
héros affiche la dernière **release** de CoproFirst (la version promue, celle
qu'une résidence installe — pas le dernier commit de `main`), datée à l'heure de
Paris. Sortie 0 conforme, 1 écart, **2 INCONNU** ; `--ecrire`, `--selftest`,
`--source`. Comme les comptes de la démo : **en CI seulement**, chaque jour
(`comptes-demo.yml`, « Concordance avec CoproFirst »). Le site peut décrire une
fonction de `main` pas encore promue : la version affichée reste celle qu'on
installe. `scripts/lecture_distante.py` est la lecture commune des deux contrôles.
