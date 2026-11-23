<!--
SPDX-FileCopyrightText: 2026 Philippe TRESSARD
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# CLAUDE.md — CoproFirst-Site

Ce fichier ne contient que l'instanciation CoproFirst-Site du socle commun
(`~/.claude/standards/`, routage : `~/.claude/CLAUDE.md` §1) : il ne le redit pas, il
y renvoie. Le détail de chaque contrôle est dans l'**en-tête de son script**.
**Toute modification d'écran suit la skill globale `emil-design-eng`** (demande du
12/10/2026).

## Après toute modification — les gestes que la CI exige

| Vous avez modifié… | Lancer, puis committer le résultat |
|---|---|
| un CSS, un JS ou une capture | `python3 scripts/empreintes.py --ecrire` (cache de 4 h de Cloudflare) |
| `site/index.html` (texte, empreinte, version) | `python3 scripts/contenu-accueil.py --ecrire` |
| une page | avancer son `lastmod` dans `site/sitemap.xml` |
| ajouté une page | la déclarer dans `sitemap.xml` et `llms.txt`, balises de tête recopiées d'une voisine |
| une couleur | `python3 scripts/verifier-css.py` (contrastes des quatre modes) |
| une phrase qui recopie un fait du produit | l'ajouter à `FAITS` (`verifier-faits-produit.py`) |
| une démo d'une autre version | `node scripts/generer-captures.mjs`, puis les empreintes |
| le gabarit de l'image de partage | `node scripts/generer-image-partage.mjs` |
| l'échéance de `security.txt` approche | `python3 scripts/verifier-security-txt.py --renouveler`, jamais à la main |

`scripts/controles.sh` porte la liste des contrôles hors réseau : le `pre-commit`
(`git config core.hooksPath .githooks`, une fois par clone) et la CI l'appellent ; la
CI y ajoute `reuse lint`, `verifier-service.sh` (Docker) et, chaque jour, la
concordance avec le produit et les apps (`comptes-demo.yml`). Un `scripts/verifier-*`
que rien ne lance est refusé ; ce fichier ne dépasse pas 10 000 octets
(`verifier-depot.sh`).

## Fusion et déploiement

Décisions de Philippe du 11/11/2026 (fusion, registre `fusion: claude`) et du 13/11/2026
(déploiement), confirmées le 18/11 : **je fusionne** les PR de ce dépôt —
celle du robot de version et celles de Dependabot comprises — dès que leurs checks
sont verts sur une tête à jour et qu'il n'y a pas de régression fonctionnelle, puis
**je déploie** (`bash deploiement/deployer.sh`, `--garder-avis` sans nouvel export des
avis) depuis le poste qui a la clé de l'instance, et je vérifie ce qui est servi
(`deployer.sh --verifier`, puis l'URL publique). Contrepartie : **compte rendu après**
(version, ce qui a changé). Restent à Philippe : une décision produit ou de
formulation commerciale, un export des avis à installer, un geste qu'un hook refuse.
Ne pas fermer puis rouvrir la PR « version » à la main : son défaut doit se voir
(`scripts/proposer-version.sh`). Jamais de geste à la main sur le serveur. La cible du
déploiement vit dans la configuration SSH du poste (alias `coprofirst-site`), jamais
dans ce dépôt public : sans l'alias, `deployer.sh` rend INCONNU.

## Tickets

Un ticket terminé se **ferme**, avec sa preuve en commentaire ; il n'est pas supprimé.
Un renvoi à un ticket de ce dépôt s'écrit `coprofirst-site#N` (`verifier-renvois.py`
refuse le dièse nu ; `--en-ligne` rend rouge un renvoi à un ticket supprimé).

## Le site

- **Statique**, sans dépendance ni build : `site/*.html` (accueil, démo, mentions
  légales, confidentialité, `supprimer-compte.html` — l'adresse exigée par Google Play —,
  `404.html`), feuilles `commun.css`, `document.css`, `accueil.css`, scripts
  `theme.js`, `accueil.js`, `demo.js`. Aucun script en ligne : la CSP n'admet que
  `'self'`. L'en-tête et le pied se recopient dans chaque page (`verifier-depot.sh`
  exige des pieds identiques).
- **Thème sombre par défaut**, clair au choix du visiteur, sans égard pour le thème du
  système (21/10/2026) : `theme.js`, chargé dans `<head>`, mémorisé dans `localStorage`
  (`coprofirst-theme`). Une surface s'écrit `var(--carte)`, un texte bleu `var(--lien)`,
  jamais `#fff` ni `--bleu` en dur.
- **Captures réelles** de la démo dans le héros, une par thème (la variante cachée est
  `loading="lazy"`). La démo suit sa vague de distribution : la version photographiée
  se lit au pied de l'application, que `generer-captures.mjs` affiche.
- **Version affichée** : la dernière release de CoproFirst, écrite par la PR « version »
  que le robot ouvre chaque heure (`version-produit.yml`) — jamais à la main.
- **Domaine** `coprofirst.fr` ; **contact public** `contact@coprofirst.fr` ; **démo**
  `demo.coprofirst.fr`, un sous-domaine (12/10/2026).
