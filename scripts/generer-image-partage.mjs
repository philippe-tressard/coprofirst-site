// SPDX-FileCopyrightText: 2026 Philippe TRESSARD
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// generer-image-partage.mjs — photographie scripts/image-partage.html en
// site/partage.png (1200 × 630), l'image que montrent les réseaux sociaux et les
// messageries (balises og:image et twitter:image des pages du site).
//
//   node scripts/generer-image-partage.mjs                   écrit site/partage.png
//   node scripts/generer-image-partage.mjs --sortie FICHIER  écrit ailleurs (essai)
//
// À relancer quand le gabarit change, puis committer l'image. Il faut playwright-core
// et un navigateur (scripts/navigateur.mjs, comme generer-captures.mjs) ; la typographie
// est celle du poste, comme pour un visiteur du site : l'image ne se reconstruit pas à
// l'octet près ailleurs. Il remplace generer-image-partage.sh, qui ne trouvait sur le
// Mac ni navigateur ni Pillow (coprofirst-site#128) : le cadre de 1200 × 630 est ici
// la taille de la page photographiée, sans recadrage.
// Sortie : 0 = image écrite et mesurée ; 1 = image fausse ; 2 = INCONNU (outil absent).
import { writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { chargerPlaywright, lancer } from './navigateur.mjs';

const RACINE = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const LARGEUR = 1200;
const HAUTEUR = 630;
const i = process.argv.indexOf('--sortie');
const sortie = i > 0 ? resolve(process.argv[i + 1]) : join(RACINE, 'site', 'partage.png');

function inconnu(message) {
  console.error(`INCONNU : ${message} — aucune image écrite`);
  process.exit(2);
}

const { chromium } = chargerPlaywright(RACINE, inconnu);
const navigateur = await lancer(chromium, inconnu);
let octets;
try {
  const page = await navigateur.newPage({ viewport: { width: LARGEUR, height: HAUTEUR }, deviceScaleFactor: 1 });
  await page.goto(pathToFileURL(join(RACINE, 'scripts', 'image-partage.html')).href, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  octets = await page.screenshot({ type: 'png' });
} finally {
  await navigateur.close();
}
// Le contrôle porte sur le résultat : l'en-tête PNG dit la taille (IHDR, octets 16 à 23).
const [l, h] = [octets.readUInt32BE(16), octets.readUInt32BE(20)];
if (l !== LARGEUR || h !== HAUTEUR) {
  console.error(`ÉCHEC : image de ${l}x${h}, attendu ${LARGEUR}x${HAUTEUR} — rien d'écrit`);
  process.exit(1);
}
writeFileSync(sortie, octets);
console.log(`${sortie} : ${l}x${h}, ${octets.length} octets`);
