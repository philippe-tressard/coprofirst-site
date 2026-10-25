// SPDX-FileCopyrightText: 2026 Philippe TRESSARD
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// generer-captures.mjs — photographie l'écran Affaires de la démonstration
// (demo.coprofirst.fr), sur ordinateur et sur téléphone, pour le héros de
// l'accueil. Ce que montre la page est alors le produit lui-même,
// pas un dessin qui dérive de lui.
//
//   node scripts/generer-captures.mjs
//
// À relancer après chaque version promue de CoproFirst, puis
// `python3 scripts/empreintes.py --ecrire` (l'adresse de chaque capture porte
// l'empreinte de son contenu, comme les CSS et JS) et committer les images.
//
// Le compte est celui que publie site/demo.html (Copropriétaire) : lu dans la page,
// jamais recopié ici — verifier-comptes-demo.py garde la page juste. Les données de
// la démo sont fictives.
//
// Il faut playwright-core et un Chrome ou un Edge installé. playwright-core est pris
// dans PLAYWRIGHT_CORE (chemin du paquet) ou, à défaut, dans le clone voisin de
// CoproFirst (../5hostachy/front/node_modules/playwright-core), qui l'installe pour
// ses tests de navigateur : ce site n'a pas de dépendance npm à lui.
// Sortie : 0 = images écrites ; 2 = INCONNU (outil absent, connexion refusée, écran
// introuvable) — aucune image n'est alors remplacée.
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const RACINE = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const SORTIE = join(RACINE, 'site', 'captures');
const DEMO = 'https://demo.coprofirst.fr';
const PRISES = [
  { fichier: 'affaires-ordinateur.jpg', viewport: { width: 1180, height: 740 }, mobile: false },
  { fichier: 'affaires-telephone.jpg', viewport: { width: 390, height: 780 }, mobile: true },
];

function inconnu(message) {
  console.error(`INCONNU : ${message} — aucune image remplacée`);
  process.exit(2);
}

// Le compte Copropriétaire publié par demo.html : les deux <code> de son bloc.
function compteDeLaPage() {
  const page = readFileSync(join(RACINE, 'site', 'demo.html'), 'utf8');
  const bloc = page.match(/<li class="compte" id="coproprietaire">([\s\S]*?)<\/li>/);
  const codes = bloc ? [...bloc[1].matchAll(/<code>([^<]+)<\/code>/g)].map((m) => m[1]) : [];
  if (codes.length !== 2) inconnu('demo.html : le compte Copropriétaire ne se lit plus (deux <code> attendus)');
  return { adresse: codes[0], motDePasse: codes[1] };
}

function chargerPlaywright() {
  const chemin = process.env.PLAYWRIGHT_CORE || resolve(RACINE, '..', '5hostachy', 'front', 'node_modules', 'playwright-core');
  if (!existsSync(join(chemin, 'package.json'))) inconnu(`playwright-core introuvable (${chemin}) — variable PLAYWRIGHT_CORE`);
  return createRequire(join(chemin, 'package.json'))(chemin);
}

async function lancer(chromium) {
  for (const channel of ['chrome', 'msedge']) {
    try { return await chromium.launch({ channel }); } catch { /* essayer le suivant */ }
  }
  inconnu('ni Chrome ni Edge ne se lancent');
}

const compte = compteDeLaPage();
const { chromium } = chargerPlaywright();
const navigateur = await lancer(chromium);
const images = [];
let version = null;
try {
  for (const prise of PRISES) {
    const contexte = await navigateur.newContext({
      viewport: prise.viewport, deviceScaleFactor: 2, isMobile: prise.mobile, hasTouch: prise.mobile,
      locale: 'fr-FR', colorScheme: 'light', reducedMotion: 'reduce',
    });
    const page = await contexte.newPage();
    await page.goto(`${DEMO}/auth/connexion`, { waitUntil: 'networkidle' });
    await page.fill('#email', compte.adresse);
    await page.fill('#password', compte.motDePasse);
    await Promise.all([page.waitForURL((u) => !u.pathname.startsWith('/auth/'), { timeout: 30000 }), page.click('button[type="submit"]')]);
    await page.goto(`${DEMO}/tickets`, { waitUntil: 'networkidle' });
    if (new URL(page.url()).pathname.startsWith('/auth/')) inconnu('connexion refusée par la démo');
    await page.waitForTimeout(800); // les polices et les pastilles finissent de se poser
    // La version photographiée : le pied de l'application renvoie au code de la
    // version en service (…/coprofirst/tree/vX.Y.Z). La démo se met à jour la nuit :
    // juste après une promotion, elle peut encore servir la précédente.
    version ??= await page.evaluate(() => document.querySelector('a[href*="/coprofirst/tree/"]')?.href.split('/tree/')[1] ?? null);
    images.push([prise.fichier, await page.screenshot({ type: 'jpeg', quality: 74 })]);
    await contexte.close();
  }
} catch (e) {
  await navigateur.close();
  inconnu(`la démo ne s'est pas laissée photographier (${e.message.split('\n')[0]})`);
}
await navigateur.close();
// Toutes les prises ou aucune : un héros à moitié mis à jour mélangerait deux versions.
mkdirSync(SORTIE, { recursive: true });
for (const [fichier, octets] of images) writeFileSync(join(SORTIE, fichier), octets);
console.log(`generer-captures : ${images.map(([f, o]) => `${f} (${Math.round(o.length / 1024)} Ko)`).join(', ')}`);
console.log(`version de la démo photographiée : ${version ?? 'INCONNUE (lien du pied introuvable)'}`);
