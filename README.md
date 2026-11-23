<!--
SPDX-FileCopyrightText: 2026 Philippe TRESSARD
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# CoproFirst — le site

La page d'accueil de [CoproFirst](https://github.com/philippe-tressard/coprofirst),
l'application libre de gestion de copropriétés : ce qu'elle fait, pour qui, son
assistant IA facultatif, une démonstration en ligne et le lien vers son code.

Servie sur **coprofirst.fr** ; la démonstration est sur **demo.coprofirst.fr**, et la
page `demo.html` en publie les trois comptes publics.

## Contenu

| Chemin | Rôle |
|---|---|
| `site/index.html` | la page d'accueil — HTML et CSS, sans dépendance ni build |
| `site/contenu.json` | le contenu de l'accueil en JSON, lu par les applications iOS et Android : **extrait** de `index.html` par `scripts/contenu-accueil.py --ecrire`, jamais écrit à la main. Ce qui part, la page le déclare (`data-contenu="<id>"`) ; l'identifiant est un contrat avec les apps (`scripts/verifier-contrat-apps.py`) |
| `site/demo.html` | la page Démo : les comptes publics de la démonstration, repris de `api/app/demo/personnages.py` de CoproFirst |
| `site/mentions-legales.html`, `site/confidentialite.html` | les pages obligatoires ; la seconde est aussi la politique de confidentialité des apps iPhone et Android |
| `site/supprimer-compte.html` | comment un résident fait supprimer son compte, avec ou sans l'app (l'adresse qu'exige Google Play) |
| `site/404.html` | la page des adresses inconnues, servie avec le code 404 par le Caddyfile (`noindex`, hors du sitemap) |
| `site/*.css`, `site/*.js` | styles partagés (jetons de couleur, thèmes clair et sombre), des pages de texte et de l'accueil ; `theme.js` (le thème choisi), les scripts de l'accueil et de la page Démo |
| `site/polices/` | Fraunces, la police des titres, servie par le site (SIL Open Font License 1.1, `LICENSES/OFL-1.1.txt`) |
| `site/captures/` | les captures réelles de la démonstration montrées par l'accueil — refaites par `scripts/generer-captures.mjs` |
| `site/logo.svg` | le logo de CoproFirst (licence propre, voir plus bas) |
| `site/robots.txt`, `site/sitemap.xml`, `site/llms.txt` | ce que lisent les moteurs de recherche et les assistants IA : tout le site leur est ouvert |
| `site/partage.png`, `site/apple-touch-icon.png` | l'image des aperçus de lien (Open Graph), l'icône des écrans d'accueil |
| `deploiement/` | le conteneur Caddy qui sert le site, et `deployer.sh` |
| `scripts/` | un script par contrôle ou par geste, chacun décrit par son **en-tête** (usage, ce qu'il vérifie, ce qu'il ne couvre pas) ; `controles.sh` lance ceux qui tournent hors réseau |
| `maquettes/` | les maquettes qui ont mené à la page, archivées telles quelles, jamais servies |

Pour voir le site : `python -m http.server -d site`, puis http://localhost:8000.

## Mise en ligne

Le site est servi sur **https://coprofirst.fr** par un conteneur Caddy
(`deploiement/`) sur une instance Oracle Cloud, derrière un tunnel Cloudflare.
`www.coprofirst.fr` redirige vers `coprofirst.fr`.

```bash
bash deploiement/deployer.sh             # déploie HEAD, une fois poussé
bash deploiement/deployer.sh --verifier  # compare au dépôt ce que sert l'origine, puis https://coprofirst.fr/
```

## Contrôles

```bash
git config core.hooksPath .githooks && git config pull.ff only   # une fois par clone
bash scripts/controles.sh --selftest   # les contrôles hors réseau, leurs selftests d'abord
python -m reuse lint
```

`scripts/controles.sh` porte **la** liste des contrôles hors réseau : le `pre-commit`
l'appelle, la CI aussi (`.github/workflows/ci.yml`, avec `reuse lint` et
`verifier-service.sh`, qui exige Docker). Les contrôles en ligne — la concordance du
site avec CoproFirst et ses apps, la version affichée — tournent à chaque poussée et
chaque jour (`comptes-demo.yml`, `version-produit.yml`) : ils sortent en
**2 (INCONNU)** si la source est injoignable, jamais en vert faute d'avoir comparé.
`verifier-depot.sh` refuse un `scripts/verifier-*` que rien ne lance.

## Licences

Le code est sous **AGPL-3.0-or-later**. Le **logo** n'est pas sous l'AGPL : il a sa
licence propre (`LICENSES/LicenseRef-CoproFirst-Logo.txt`), et la police **Fraunces**
la sienne (`LICENSES/OFL-1.1.txt`). « CoproFirst » fait
l'objet de la demande de marque n° 5307183. Le détail par fichier se lit dans
`REUSE.toml` et dans l'en-tête de chaque fichier.
