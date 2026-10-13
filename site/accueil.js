// SPDX-FileCopyrightText: 2026 Philippe TRESSARD
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Chargé dans <head>, sans defer : la classe .js doit être posée avant le premier
// affichage, sinon les éléments animés apparaissent puis disparaissent. Le reste
// attend que la page soit lue. Fichier séparé plutôt qu'en ligne : la politique de
// sécurité du serveur (deploiement/Caddyfile) n'admet que les scripts du site.
document.documentElement.classList.add('js');

addEventListener('DOMContentLoaded', () => {
  const obs = new IntersectionObserver((entrees) => {
    for (const e of entrees) if (e.isIntersecting) { e.target.classList.add('vu'); obs.unobserve(e.target); }
  }, { rootMargin: '0px 0px -60px 0px' });
  document.querySelectorAll('.revele').forEach((el, i) => { el.style.transitionDelay = (i % 3) * 50 + 'ms'; obs.observe(el); });

  // Onglets accessibles (flèches, Début, Fin) dont la couleur glisse par clip-path.
  // mode : 'souris' anime ; 'clavier' et 'init' sont instantanés (un geste au clavier ne s'anime pas).
  function initOnglets(racine, montrer = (panneau, actif) => { panneau.hidden = !actif; }) {
    const onglets = [...racine.querySelectorAll('.onglets:not(.copie) .onglet')];
    const copie = racine.querySelector('.onglets.copie');
    const decouper = (o) => { copie.style.clipPath = `inset(6px ${copie.offsetWidth - o.offsetLeft - o.offsetWidth}px 6px ${o.offsetLeft}px round 99px)`; };
    function activer(onglet, mode) {
      racine.toggleAttribute('data-instant', mode !== 'souris');
      for (const o of onglets) {
        const actif = o === onglet;
        o.setAttribute('aria-selected', actif);
        o.tabIndex = actif ? 0 : -1;
        montrer(document.getElementById(o.getAttribute('aria-controls')), actif);
      }
      decouper(onglet);
      if (mode === 'clavier') onglet.focus();
    }
    onglets.forEach((o, i) => {
      o.addEventListener('click', () => activer(o, 'souris'));
      o.addEventListener('keydown', (e) => {
        const cible = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: onglets.length - 1 }[e.key];
        if (cible === undefined) return;
        e.preventDefault();
        activer(onglets[(cible + onglets.length) % onglets.length], 'clavier');
      });
    });
    addEventListener('resize', () => { copie.style.transition = 'none'; decouper(onglets.find(o => o.tabIndex === 0)); copie.offsetWidth; copie.style.transition = ''; });
    decouper(onglets[0]);
    return { onglets, activer };
  }

  initOnglets(document.getElementById('pour-qui'));
});
