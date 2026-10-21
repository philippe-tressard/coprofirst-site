// SPDX-FileCopyrightText: 2026 Philippe TRESSARD
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Maquette F : les comportements proposés (I2, I4, I5, I6, I11) et les réglages
// qui permettent de comparer (repères, thème sombre, entrée d'avant, aimantation).
document.documentElement.classList.add('js');

addEventListener('DOMContentLoaded', () => {
  const racine = document.documentElement;
  const reduit = matchMedia('(prefers-reduced-motion: reduce)');

  const obs = new IntersectionObserver((entrees) => {
    for (const e of entrees) if (e.isIntersecting) { e.target.classList.add('vu'); obs.unobserve(e.target); }
  }, { rootMargin: '0px 0px -60px 0px' });
  document.querySelectorAll('.revele').forEach((el, i) => { el.style.transitionDelay = (i % 3) * 40 + 'ms'; obs.observe(el); });

  // I11 : la fenêtre s'allume une fois l'entrée jouée — l'affaire est résolue.
  const scene = document.querySelector('.scene');
  let minuterie;
  function allumer() {
    clearTimeout(minuterie);
    scene.classList.remove('allumee');
    const delai = reduit.matches ? 0 : (racine.classList.contains('anim-avant') ? 1300 : 750);
    minuterie = setTimeout(() => scene.classList.add('allumee'), delai);
  }
  allumer();

  // I2 : le Sommaire. Échap ou un clic ailleurs le ferme ; le focus revient au bouton.
  const boutonSommaire = document.querySelector('.btn-sommaire');
  const menu = document.getElementById('menu-sommaire');
  const ouvrirMenu = (ouvert) => { menu.toggleAttribute('data-ferme', !ouvert); boutonSommaire.setAttribute('aria-expanded', ouvert); };
  boutonSommaire.addEventListener('click', () => ouvrirMenu(menu.hasAttribute('data-ferme')));
  menu.addEventListener('click', (e) => { if (e.target.closest('a')) ouvrirMenu(false); });
  addEventListener('keydown', (e) => { if (e.key === 'Escape' && !menu.hasAttribute('data-ferme')) { ouvrirMenu(false); boutonSommaire.focus(); } });
  addEventListener('click', (e) => { if (!e.target.closest('.sommaire')) ouvrirMenu(false); });

  // I4 : onglets du site (flèches, Début, Fin, couleur par clip-path), plus le
  // fondu du bord qui déborde et l'onglet choisi ramené en vue.
  const cadre = document.querySelector('.onglets-cadre');
  const onglets = [...cadre.querySelectorAll('.onglets:not(.copie) .onglet')];
  const copie = cadre.querySelector('.onglets.copie');
  const decouper = (o) => { copie.style.clipPath = `inset(6px ${copie.offsetWidth - o.offsetLeft - o.offsetWidth}px 6px ${o.offsetLeft}px round 99px)`; };
  const bords = () => {
    cadre.toggleAttribute('data-debut', cadre.scrollLeft <= 1);
    cadre.toggleAttribute('data-fin', cadre.scrollLeft + cadre.clientWidth >= cadre.scrollWidth - 1);
  };
  function activer(onglet, mode) {
    const section = document.getElementById('pour-qui');
    section.toggleAttribute('data-instant', mode !== 'souris');
    for (const o of onglets) {
      const actif = o === onglet;
      o.setAttribute('aria-selected', actif);
      o.tabIndex = actif ? 0 : -1;
      document.getElementById(o.getAttribute('aria-controls')).hidden = !actif;
    }
    decouper(onglet);
    const gauche = onglet.offsetLeft - (cadre.clientWidth - onglet.offsetWidth) / 2;
    cadre.scrollTo({ left: gauche, behavior: mode === 'souris' && !reduit.matches ? 'smooth' : 'auto' });
    if (mode === 'clavier') onglet.focus({ preventScroll: true });
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
  cadre.addEventListener('scroll', bords, { passive: true });
  addEventListener('resize', () => { copie.style.transition = 'none'; decouper(onglets.find((o) => o.tabIndex === 0)); copie.offsetWidth; copie.style.transition = ''; bords(); });
  decouper(onglets[0]);
  bords();

  // I5 : flèches et compteur du carrousel (les flèches ne paraissent qu'à la souris, CSS).
  const carrousel = document.querySelector('.carrousel');
  const cartes = [...carrousel.querySelectorAll('.carte-ia')];
  const compteur = document.querySelector('.compteur');
  const [precedent, suivant] = document.querySelectorAll('.fleche-c');
  const pas = () => cartes[1].offsetLeft - cartes[0].offsetLeft;
  let image;
  const majCarrousel = () => {
    image = null;
    const rang = Math.min(cartes.length, Math.round(carrousel.scrollLeft / pas()) + 1);
    compteur.textContent = `${rang} / ${cartes.length}`;
    precedent.disabled = carrousel.scrollLeft <= 1;
    suivant.disabled = carrousel.scrollLeft + carrousel.clientWidth >= carrousel.scrollWidth - 1;
  };
  carrousel.addEventListener('scroll', () => { image ??= requestAnimationFrame(majCarrousel); }, { passive: true });
  for (const b of [precedent, suivant]) b.addEventListener('click', () => carrousel.scrollBy({ left: Number(b.dataset.sens) * pas() }));
  majCarrousel();

  // Réglages de la maquette
  const heros = document.querySelector('.heros');
  const rejouer = () => { heros.classList.remove('entree'); heros.offsetWidth; heros.classList.add('entree'); allumer(); scrollTo({ top: 0 }); };
  const actions = {
    reperes: (oui) => racine.classList.toggle('sans-reperes', !oui),
    sombre: (oui) => (oui ? racine.setAttribute('data-theme', 'dark') : racine.removeAttribute('data-theme')),
    avant: (oui) => { racine.classList.toggle('anim-avant', oui); rejouer(); },
    aimant: (oui) => racine.classList.toggle('aimant', oui),
  };
  document.querySelectorAll('.reglages button').forEach((b) => b.addEventListener('click', () => {
    const quoi = b.dataset.reglage;
    if (quoi === 'rejouer') return rejouer();
    const oui = b.getAttribute('aria-pressed') !== 'true';
    b.setAttribute('aria-pressed', oui);
    actions[quoi](oui);
  }));
});
