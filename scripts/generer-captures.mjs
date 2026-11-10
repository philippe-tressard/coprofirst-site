// SPDX-FileCopyrightText: 2026 Philippe TRESSARD
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// generer-captures.mjs — photographie l'écran Affaires de la démonstration
// (demo.coprofirst.fr), sur ordinateur et sur téléphone, en thème clair ET sombre,
// pour le héros de l'accueil (qui montre celle du thème de la page : le site est
// sombre par défaut, un grand rectangle clair y faisait un saut de luminosité —
// coprofirst-site#33). Ce que montre la page est alors le produit lui-même,
// pas un dessin qui dérive de lui.
//
//   node scripts/generer-captures.mjs
//
// À relancer quand la démo a changé de version (elle suit sa vague, pas la
// dernière release : coprofirst#2210), puis
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
// Navigateur : Chrome, puis Edge, puis le Chromium que Playwright installe.
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const RACINE = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const SORTIE = join(RACINE, 'site', 'captures');
const DEMO = 'https://demo.coprofirst.fr';
// Le thème de l'application suit le cookie `theme` que l'application écrit elle-même
// (`sombre` → data-theme="dark" côté serveur) : plus sûr que d'émuler l'appareil, qui
// ne vaut que pour le mode Auto.
const APPAREILS = [
  { nom: 'ordinateur', viewport: { width: 1180, height: 740 }, mobile: false },
  { nom: 'telephone', viewport: { width: 390, height: 780 }, mobile: true },
];
const PRISES = APPAREILS.flatMap((a) => [
  { ...a, fichier: `affaires-${a.nom}.jpg`, sombre: false },
  { ...a, fichier: `affaires-${a.nom}-sombre.jpg`, sombre: true },
]);

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
  try { return await chromium.launch(); } catch { /* le Chromium de Playwright, s'il est installé */ }
  inconnu('ni Chrome, ni Edge, ni le Chromium de Playwright ne se lancent');
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
      locale: 'fr-FR', colorScheme: prise.sombre ? 'dark' : 'light', reducedMotion: 'reduce',
    });
    if (prise.sombre) await contexte.addCookies([{ name: 'theme', value: 'sombre', url: DEMO }]);
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
    const cette = await page.evaluate(() => document.querySelector('a[href*="/coprofirst/tree/"]')?.href.split('/tree/')[1] ?? null);
    // Les quatre prises montrent la MÊME version : la démo peut changer de version
    // entre deux d'entre elles (promotion de nuit), et le héros mélangerait deux états.
    if (version && cette !== version) throw new Error(`la démo a changé de version en cours de route (${version} puis ${cette})`);
    version ??= cette;
    // La capture doit montrer le thème demandé : un cookie ignoré donnerait deux
    // images identiques, sans que rien ne le dise.
    const theme = await page.evaluate(() => document.documentElement.dataset.theme ?? null);
    if ((theme === 'dark') !== prise.sombre) throw new Error(`${prise.fichier} : thème « ${theme} » au lieu de ${prise.sombre ? 'sombre' : 'clair'}`);
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
