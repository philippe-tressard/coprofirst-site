#!/bin/bash
# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# env-report.sh — rapport d'environnement injecté au démarrage de session.
# L'étiquette et la banque de mémoire découlent du répertoire de lancement, pas de
# la demande : une session ouverte ailleurs écrit ses mémoires au mauvais endroit
# (~/.claude/CLAUDE.md §3).
#
# Le répertoire attendu, la banque de mémoire et l'emplacement de CoproFirst se
# lisent dans ~/.claude/projets.json, pour le poste courant (clé « macos » ou
# « windows ») : recopiés ici, ils annonçaient le chemin Windows sur le Mac et
# criaient « répertoire inattendu » à chaque session (05/11/2026). Registre
# illisible : INCONNU, jamais une alerte ni un silence de complaisance.
set -uo pipefail
COURANT=$(pwd)
REGISTRE=$(python3 - "$HOME/.claude/projets.json" <<'PY' 2>/dev/null
import json, os, sys
poste = "windows" if sys.platform.startswith(("win", "cygwin", "msys")) else "macos"
d = json.load(open(sys.argv[1], encoding="utf-8"))
projets = {p["nom"]: p for p in (d["projets"] if isinstance(d, dict) and "projets" in d else d)}
site, produit = projets["CoproFirst-Site"], projets["5Hostachy"]
attendu = site["repertoire"][poste]
# Python lit le répertoire courant sous la même forme que le registre (C:\… sous
# Windows, là où le pwd de Git Bash rend /c/…) : la comparaison se fait ici.
egal = os.path.normcase(os.path.realpath(os.getcwd())) == os.path.normcase(os.path.realpath(attendu))
print(attendu); print(site["memoire"]); print(produit["repertoire"][poste]); print("oui" if egal else "non")
PY
)
if [ -n "$REGISTRE" ]; then
  { read -r ATTENDU; read -r MEMOIRE; read -r PRODUIT; read -r ICI; } <<< "$REGISTRE"
else
  ATTENDU=""; MEMOIRE="INCONNU (~/.claude/projets.json illisible)"; PRODUIT="INCONNU"
fi
echo "═══════════════ ENVIRONNEMENT DE TRAVAIL ═══════════════"
echo "  Projet        : CoproFirst-Site (page d'accueil de CoproFirst — site statique)"
echo "  Étiquette     : CoproFirst-Site — <sujet>"
echo "  Répertoire    : $COURANT"
echo "  Dépôt/branche : $(git config --get remote.origin.url 2>/dev/null || echo 'aucun dépôt distant') [$(git branch --show-current 2>/dev/null)]"
echo "  Mémoire       : ~/.claude/projects/$MEMOIRE/memory/"
echo "  Produit décrit: $PRODUIT (CoproFirst) — vérifier chaque affirmation dans son README"
echo "  Écrans        : skill globale emil-design-eng, d'office"
if [ -z "$ATTENDU" ]; then
  echo "  ⚠️  RÉPERTOIRE : INCONNU (registre illisible) — vérifie-le avant d'agir."
elif [ "$ICI" != "oui" ]; then
  echo "  ⚠️  RÉPERTOIRE INATTENDU (attendu $ATTENDU) — signale-le à l'utilisateur"
  echo "      AVANT d'agir : mémoires et étiquette partiront au mauvais endroit."
fi
echo "  → Reprends cette ligne en tête de ta 1ʳᵉ réponse."
echo "════════════════════════════════════════════════════════"
