#!/bin/sh

chown -R uwsgi /usr/var/strava_query-instance/

exec "$@"

