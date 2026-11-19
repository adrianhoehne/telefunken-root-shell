#!/usr/bin/env python3
"""Sammelt Verzeichnislisten und Textdateien vom Fernseher über file://.

Chrome rendert geöffnete Dateien als Text; XHR auf file:// ist gesperrt, also
lassen sich nur Textdateien lesen, keine Binärdateien. Ergebnisse landen unter
artefacts/tv-fs/ mit '/' im Namen als '_'.

Aufruf:  dump_tv_files.py <pfad> [...]        Pfade, wie sie auf dem Gerät
                                              stehen ('/' für die Wurzel)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_fileread import Page, targets  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "artefacts", "tv-fs")


def main(paths):
    os.makedirs(OUT, exist_ok=True)
    page = Page(targets()[0])
    for path in paths:
        url = "file://" + path
        try:
            _, err = page.goto(url)
            if err:
                print(f"{path:28} ABGELEHNT ({err})")
                continue
            text = page.text()
        except Exception as exc:  # noqa: BLE001
            print(f"{path:28} FEHLER {exc}")
            continue
        name = path.strip("/").replace("/", "_") or "root"
        with open(os.path.join(OUT, name + ".txt"), "w", encoding="utf-8") as fh:
            fh.write(text)
        first = text.strip().splitlines()[:1]
        print(f"{path:28} {len(text):7} Zeichen  {first[0][:60] if first else ''}")


if __name__ == "__main__":
    main(sys.argv[1:])