- **Hébergement** : Oracle Cloud (instance `coprofirst-demo`, Paris), conteneur Caddy
  sur `127.0.0.1:8080` derrière le tunnel Cloudflare ; le port 80 est à la démo. Le
  Caddyfile est validé à la construction de l'image et en CI, avec l'image lue au
  `FROM` du `Dockerfile` (sa seule écriture, que Dependabot monte).
- **Dépôt public**, AGPL-3.0-or-later (13/10/2026). Les commits portent l'adresse
  *noreply* de GitHub, réglée dans la configuration locale du clone (GH007).
- `maquettes/` : les propositions qui ont mené à la page (`E` retenue). Archives
  jamais servies : on ne les corrige pas.

## Ce qui est propre à ce projet

- **Le produit décrit est CoproFirst** (dépôt `philippe-tressard/coprofirst`, son
  répertoire dans `~/.claude/projets.json`) : toute affirmation sur une fonctionnalité
  se vérifie dans son `README.md` avant d'être écrite ici. Vocabulaire : « Bailleur
  (mandataire) » pour l'agence ou le gestionnaire, « Aidant » pour la délégation en
  lecture.
- **Marque** : « CoproFirst — demande de marque n° 5307183 », jamais ® tant qu'elle
  n'est pas enregistrée (`verifier-depot.sh`, `MARQUE_ENREGISTREE`). Le logo est sous
  `LicenseRef-CoproFirst-Logo`, hors de l'AGPL : il reste dans son fichier, jamais en
  ligne dans le HTML ; le texte de sa licence est celui de coprofirst, au paragraphe
  des fichiers couverts près (`verifier-licence-logo.py`) — il change là-bas.
- **Avis d'utilisateurs** : seulement l'export de l'onglet ⭐ Avis de l'application
  (`site/avis.json`, **jamais versionné** : un accord retiré ne survit pas dans
  l'historique public). `deployer.sh` installe seul le dernier export des
  Téléchargements puis l'efface, et refuse sans lui (`--garder-avis` reprend celui en
  ligne) — **redéployer après chaque export**. Sans avis valide, la section reste
  masquée, **jamais** d'exemple. Publication **deux ans** au plus après la date de
  l'avis ; un nom de résidence admis, le nom complet d'une personne non. La mention
  sous la section (L111-7-2, D111-17 du Code de la consommation) et
  `confidentialite.html#t-avis` disent comment ils sont choisis : les changer ensemble.
  Jamais balisés `Review` ni `AggregateRating` (avis choisis parmi les 4 et 5 étoiles,
  20/10/2026 ; `verifier-depot.sh` le refuse).
- **Le mot du créateur** (section IA de l'accueil) est écrit en dur dans `index.html`,
  **jamais** parmi les avis d'utilisateurs (`verifier-avis.py` refuse « Philippe T. »).
- **Aucune police externe, aucun traceur** : c'est ce qui dispense de bandeau
  (`standards/14` §4) ; un ajout rouvre la question. `verifier-depot.sh` lit pages,
  feuilles, scripts, SVG et la CSP du Caddyfile. Fraunces (OFL-1.1) est servie par le
  site (`site/polices/`).
- **Référencement** : ouvert à tous les robots, assistants IA compris (`robots.txt`,
  15/10/2026). ⚠️ Cloudflare sert aussi son propre `robots.txt` géré et peut bloquer
  les robots IA à la périphérie : cela se règle dans son tableau de bord.
- **Cloudflare, *Security Insights*** (22/10/2026) : réglés — double authentification,
  TLS 1.2 minimum, « Toujours utiliser HTTPS », DMARC `p=none`, `security.txt` ; une
  règle de transformation de la zone pose HSTS et `nosniff` sur
  `registre.coprofirst.fr`. **Refusés, à ne pas réactiver** : *Bot Fight Mode* (il
  défierait les instances qui s'inscrivent au registre, `deployer.sh --verifier` et
  `generer-captures.mjs`), *Labyrinthe IA*, *Turnstile* (aucun formulaire), HSTS de
  Cloudflare (Caddy et la démo envoient le leur). DKIM s'active chez OVH avant de
  passer DMARC en `quarantine`.
- **La démo** (ouverte le 14/10/2026) : trois comptes publics (CS, copropriétaire,
  locataire) publiés par `site/demo.html`, repris de `api/app/demo/personnages.py` de
  CoproFirst ; l'administrateur n'en est pas un. `verifier-comptes-demo.py` les
  compare chaque jour.
- **Les apps** lisent `site/contenu.json`, projection de `index.html` : un
  `data-contenu` ne se renomme ni ne se retire sans ticket dans coprofirst-ios et
  coprofirst-android (`CONTRAT_APP`). `confidentialite.html#t-application`, commune aux
  deux apps, est la politique que citent l'App Store et Google Play : une permission,
  une bibliothèque ou une montre ajoutée à une app la fait changer
  (`verifier-app-ios.py`, `verifier-app-android.py`).
- **Mentions légales** : éditeur particulier, **à titre non professionnel**, sans
  adresse publiée (LCEN, 13/10/2026 : l'hébergeur la connaît). Si CoproFirst devient
  une activité commerciale, l'adresse doit y figurer. Jamais l'adresse personnelle.
