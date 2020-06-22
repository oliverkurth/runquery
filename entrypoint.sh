#!/bin/sh

chown -R uwsgi /usr/var/runquery-instance/

exec "$@"

