#!/bin/sh
# Ejecuta SysCheckup contra un portátil simulado. Los montajes viven en un
# espacio privado (unshare -m): el /sys real del equipo no se toca.
HERE=$(cd "$(dirname "$0")" && pwd)
exec unshare -m sh -c '
  for d in /sys/class /sys/bus /sys/module /sys/firmware; do mount -t tmpfs none "$d" || exit 1; done
  exec ${PYTHON:-python3} "$0/simular_portatil.py" "$@"' "$HERE" "$@"
