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
//
// Seul script de toutes les pages, il porte aussi l'écouteur de toucher qui rend
// :active à Safari sur iOS (en fin de fichier).
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

  // La bascule au clic : toute la page change sur la même image. Les transitions
  // propres des boutons et des cartes sont coupées (data-bascule, commun.css), sinon
  // le fond change d'un coup et les contrôles 200 ms plus tard. Le passage du sombre
  // au clair se fait par un fondu de la page entière (View Transitions) ; sans elle,
  // d'un coup, mais d'un seul. data-bascule est retiré sur tous les chemins.
  const basculer = (theme) => {
    racine.setAttribute('data-bascule', '');
    const fin = () => racine.removeAttribute('data-bascule');
    try {
      if (document.startViewTransition) {
        document.startViewTransition(() => appliquer(theme)).finished.finally(fin);
        return;
      }
      appliquer(theme);
    } catch {
      appliquer(theme);
    }
    // Deux images : le nouveau thème est peint, sans transition, avant le retrait.
    requestAnimationFrame(() => requestAnimationFrame(fin));
  };

  appliquer(lire() || 'sombre');
  addEventListener('DOMContentLoaded', () => appliquer(racine.dataset.theme));
  // Délégué au document : le bouton n'existe pas encore quand ce script s'exécute.
  document.addEventListener('click', (e) => {
    if (!e.target.closest('[data-bascule-theme]')) return;
    const suivant = racine.dataset.theme === 'clair' ? 'sombre' : 'clair';
    basculer(suivant);
    try { localStorage.setItem(CLE, suivant); } catch { /* le choix vaut pour cette page */ }
  });
  addEventListener('storage', (e) => { if (e.key === CLE) appliquer(lire() || 'sombre'); });

  // Safari sur iOS n'applique :active (l'enfoncement des boutons, commun.css) que si
  // un écouteur de toucher existe : celui-ci, vide et passif, ne retient rien.
  addEventListener('touchstart', () => {}, { passive: true });
})();
