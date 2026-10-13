<!--
SPDX-FileCopyrightText: 2026 Philippe TRESSARD
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# CoproFirst — le site

La page d'accueil de [CoproFirst](https://github.com/philippe-tressard/coprofirst),
l'application libre de gestion de copropriétés : ce qu'elle fait, pour qui, son
assistant IA facultatif, une démonstration en ligne et le lien vers son code.

Destinée à **coprofirst.fr** ; la démonstration sera sur **demo.coprofirst.fr**.

## Contenu

| Chemin | Rôle |
|---|---|
| `site/index.html` | la page d'accueil — HTML et CSS, sans dépendance ni build |
| `site/mentions-legales.html`, `site/confidentialite.html` | les pages obligatoires |
| `site/commun.css`, `site/document.css`, `site/accueil.js` | styles partagés, styles des pages de texte, script de l'accueil |
| `site/logo.svg` | le logo de CoproFirst (licence propre, voir plus bas) |
| `deploiement/` | le conteneur Caddy qui sert le site, et `deployer.sh` |
| `maquettes/` | les maquettes qui ont mené à la page, archivées telles quelles |
| `scripts/verifier-depot.sh` | encodage, fins de ligne, bits d'exécution, syntaxe des scripts |

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
```

## Licences

Le code est sous **AGPL-3.0-or-later**. Le **logo** n'est pas sous l'AGPL : il a sa
licence propre (`LICENSES/LicenseRef-CoproFirst-Logo.txt`). « CoproFirst » fait
l'objet de la demande de marque n° 5307183. Le détail par fichier se lit dans
`REUSE.toml` et dans l'en-tête de chaque fichier.
