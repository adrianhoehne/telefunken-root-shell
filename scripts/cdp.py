#!/usr/bin/env python3
"""Minimaler Chrome-DevTools-Protokoll-Client fuer den Vestel-SmartTV.

Das Geraet bietet auf TCP 4725 eine Chromium-Fernwartung an
("Content shell remote debugging"). Dieses Skript spricht sie direkt an.

Aufrufe:
  cdp.py targets                      Ziele (Seiten) auflisten
  cdp.py eval '<js>' [--id ID]        JavaScript auf der Seite auswerten
  cdp.py net [--seconds N] [--id ID]  Netzwerkverkehr live mitlesen
  cdp.py nav <url> [--id ID]          Seite navigieren (veraendert das Geraet!)
  cdp.py shot <datei.png> [--id ID]   Screenshot der laufenden Seite

Ohne --id wird das Ziel "Portal TV" genommen.
"""
import argparse
import json
import sys
import time

import websocket  # websocket-client

HOST = "192.168.0.0"  # TODO: set TV IP
PORT = 4725


def http_json(path):
    import urllib.request

    with urllib.request.urlopen(f"http://{HOST}:{PORT}{path}", timeout=5) as r:
        return json.load(r)


def pick_target(target_id=None):
    targets = http_json("/json/list")
    if target_id:
        for t in targets:
            if t["id"] == target_id:
                return t
        sys.exit(f"Ziel {target_id} nicht gefunden")
    for t in targets:
        if "map" not in t["url"].lower() and t["type"] == "page":
            return t
    return targets[0]


def connect(target):
    ws = websocket.create_connection(
        target["webSocketDebuggerUrl"],
        timeout=15,
        suppress_origin=True,
        header=["Origin: http://localhost"],
    )
    return ws


class CDP:
    def __init__(self, ws):
        self.ws = ws
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

    def events(self, seconds, stop_on=None):
        end = time.time() + seconds
        self.ws.settimeout(1.0)
        while time.time() < end:
            try:
                msg = json.loads(self.ws.recv())
            except websocket.WebSocketTimeoutException:
                continue
            yield msg
            if stop_on and msg.get("method") == stop_on:
                return


def cmd_targets(_args):
    for t in http_json("/json/list"):
        print(f"{t['id']}  {t['type']:8}  {t['title']!r}\n    {t['url']}")


def cmd_eval(args):
    target = pick_target(args.id)
    conn = CDP(connect(target))
    expr = args.js
    res = conn.call(
        "Runtime.evaluate",
        {"expression": expr, "returnByValue": True, "awaitPromise": True},
    )
    if "exceptionDetails" in res:
        print(json.dumps(res["exceptionDetails"], indent=2, ensure_ascii=False))
        return
    value = res.get("result", {}).get("value")
    if isinstance(value, (dict, list)):
        print(json.dumps(value, indent=2, ensure_ascii=False))
    else:
        print(value)


def fmt_request(ev, rid):
    req = rid.get(ev["requestId"], {})
    return req.get("request", {}), req.get("type", "?")


def cmd_net(args):
    target = pick_target(args.id)
    conn = CDP(connect(target))
    conn.call("Network.enable", {"maxTotalBufferSize": 1 << 20})
    reqs = {}
    print(f"# Netzwerk von {target['title']!r} — {args.seconds}s", file=sys.stderr)
    t0 = time.time()
    for msg in conn.events(args.seconds):
        m = msg.get("method")
        p = msg.get("params", {})
        if m == "Network.requestWillBeSent":
            r = p["request"]
            reqs[p["requestId"]] = r
            print(f"[{time.time()-t0:6.1f}s] >> {p.get('type','?'):10} {r['method']:4} {r['url']}")
        elif m == "Network.responseReceived":
            r = p["response"]
            print(f"[{time.time()-t0:6.1f}s] << {p.get('type','?'):10} {r['status']:3} {r['url'][:160]}")
        elif m == "Network.loadingFailed":
            print(f"[{time.time()-t0:6.1f}s] !! {p.get('errorText')} {reqs.get(p['requestId'],{}).get('url','')[:120]}")


def cmd_shot(args):
    """Screenshot der laufenden Seite (Page.captureScreenshot)."""
    import base64

    target = pick_target(args.id)
    conn = CDP(connect(target))
    res = conn.call("Page.captureScreenshot", {"format": "png"})
    with open(args.file, "wb") as fh:
        fh.write(base64.b64decode(res["data"]))
    print(f"geschrieben: {args.file}")


def cmd_nav(args):
    target = pick_target(args.id)
    conn = CDP(connect(target))
    conn.call("Page.enable")
    res = conn.call("Page.navigate", {"url": args.url})
    print(json.dumps(res, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", default=None, help="Ziel-ID (aus 'targets')")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("targets")
    e = sub.add_parser("eval")
    e.add_argument("js")
    n = sub.add_parser("net")
    n.add_argument("--seconds", type=float, default=20)
    v = sub.add_parser("nav")
    v.add_argument("url")
    s = sub.add_parser("shot")
    s.add_argument("file")
    args = ap.parse_args()
    {
        "targets": cmd_targets,
        "eval": cmd_eval,
        "net": cmd_net,
        "nav": cmd_nav,
        "shot": cmd_shot,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
