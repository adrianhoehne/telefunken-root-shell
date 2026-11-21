#!/usr/bin/env python3
"""Befehl auf dem Fernseher per Telnet (Port 23) ausführen und Ausgabe zeigen.

Aufruf:  tvsh.py "<befehl>"
Umgebung: TV_IP (Standard 192.168.178.79), TV_PORT (Standard 23)

Der Fernseher muss eingeschaltet sein. Die Shell ist root.
"""
import socket, time, sys, os

HOST = os.environ.get("TV_IP", "192.168.178.79")
PORT = int(os.environ.get("TV_PORT", "23"))


def run(cmd, wait=3.0):
    last = ""
    for attempt in range(3):
        s = socket.socket()
        s.settimeout(10)
        try:
            s.connect((HOST, PORT))
            time.sleep(0.8)
            s.sendall(cmd.encode() + b"\r\n")
            time.sleep(wait)
            d = b""
            try:
                while True:
                    x = s.recv(8192)
                    if not x:
                        break
                    d += x
            except socket.timeout:
                pass
            s.close()
            out = d.decode(errors="replace")
            # Telnet-IAC- und sonstige Steuerbytes entfernen, Text behalten
            out = "".join(c for c in out if c == "\n" or c == "\t" or ord(c) >= 32)
            if out.strip():
                return out
            last = out
        except (OSError, socket.timeout):
            time.sleep(1)
    return last


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.stdout.write(run(sys.argv[1]))
