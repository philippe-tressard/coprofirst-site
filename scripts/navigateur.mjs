// SPDX-FileCopyrightText: 2026 Philippe TRESSARD
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// navigateur.mjs — le navigateur des scripts qui photographient (generer-captures.mjs,
// generer-image-partage.mjs). Module, pas commande.
//
// playwright-core vient de PLAYWRIGHT_CORE (chemin du paquet) ou, à défaut, du clone
// voisin de CoproFirst (5hostachy/front/node_modules/playwright-core), cherché à côté
// de ce clone et à côté du clone principal quand on travaille dans un worktree : ce site
// n'a pas de dépendance npm à lui. Navigateur : Chrome, puis Edge, puis le Chromium que
// Playwright installe — ce dernier suffit sur un poste sans Chrome (coprofirst-site#128).
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';

function clonePrincipal(racine) {
  try {
    const commun = execFileSync('git', ['rev-parse', '--path-format=absolute', '--git-common-dir'],
      { cwd: racine, encoding: 'utf8' }).trim();
    return dirname(commun);
  } catch { return racine; }
}

// chargerPlaywright(racine, inconnu) — le module playwright-core ; inconnu(message) sinon.
export function chargerPlaywright(racine, inconnu) {
  const candidats = process.env.PLAYWRIGHT_CORE ? [process.env.PLAYWRIGHT_CORE]
    : [racine, clonePrincipal(racine)].map((r) => resolve(r, '..', '5hostachy', 'front', 'node_modules', 'playwright-core'));
  const chemin = candidats.find((c) => existsSync(join(c, 'package.json')));
  if (!chemin) inconnu(`playwright-core introuvable (${candidats.join(', ')}) — variable PLAYWRIGHT_CORE`);
  return createRequire(join(chemin, 'package.json'))(chemin);
}

// lancer(chromium, inconnu) — Chrome, Edge, puis le Chromium de Playwright.
export async function lancer(chromium, inconnu) {
  for (const channel of ['chrome', 'msedge']) {
    try { return await chromium.launch({ channel }); } catch { /* essayer le suivant */ }
  }
  try { return await chromium.launch(); } catch { /* le Chromium de Playwright, s'il est installé */ }
  return inconnu('ni Chrome, ni Edge, ni le Chromium de Playwright ne se lancent');
}
