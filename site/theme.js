// SPDX-FileCopyrightText: 2026 Philippe TRESSARD
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Le thème : SOMBRE par défaut, clair au choix. Chargé dans <head>, sans defer, pour
// que l'attribut data-theme soit posé avant le premier affichage (sinon un visiteur
// qui a choisi le clair verrait un éclair sombre à chaque page). Fichier séparé : la
// politique de sécurité du serveur (deploiement/Caddyfile) n'admet que les scripts
// du site.
//
// Le choix n'est mémorisé qu'à l'action du visiteur sur l'interrupteur, dans
// localStorage (clé « coprofirst-theme », sur son appareil, jamais envoyée) — dit dans
// confidentialite.html. Stockage interdit ou indisponible : le thème s'applique quand
// même, pour la page seulement.
(() => {
  const CLE = 'coprofirst-theme';
  const racine = document.documentElement;
  const lire = () => {
    try { const v = localStorage.getItem(CLE); return v === 'clair' || v === 'sombre' ? v : null; } catch { return null; }
  };
  // Idempotent : appelée au chargement, au clic et quand un autre onglet change le thème.
  const appliquer = (theme) => {
    racine.dataset.theme = theme;
    for (const b of document.querySelectorAll('[data-bascule-theme]')) b.setAttribute('aria-pressed', String(theme === 'sombre'));
  };

  appliquer(lire() || 'sombre');
  addEventListener('DOMContentLoaded', () => appliquer(racine.dataset.theme));
  // Délégué au document : le bouton n'existe pas encore quand ce script s'exécute.
  document.addEventListener('click', (e) => {
    if (!e.target.closest('[data-bascule-theme]')) return;
    const suivant = racine.dataset.theme === 'clair' ? 'sombre' : 'clair';
    appliquer(suivant);
    try { localStorage.setItem(CLE, suivant); } catch { /* le choix vaut pour cette page */ }
  });
  addEventListener('storage', (e) => { if (e.key === CLE) appliquer(lire() || 'sombre'); });
})();
