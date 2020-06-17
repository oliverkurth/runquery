#!/bin/sh

chown -R uwsgi /usr/var/query-instance/

exec "$@"

