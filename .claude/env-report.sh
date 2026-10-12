#!/bin/bash
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# env-report.sh — rapport d'environnement injecté au démarrage de session.
# L'étiquette et la banque de mémoire découlent du répertoire de lancement, pas de
# la demande : une session ouverte ailleurs écrit ses mémoires au mauvais endroit
# (~/.claude/CLAUDE.md §3).
set -uo pipefail
ATTENDU="/c/Dev/CoproFirst-Site"
COURANT=$(pwd)
echo "═══════════════ ENVIRONNEMENT DE TRAVAIL ═══════════════"
echo "  Projet        : CoproFirst-Site (page d'accueil de CoproFirst — site statique)"
echo "  Étiquette     : CoproFirst-Site — <sujet>"
echo "  Répertoire    : $COURANT"
echo "  Dépôt/branche : $(git config --get remote.origin.url 2>/dev/null || echo 'aucun dépôt distant') [$(git branch --show-current 2>/dev/null)]"
echo "  Mémoire       : ~/.claude/projects/C--Dev-CoproFirst-Site/memory/"
echo "  Produit décrit: C:\\Dev\\5hostachy (CoproFirst) — vérifier chaque affirmation dans son README"
echo "  Écrans        : skill globale emil-design-eng, d'office"
if [ "${COURANT,,}" != "${ATTENDU,,}" ]; then
  echo "  ⚠️  RÉPERTOIRE INATTENDU (attendu $ATTENDU) — signale-le à l'utilisateur"
  echo "      AVANT d'agir : mémoires et étiquette partiront au mauvais endroit."
fi
echo "  → Reprends cette ligne en tête de ta 1ʳᵉ réponse."
echo "════════════════════════════════════════════════════════"
