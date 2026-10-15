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
| `site/demo.html` | la page Démo : les comptes publics de la démonstration, repris de `api/app/demo/personnages.py` de CoproFirst |
| `site/mentions-legales.html`, `site/confidentialite.html` | les pages obligatoires |
| `site/commun.css`, `site/document.css`, `site/accueil.js`, `site/demo.js` | styles partagés, styles des pages de texte, scripts de l'accueil et de la page Démo |
| `site/logo.svg` | le logo de CoproFirst (licence propre, voir plus bas) |
| `site/robots.txt`, `site/sitemap.xml`, `site/llms.txt` | ce que lisent les moteurs de recherche et les assistants IA : tout le site leur est ouvert |
| `site/partage.png`, `site/apple-touch-icon.png` | l'image des aperçus de lien (Open Graph), l'icône des écrans d'accueil |
| `deploiement/` | le conteneur Caddy qui sert le site, et `deployer.sh` |
| `maquettes/` | les maquettes qui ont mené à la page, archivées telles quelles |
| `scripts/verifier-depot.sh` | encodage, fins de ligne, bits d'exécution, syntaxe des scripts |
| `scripts/verifier-referencement.py` | balises de tête (canonique, Open Graph, JSON-LD), sitemap, robots.txt, llms.txt — complets et cohérents |
| `scripts/generer-image-partage.sh` | refait `site/partage.png` à partir de `scripts/image-partage.html` |
| `scripts/signaler-indexnow.sh` | après un déploiement, annonce les pages du sitemap aux moteurs IndexNow (Bing…) — envoi à un tiers, à la main |
| `scripts/verifier-comptes-demo.py` | les comptes de `demo.html` sont-ils ceux de `personnages.py` de CoproFirst ? (CI, chaque jour) |

Pour voir le site : `python -m http.server -d site`, puis http://localhost:8000.

## Mise en ligne

Le site est servi sur **https://coprofirst.fr** par un conteneur Caddy
(`deploiement/`) sur une instance Oracle Cloud, derrière un tunnel Cloudflare.
`www.coprofirst.fr` redirige vers `coprofirst.fr`.

```bash
bash deploiement/deployer.sh             # déploie HEAD, une fois poussé
bash deploiement/deployer.sh --verifier  # compare ce qui est servi au dépôt
```

## Contrôles

```bash
git config core.hooksPath .githooks && git config pull.ff only
bash scripts/verifier-depot.sh --selftest
bash scripts/verifier-depot.sh
python -m reuse lint
python3 scripts/verifier-referencement.py --selftest
python3 scripts/verifier-referencement.py
python3 scripts/verifier-comptes-demo.py --selftest
python3 scripts/verifier-comptes-demo.py   # réseau : lit personnages.py sur GitHub
```

Le dernier contrôle ne tourne pas en pre-commit : il lit le dépôt de CoproFirst, où
naît la dérive, et la CI le lance chaque jour. Il sort en **2 (INCONNU)** si la
source est injoignable ou illisible — jamais en vert faute d'avoir comparé.

## Licences

Le code est sous **AGPL-3.0-or-later**. Le **logo** n'est pas sous l'AGPL : il a sa
licence propre (`LICENSES/LicenseRef-CoproFirst-Logo.txt`). « CoproFirst » fait
l'objet de la demande de marque n° 5307183. Le détail par fichier se lit dans
`REUSE.toml` et dans l'en-tête de chaque fichier.
