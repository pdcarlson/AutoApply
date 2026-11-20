#!/bin/sh
# Starts as root only to hand the mounted volume to the unprivileged user, then drops to it:
# the server and the browsers it launches never run as root.
set -e
DATA_DIR="${AUTOAPPLY_DATA_DIR:-/data}"
mkdir -p "$DATA_DIR"
if [ "$(id -u)" = "0" ]; then
    chown -R app:app "$DATA_DIR"
    exec setpriv --reuid=app --regid=app --init-groups env HOME=/home/app "$@"
fi
exec "$@"
