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
  afficherAvis();
});

// ── Avis d'utilisateurs (coprofirst-site#6) ─────────────────────────────────────
// avis.json est l'export de l'application, commité tel quel :
//   { "genere_le": "AAAA-MM-JJ", "avis": [ { titre, texte, note, auteur, role, date } ] }
// Un avis hors format, ou de plus de DUREE_MAX_ANS ans (la durée maximale annoncée
// par confidentialite.html#t-avis), est écarté ; sans aucun avis valide, la section
// reste masquée (jamais d'exemple à la place). Les mêmes règles refusent le fichier
// au déploiement : scripts/verifier-avis.py — l'un ne change pas sans l'autre.
// Le fichier n'est pas versionné : deploiement/deployer.sh l'envoie.
const NOTE_PUBLIABLE = 4;
const DUREE_MAX_ANS = 2;
const NOTE_MAX = 5;
const SECONDES_PAR_CARTE = 10;
const TEINTES = 4;

const rempli = (v) => typeof v === 'string' && v.trim() !== '';

// Le serveur ne retire rien seul : c'est l'affichage qui tient la durée maximale,
// même si le site n'a pas été redéployé depuis.
function encorePublie(jour) {
  const fin = new Date(jour);
  fin.setUTCFullYear(fin.getUTCFullYear() + DUREE_MAX_ANS);
  return Date.now() < fin.getTime();
}

function avisValide(a) {
  return a !== null && typeof a === 'object'
    && rempli(a.titre) && rempli(a.texte) && rempli(a.auteur)
    && (a.role === null || a.role === undefined || typeof a.role === 'string')
    && Number.isInteger(a.note) && a.note >= NOTE_PUBLIABLE && a.note <= NOTE_MAX
    && typeof a.date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(a.date) && !Number.isNaN(Date.parse(a.date)) && encorePublie(a.date);
}

// Texte posé par textContent, jamais par innerHTML : un avis est saisi par un tiers.
function el(balise, classe, texte) {
  const e = document.createElement(balise);
  if (classe) e.className = classe;
  if (texte !== undefined) e.textContent = texte;
  return e;
}

// « Alain G. » → « AG » ; « Jean-Pierre D. » → « JD ».
function initiales(nom) {
  const mots = nom.trim().split(/\s+/);
  return [mots[0], mots.length > 1 ? mots[mots.length - 1] : ''].map((m) => [...m][0] || '').join('').toUpperCase();
}

const DATE_LONGUE = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
// « 1er octobre » : Intl écrit « 1 octobre ».
const dateLongue = (jour) => DATE_LONGUE.formatToParts(new Date(jour))
  .map((p) => (p.type === 'day' && p.value === '1' ? '1er' : p.value)).join('');

function carteAvis(a, teinte, rang) {
  const carte = el('figure', 'postale');
  carte.dataset.teinte = teinte;
  const etoiles = el('p', 'etoiles', '★'.repeat(a.note));
  etoiles.setAttribute('role', 'img');
  etoiles.setAttribute('aria-label', `Note : ${a.note} sur ${NOTE_MAX}`);
  etoiles.append(el('span', '', '★'.repeat(NOTE_MAX - a.note)));
  const citation = el('blockquote');
  const texte = el('p', 'texte-avis', `« ${a.texte.trim()} »`);
  texte.id = `avis-texte-${rang}`;
  citation.append(el('p', 'titre-avis', a.titre.trim()), texte);
  const rond = el('span', 'rond', initiales(a.auteur));
  rond.setAttribute('aria-hidden', 'true');
  const qui = el('span');
  qui.append(el('b', '', a.auteur.trim()));
  if (rempli(a.role)) qui.append(el('span', 'sr', ' · '), a.role.trim());
  const date = el('time', '', `Avis du ${dateLongue(a.date)}`);
  date.dateTime = a.date;
  qui.append(el('span', 'sr', ' · '), date);
  const legende = el('figcaption');
  legende.append(rond, qui);
  carte.append(etoiles, citation, legende);
  return carte;
}

