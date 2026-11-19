#!/usr/bin/env bash
set -eo pipefail
cd /work
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null 2>&1
apt-get install -y -qq gcc gcc-arm-linux-gnueabihf make wget tar gzip xz-utils >/dev/null 2>&1

# ncurses nur bauen, falls die Installation fehlt
if [ ! -d /work/ncurses-install/lib ]; then
  echo "== ncurses =="
  [ -d ncurses-6.4 ] || { wget -q https://invisible-mirror.net/archives/ncurses/ncurses-6.4.tar.gz && tar xzf ncurses-6.4.tar.gz; }
  cd ncurses-6.4
  [ -f Makefile ] || ./configure --host=arm-linux-gnueabihf --build=x86_64-linux-gnu --with-build-cc=gcc --prefix=/work/ncurses-install --enable-static --disable-shared --without-progs --without-tests --without-cxx --without-ada --without-manpages >/dev/null 2>&1
  make -j4 >/dev/null 2>&1
  make install >/dev/null 2>&1
  cd /work
  echo "ncurses OK"
fi

echo "== htop =="
cd /work
[ -d htop-3.5.3 ] || { wget -q https://github.com/htop-dev/htop/releases/download/3.5.3/htop-3.5.3.tar.xz && tar xJf htop-3.5.3.tar.xz; }
cd htop-3.5.3
CPPFLAGS="-I/work/ncurses-install/include" LDFLAGS="-L/work/ncurses-install/lib -static" \
  ./configure --host=arm-linux-gnueabihf --enable-static --disable-shared \
  --disable-unicode --disable-affinity --disable-delayacct >/dev/null 2>&1
make -j4 >/dev/null 2>&1
cp htop /out/htop
echo "htop BUILD OK"
