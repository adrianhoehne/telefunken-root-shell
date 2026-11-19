#!/usr/bin/env bash
# Build the static ARM payload for the remote.txt backdoor.
# Requires the cross-compiler (Debian/Ubuntu: apt install gcc-arm-linux-gnueabihf).
set -euo pipefail
cd "$(dirname "$0")"
arm-linux-gnueabihf-gcc -static -Os -o aurora.elf payload3.c
echo "built: aurora.elf"
