// SPDX-FileCopyrightText: 2026 Philippe TRESSARD
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Page Démo : les boutons « Copier » des identifiants. Ils sont cachés dans le HTML
// et ne s'affichent que si le navigateur offre le presse-papiers ; sinon, chaque
// identifiant se sélectionne d'un clic (user-select: all). Fichier séparé : la
// politique de sécurité du serveur (deploiement/Caddyfile) n'admet que les scripts
// du site.
addEventListener('DOMContentLoaded', () => {
  if (!navigator.clipboard) return;
  const annonce = document.getElementById('annonce-copie');
  for (const bouton of document.querySelectorAll('.copier')) {
    const valeur = bouton.previousElementSibling;
    let minuterie;
    bouton.hidden = false;
    bouton.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(valeur.textContent.trim());
      } catch {
        // Presse-papiers refusé (permission, cadre intégré) : le texte est
        // sélectionné, il reste à le copier au clavier.
        getSelection().selectAllChildren(valeur);
        annonce.textContent = 'Copie refusée par le navigateur : le texte est sélectionné, copiez-le avec Ctrl+C.';
        return;
      }
      clearTimeout(minuterie);
      bouton.classList.add('fait');
      bouton.querySelector('span').textContent = 'Copié';
      annonce.textContent = `${bouton.dataset.quoi} copié.`;
      minuterie = setTimeout(() => {
        bouton.classList.remove('fait');
        bouton.querySelector('span').textContent = 'Copier';
      }, 1800);
    });
  }
});
