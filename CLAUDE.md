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
  `site/mentions-legales.html`, `site/confidentialite.html` ; styles partagés dans
  `site/commun.css`, ceux des pages de texte dans `site/document.css`, les scripts
  dans `site/accueil.js` et `site/demo.js` (pas de script en ligne : la CSP n'admet
  que `'self'`). Un site
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
  réservé à la démo. **Déployer** : `bash deploiement/deployer.sh` (HEAD poussé
  seulement, puis comparaison octet par octet de ce qui est servi ;
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
- **Témoignages fictifs** : la page les annonce comme tels. Ils se remplacent par
  de vrais retours, avec l'accord écrit de leurs auteurs — jamais présentés comme
  vrais.
- **Aucune police externe, aucun traceur** : c'est ce qui dispense de bandeau de
  consentement (`standards/14` §4). Un ajout de ce type rouvre la question.

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

### Ce qui reste

- le **thème sombre** (`standards/11` §10) : la page n'a que le thème clair ;
- le remplacement des témoignages fictifs.

## Contrôles

`bash scripts/verifier-depot.sh` — encodage (BOM), fins de ligne (CRLF), bits
d'exécution et syntaxe des scripts. Il tourne en `pre-commit`
(`git config core.hooksPath .githooks`, à armer une fois par clone) et en CI, avec
`reuse lint`.

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
