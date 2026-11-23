# SPDX-FileCopyrightText: 2026 Philippe TRESSARD
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# L'image contient le site tel qu'il est dans le commit déployé : pas de volume,
# donc rien à modifier à la main sur le serveur. Caddy épinglé par version ET
# empreinte : un même Dockerfile reconstruit la même image.
FROM caddy:2.11.9-alpine@sha256:003a97808e781aa9f7e75cc2f43d34d461099031faf5e20faefb9f61126836f0
COPY deploiement/Caddyfile /etc/caddy/Caddyfile
# Un Caddyfile invalide arrête la construction de l'image : l'ancien conteneur
# continue alors de servir le site, au lieu d'un conteneur qui ne démarre pas.
RUN caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
COPY site/ /srv/
