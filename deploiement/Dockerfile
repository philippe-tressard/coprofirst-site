# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# L'image contient le site tel qu'il est dans le commit déployé : pas de volume,
# donc rien à modifier à la main sur le serveur. Caddy épinglé par version ET
# empreinte : un même Dockerfile reconstruit la même image.
FROM caddy:2.11.7-alpine@sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f
COPY deploiement/Caddyfile /etc/caddy/Caddyfile
# Un Caddyfile invalide arrête la construction de l'image : l'ancien conteneur
# continue alors de servir le site, au lieu d'un conteneur qui ne démarre pas.
RUN caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
COPY site/ /srv/
