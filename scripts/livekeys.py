#!/usr/bin/env python3
"""Live-Anzeige der Fernbedienungs-Tasten.

Pollt /tmp/keylog.bin (vom LD_PRELOAD-Hook geschrieben) jede Sekunde und gibt
neu gedrückte Tasten sofort aus. Läuft auf dem Rechner, verbindet sich per
Telnet (Port 23) zum Fernseher.

Aufruf: livekeys.py [sekunden]
"""
import socket, time, base64, re, sys

HOST = '192.168.178.79'
PORT = 23

KEYS = {
    0x41: '1', 0x42: '2', 0x43: '3', 0x44: '4', 0x45: '5',
    0x46: '6', 0x47: '7', 0x48: '8', 0x49: '9', 0x40: '0',
    0x55: 'LINKS', 0x56: 'RECHTS', 0x54: 'HOCH', 0x53: 'RUNTER',
    0x60: 'KANAL+', 0x61: 'KANAL-',
    0x50: 'VOL-', 0x51: 'VOL+',
    0x75: 'OK', 0x70: 'MENÜ', 0x78: 'QUELLE',
    0x5f: 'UNTERTITEL', 0x7c: 'TEXT',
    0x77: 'ROT', 0x76: 'GRÜN', 0x72: 'GELB', 0x74: 'BLAU',
    0x58: 'STOP', 0x59: 'PLAY', 0x71: 'PAUSE',
    0x5b: 'ZURÜCK', 0x5c: 'VOR', 0x4c: 'STANDBY',
}


def telnet(cmd, wait=1.5):
    s = socket.socket(); s.settimeout(6)
    s.connect((HOST, PORT))
    time.sleep(0.8)
    s.sendall(cmd.encode() + b'\r\n')
    time.sleep(wait)
    d = b''
    try:
        while True:
            x = s.recv(8192)
            if not x: break
            d += x
    except socket.timeout:
        pass
    s.close()
    return d.decode(errors='replace')


def read_from(offset):
    out = telnet(f'tail -c +{offset + 1} /tmp/keylog.bin | base64')
    b64 = ''.join(re.findall(r'[A-Za-z0-9+/=]{20,}', out))
    if not b64:
        return b'', offset
    try:
        data = base64.b64decode(b64)
    except Exception:
        return b'', offset
    return data, offset + len(data)


def events(data):
    for part in data.split(b'\xff\xff'):
        p = part[:7]
        if len(p) < 7:
            continue
        if p[0] == 0x8B and p[6] == 0x8B:
            continue
        if p[0] == 0x5E and p[6] == 0x5E:
            yield '[losgelassen]'
            continue
        if p[0] == 0x50 and p[5] == 0x00:
            cmd = p[4]
            yield KEYS.get(cmd, f'0x{cmd:02x}')
            continue
        # unbekanntes Event überspringen


def main(seconds):
    out = telnet('wc -c < /tmp/keylog.bin')
    digits = ''.join(re.findall(r'\d+', out))
    offset = int(digits) if digits else 0
    print(f'Live ab Offset {offset} — drück jetzt Tasten auf der Fernbedienung.')
    print('(Strg+C zum Beenden)\n', flush=True)

    end = time.time() + seconds
    while time.time() < end:
        data, offset = read_from(offset)
        for e in events(data):
            print(f'  >>> {e}', flush=True)
        time.sleep(0.8)


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 45)
