#!/usr/bin/env bash
# Rebuild the minimal /conf (apdat0) UBIFS image that triggers the backdoor.
# Requires mtd-utils (Debian/Ubuntu: apt install mtd-utils).
#
# The image replaces /conf entirely. It contains only remote.txt and a
# friendly name. Everything else (settings, channel list, PlayReady/Netflix
# keys) is lost. Keep the original apdat0 dump as a fallback.
set -euo pipefail
cd "$(dirname "$0")"

rm -rf conf-neu
mkdir -p conf-neu
cp ../payload/remote.txt.example conf-neu/remote.txt
printf 'FriendlyName:TELEFUNKEN\n' > conf-neu/friendlyname.txt

# Geometry of the device: min I/O 4096, LEB 253952, 158 LEBs capacity, lzo.
mkfs.ubifs -r conf-neu -m 4096 -e 253952 -c 158 -x lzo -o conf_jb.ubifs

CRC=$(python3 -c "import zlib,sys;print('0x%08x'%(zlib.crc32(open('conf_jb.ubifs','rb').read())&0xffffffff))")
echo "conf_jb.ubifs built, size $(stat -c%s conf_jb.ubifs) (0x$(printf '%x' $(stat -c%s conf_jb.ubifs))), crc32 $CRC"
echo "Update the crc32 value in scripts/u-boot/probe_v20_write.scr to $CRC"
