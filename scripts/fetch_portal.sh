#!/usr/bin/env bash
# Holt das Vestel-Portal (mb211.portaltv.tv) mit der Sitzung des Fernsehers
# nach artefacts/portal/, damit die Analyse offline und ohne Geraet laeuft.
#
# Voraussetzung: artefacts/portal-cookie.txt enthaelt den Cookie-Header
# ("Cookie: ...") aus scripts/cdp.py. Diese Datei ist Zugangsdatum und steht
# in .gitignore — niemals in Notizen oder Commits uebernehmen.
set -euo pipefail
cd "$(dirname "$0")/.."

HOST=http://mb211.portaltv.tv
OUT=artefacts/portal
COOKIE_FILE=artefacts/portal-cookie.txt
mkdir -p "$OUT"

if [[ ! -s $COOKIE_FILE ]]; then
  echo "fehlt: $COOKIE_FILE (Cookie-Header aus dem Geraet holen)" >&2
  exit 1
fi
COOKIE=$(cat "$COOKIE_FILE")

fetch() {  # fetch <pfad> <dateiname>
  local url="$HOST$1" name="$2"
  local code
  code=$(curl -sS -m 20 -H "$COOKIE" -o "$OUT/$name" -w '%{http_code}' "$url")
  printf '%-10s %6s  %s\n' "$code" "$(wc -c <"$OUT/$name")" "$1"
}

fetch /advgallery/main.aspx                        main.html
fetch /advgallery/js/Main/Init.js                  Init.js
fetch /advgallery/js/Main/Starter2.js              Starter2.js
fetch /advgallery/js/Main/Navigation2.js           Navigation2.js
fetch /advgallery_mb120/js/AppManager.js           AppManager.js
fetch /advgallery_mb120/js/Main/Core2.js           Core2.js
fetch /advgallery/js/AppSettingsManager.js         AppSettingsManager.js
fetch /advgallery/js/TopMenuManager.js             TopMenuManager.js
fetch /advgallery/js/Main/BrandCustomization.js    BrandCustomization.js
fetch /js/Ajaxer.js                                Ajaxer.js
fetch /js/Keys.js                                  Keys.js
fetch /gallery/GalleryService.asmx/GetServerTime   GetServerTime.xml
fetch '/gallery/UpdateWidgetMainPage.ashx?appId=217&index=0&init=true' WidgetMainPage.xml
fetch '/allow/Getresource.ashx?name=NewUISplash'    NewUISplash.txt
