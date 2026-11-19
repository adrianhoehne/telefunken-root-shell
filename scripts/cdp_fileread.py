#!/usr/bin/env python3
"""Liest Textdateien vom Fernseher über die Chromium-Fernwartung (Port 4725).

Vorgehen: eine bereits offene Seite wird per Page.navigate auf eine
file://-Adresse umgelenkt; danach wird der gerenderte Text ausgelesen. Ob die
Browser-Shell file:// überhaupt zulässt, zeigt der erste Aufruf.

Aufruf:
  cdp_fileread.py /proc/version [/proc/mounts ...]
  cdp_fileread.py --list            nur die vorhandenen Ziele zeigen
"""
import argparse
import json
import sys
import time
import urllib.request

import websocket

HOST = "192.168.0.0"  # TODO: set TV IP
PORT = 4725


def targets():
    with urllib.request.urlopen(f"http://{HOST}:{PORT}/json/list", timeout=5) as r:
        return json.load(r)


class Page:
    def __init__(self, target):
        self.ws = websocket.create_connection(
            target["webSocketDebuggerUrl"], timeout=20, suppress_origin=True
        )
        self.n = 0

    def call(self, method, params=None):
        self.n += 1
        mid = self.n
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})

    def goto(self, url):
        self.call("Page.enable")
        res = self.call("Page.navigate", {"url": url})
        if res.get("errorText"):
            return None, res["errorText"]
        # Laden abwarten: bis document.readyState == complete oder Zeitgrenze
        for _ in range(40):
            time.sleep(0.15)
            try:
                r = self.call("Runtime.evaluate", {"expression": "document.readyState", "returnByValue": True})
                if r.get("result", {}).get("value") == "complete":
                    break
            except RuntimeError:
                pass
        return res, None

    def text(self):
        for expr in ("document.body ? document.body.innerText : ''",
                     "document.documentElement.innerText",
                     "document.documentElement.outerHTML"):
            r = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True})
            val = r.get("result", {}).get("value")
            if val:
                return val
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    ts = targets()
    if args.list or not ts:
        for t in ts:
            print(f"{t['id']}  {t['type']:6} {t['title']!r} {t['url'][:70]}")
        if not ts:
            sys.exit("keine Seite offen — am Fernseher Portal oder HbbTV starten")
        if args.list:
            return

    page = Page(ts[0])
    for path in args.paths:
        url = "file://" + path
        res, err = page.goto(url)
        if err:
            print(f"### {path}: Navigation abgelehnt ({err})")
            continue
        content = page.text()
        print(f"### {path} — {len(content)} Zeichen")
        print(content[:4000].strip())
        print()


if __name__ == "__main__":
    main()
