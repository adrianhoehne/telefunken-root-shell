#!/usr/bin/env bash
# Payload bauen, auf die SMB-Freigabe legen und die lokale Fallback-Kopie
# auf dem Fernseher aktualisieren.
#
#   bauen:     aurora.elf (Payload), logd (Logger), libkeyhook.so (Tasten-Hook)
#   Freigabe:  $SHARE (Standard: ~/rea/.../smb/share)
#   Fallback:  /conf/remotelf/ auf dem Fernseher (startet, wenn die Freigabe weg ist)
#
# Voraussetzung: Docker (fuer den ARM-Cross-Compiler), Fernseher eingeschaltet.
set -euo pipefail
cd "$(dirname "$0")"

SHARE="${SHARE:-$HOME/rea/projekte/telefunken-b43f545b/ergebnis/root-shell/smb/share}"
SMB_SERVER="${SMB_SERVER:-192.168.178.44}"
TVSH="$(cd "$(dirname "$0")/../scripts" && pwd)/tvsh.py"

echo "== 1. bauen =="
docker run --rm -v "$PWD:/work" ubuntu:24.04 bash -c '
  apt-get update -qq >/dev/null 2>&1
  apt-get install -y -qq gcc-arm-linux-gnueabihf >/dev/null 2>&1
  arm-linux-gnueabihf-gcc -shared -fPIC -O2 -o /work/libkeyhook.so /work/libkeyhook.c
  arm-linux-gnueabihf-gcc -static -Os -o /work/logd /work/logd.c
  arm-linux-gnueabihf-gcc -static -Os -o /work/aurora.elf /work/payload7.c
  arm-linux-gnueabihf-strip /work/libkeyhook.so /work/logd /work/aurora.elf
'

echo "== 2. auf die Freigabe kopieren =="
cp -f aurora.elf libkeyhook.so logd "$SHARE/"

echo "== 3. lokale Fallback-Kopie auf dem Fernseher aktualisieren =="
python3 "$TVSH" "
  cp -f /conf/remotelf/aurora.elf /conf/remotelf/libkeyhook.so /conf/remotelf/logd /tmp/ &&
  umount /conf/remotelf &&
  mkdir -p /conf/remotelf &&
  cp -f /tmp/aurora.elf /tmp/libkeyhook.so /tmp/logd /conf/remotelf/ &&
  mount -t cifs -o username=,password= //$SMB_SERVER/mb211cifs /conf/remotelf &&
  echo FALLBACK_OK
"

echo "fertig: gebaut, auf Freigabe, Fallback aktualisiert"
