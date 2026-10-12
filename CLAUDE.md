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
  La page est `site/index.html`, le logo `site/logo.svg`.
- **Domaine** : `coprofirst.fr` (pas encore acheté au 12/10/2026). **Démo** :
  `demo.coprofirst.fr` — un sous-domaine, parce qu'il ne coûte rien de plus et ne
  demande aucune modification de l'application (arbitrage du 12/10/2026 :
  « possible techniquement sans surcoût »).
- **Hébergement** : Oracle Cloud Always Free, comme la démo.
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

### Avant la mise en ligne — ce qui manque

- les pages **Mentions légales** et **Confidentialité** (`standards/14` §3) : les
  liens du pied de page pointent sur `#` ;
- le **thème sombre** (`standards/11` §10) : la page n'a que le thème clair ;
- les adresses d'entrée de la démo par rôle (la session qui monte la démo les
  fournira) : les trois boutons pointent sur `#demo` ;
- le remplacement des témoignages fictifs.

## Contrôles

`bash scripts/verifier-depot.sh` — encodage (BOM), fins de ligne (CRLF), bits
d'exécution et syntaxe des scripts. Il tourne en `pre-commit`
(`git config core.hooksPath .githooks`, à armer une fois par clone) et en CI, avec
`reuse lint`.
