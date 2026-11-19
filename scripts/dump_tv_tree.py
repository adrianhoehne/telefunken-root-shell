#!/usr/bin/env python3
"""Vollständiger Abzug des Fernseher-Dateisystems, soweit er über den Browser geht.

Was der Browser hergibt:
  * Verzeichnislisten für JEDES Verzeichnis (Name, Größe, Datum)  → vollständige Inventur
  * Inhalte von Textdateien                                        → echter Dateiinhalt
Was nicht geht:
  * Binärdateien (Chrome lädt sie herunter, statt sie anzuzeigen)

Deshalb wird für Binärdateien bewusst KEINE Navigation ausgelöst — das würde auf
dem Fernseher Downloads erzeugen und Platz verbrauchen. Sie stehen nur in der
Inventur.

Ergebnis:
  artefacts/tv-dump/inventar.tsv     eine Zeile je Eintrag
  artefacts/tv-dump/dateien/<pfad>   Inhalt der lesbaren Textdateien

Aufruf:  dump_tv_tree.py [--dirs N] [--files N]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_fileread import Page, targets  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "artefacts", "tv-dump"))

TEXT_EXT = {
    "sh", "ini", "txt", "xml", "htm", "html", "js", "css", "lst", "conf",
    "cfg", "version", "json", "log", "md", "bat", "sdp", "dtd", "xsl",
    "scc", "inf", "crt", "pem", "properties", "csv", "map",
}
# Nicht betreten: virtuelle Dateisysteme und Wechselmedien
SKIP_DIRS = {"/proc", "/sys", "/dev", "/media", "/mnt", "/nvtpipe"}

LIST_JS = """
(function(){
  var rows=[], trs=document.querySelectorAll('table tr');
  for (var i=0;i<trs.length;i++){
    var c=trs[i].children;
    if(c.length<3) continue;
    var name=(c[0].innerText||'').trim();
    if(!name || name.indexOf('[parent')===0) continue;
    var isDir = name.charAt(name.length-1)==='/';
    rows.push({name:name.replace(/\\/$/,''), dir:isDir,
               size:(c[1].innerText||'').trim(), date:(c[2].innerText||'').trim()});
  }
  if(rows.length===0){
    var lines=(document.body?document.body.innerText:'').split('\\n').slice(1);
    for(var j=0;j<lines.length;j++){
      var p=lines[j].split('\\t');
      if(p.length<3 || !p[0] || p[0].indexOf('[parent')===0) continue;
      rows.push({name:p[0].replace(/\\/$/,''), dir:p[0].slice(-1)==='/',
                 size:p[1]||'', date:p[2]||''});
    }
  }
  return JSON.stringify(rows);
})()
"""


def evaluate(page, expr):
    r = page.call("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    return r.get("result", {}).get("value")


def list_dir(page, path):
    url = "file://" + (path if path.endswith("/") else path + "/")
    _, err = page.goto(url)
    if err:
        return []
    raw = evaluate(page, LIST_JS) or "[]"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def read_text(page, path):
    """Gibt Inhalt zurück, oder None wenn der Browser die Datei nicht anzeigt."""
    url = "file://" + path
    _, err = page.goto(url)
    if err:
        return None
    # Bei einem Download bleibt die alte Adresse stehen — das ist das Signal.
    still = evaluate(page, "location.href")
    if still != url:
        return None
    return page.text()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", type=int, default=400)
    ap.add_argument("--files", type=int, default=500)
    args = ap.parse_args()

    os.makedirs(os.path.join(OUT, "dateien"), exist_ok=True)
    ts = targets()
    ziel = next((t for t in ts if not t["url"].startswith("chrome")), ts[0])
    print("Ziel:", ziel["title"], ziel["url"][:60], flush=True)
    page = Page(ziel)
    inventar = open(os.path.join(OUT, "inventar.tsv"), "w", encoding="utf-8")
    inventar.write("pfad\ttyp\tgroesse\tdatum\tinhalt\n")

    queue = ["/"]
    seen = set()
    n_dirs = n_files = n_text = 0
    t0 = time.time()

    try:
        while queue and n_dirs < args.dirs:
            path = queue.pop(0)
            if path in seen or path in SKIP_DIRS:
                continue
            seen.add(path)
            n_dirs += 1
            entries = list_dir(page, path)
            print(f"[{n_dirs:3}] {path} — {len(entries)} Einträge", flush=True)
            for e in entries:
                full = path.rstrip("/") + "/" + e["name"]
                if e["dir"]:
                    inventar.write(f"{full}/\tdir\t\t{e['date']}\t\n")
                    inventar.flush()
                    if full not in seen and full not in SKIP_DIRS:
                        queue.append(full)
                    continue
                n_files += 1
                ext = e["name"].rsplit(".", 1)[-1].lower() if "." in e["name"] else ""
                if ext in TEXT_EXT and n_text < args.files:
                    text = read_text(page, full)
                    if text is not None:
                        n_text += 1
                        inhalt = "text"
                        ziel = os.path.join(OUT, "dateien", full.strip("/").replace("/", "__"))
                        with open(ziel, "w", encoding="utf-8") as fh:
                            fh.write(text)
                    else:
                        inhalt = "nicht lesbar"
                else:
                    inhalt = "binär (nicht abgezogen)"
                inventar.write(f"{full}\tdatei\t{e['size']}\t{e['date']}\t{inhalt}\n")
                inventar.flush()
    except Exception as exc:  # noqa: BLE001 — Verbindungsverlust darf den Abzug nicht wegwerfen
        print(f"\nAbgebrochen: {type(exc).__name__}: {exc}", flush=True)
        print("Bisher Erhobenes ist gespeichert.", flush=True)

    inventar.close()
    print(f"\nFertig: {n_dirs} Verzeichnisse, {n_files} Dateien, {n_text} Textinhalte, "
          f"{time.time()-t0:.0f}s")
    print(f"Inventur: {os.path.join(OUT, 'inventar.tsv')}")


if __name__ == "__main__":
    main()