// « Lire la suite » : le texte est coupé à quelques lignes (CSS), et le bouton ne
// paraît que s'il déborde vraiment — mesuré une fois la carte affichée, puis à
// chaque redimensionnement. Seules les cartes lues en reçoivent un, jamais les
// copies de la boucle. Une carte dépliée met le défilement en pause (CSS :has).
function lireLaSuite(cartes) {
  for (const carte of cartes) {
    const texte = carte.querySelector('.texte-avis');
    let bouton = carte.querySelector('.lire-suite');
    const deborde = carte.classList.contains('deplie') || texte.scrollHeight > texte.clientHeight + 1;
    if (deborde && !bouton) {
      bouton = el('button', 'lire-suite', 'Lire la suite');
      bouton.type = 'button';
      bouton.setAttribute('aria-expanded', 'false');
      bouton.setAttribute('aria-controls', texte.id);
      bouton.addEventListener('click', () => {
        const deplie = carte.classList.toggle('deplie');
        bouton.setAttribute('aria-expanded', deplie);
        bouton.textContent = deplie ? 'Réduire' : 'Lire la suite';
        // Repliée, la carte raccourcit : si son haut est passé au-dessus de
        // l'écran, on le ramène en vue (verticalement seulement — la piste qui
        // défile ne doit pas bouger).
        const haut = carte.getBoundingClientRect().top;
        if (!deplie && haut < 0) scrollBy(0, haut - 96);
      });
      carte.querySelector('blockquote').after(bouton);
    } else if (!deborde && bouton) {
      bouton.remove();
    }
  }
}

async function afficherAvis() {
  const section = document.getElementById('avis');
  if (!section) return;
  let avis = [];
  try {
    const reponse = await fetch('avis.json', { cache: 'no-cache' });
    if (reponse.ok) {
      const donnees = await reponse.json();
      if (Array.isArray(donnees?.avis)) avis = donnees.avis.filter(avisValide);
    }
  } catch { /* injoignable ou illisible : rien à montrer, la section reste masquée */ }
  if (avis.length === 0) return;

  // L'ordre annoncé sous la section : du plus récent au plus ancien.
  avis.sort((x, y) => y.date.localeCompare(x.date));
  // Quatre teintes en rotation ; la dernière carte ne prend pas celle de la
  // première, qu'elle touche à la jonction de la boucle.
  const cartes = avis.map((a, i) => carteAvis(a, (i === avis.length - 1 && i % TEINTES === 0 && i > 0) ? 1 : i % TEINTES, i));
  // La boucle : une copie de chaque carte, cachée aux lecteurs d'écran.
  // inert : rien de focalisable dans une copie ; et pas d'id en double.
  const copies = cartes.map((c) => {
    const k = c.cloneNode(true);
    k.setAttribute('aria-hidden', 'true');
    k.inert = true;
    k.querySelectorAll('[id]').forEach((e) => e.removeAttribute('id'));
    return k;
  });
  const defile = section.querySelector('.defile');
  const piste = section.querySelector('.piste');
  piste.append(...cartes, ...copies);
  piste.style.setProperty('--duree', `${cartes.length * SECONDES_PAR_CARTE}s`);
  section.hidden = false;
  document.querySelectorAll('a[href="#avis"]').forEach((a) => { a.hidden = false; });

  // Immobile si les avis ne remplissent pas la largeur (la boucle montrerait un
  // trou) ou si le visiteur demande moins de mouvement. Le focus clavier ne sert
  // qu'à mettre en pause : sans défilement, la zone n'en prend pas.
  const reduit = matchMedia('(prefers-reduced-motion: reduce)');
  const ajuster = () => {
    const pas = cartes[0].offsetWidth + parseFloat(getComputedStyle(piste).columnGap || 0);
    const fixe = reduit.matches || cartes.length * pas <= defile.clientWidth;
    defile.classList.toggle('fixe', fixe);
    if (fixe) defile.removeAttribute('tabindex'); else defile.tabIndex = 0;
  };
  const ajusterTout = () => { ajuster(); lireLaSuite(cartes); };
  ajusterTout();
  addEventListener('resize', ajusterTout);
  reduit.addEventListener('change', ajuster);
}
