#!/usr/bin/env python3
"""Decode /tmp/keylog.bin (captured by libkeyhook.so) into key presses.

The TV app reads remote-control events from the STBC MCU over /dev/ttyS2
(115200). libkeyhook.so logs those reads verbatim. This script turns the raw
byte stream into human-readable key presses.

Protocol (observed, one event = FF FF + 7 bytes):
  heartbeat = 8B 00 00 00 00 00 8B      (idle poll, ignore)
  release   = 5E 00 00 00 00 00 5E      (key up, generic)
  key press = 50 00 00 <addr> <cmd> 00 <chk>
              addr = RC5 address (0x38 / 0x30)
              cmd  = RC5 command byte (the actual key)
              chk  = cmd + 0x88 (checksum)

The command -> key mapping below comes from /vendor/data/nvt.key.tk.ini
(lines `0x000038XX=<key>`). Usage: keydecode.py <keylog.bin>
"""
import sys

# RC5 command byte -> key name, from nvt.key.tk.ini
KEYS = {
    0x41: '1', 0x42: '2', 0x43: '3', 0x44: '4', 0x45: '5',
    0x46: '6', 0x47: '7', 0x48: '8', 0x49: '9', 0x40: '0',
    0x55: 'LEFT', 0x56: 'RIGHT', 0x54: 'UP', 0x53: 'DOWN',
    0x60: 'CH+', 0x61: 'CH-',
    # NOTE: the .ini labels these 0x50=VOL_DOWN, 0x51=VOL_UP; the physical
    # remote orientation was not re-verified. Adjust if they appear swapped.
    0x50: 'VOL-', 0x51: 'VOL+',
    0x75: 'OK', 0x70: 'MENU', 0x78: 'SOURCE',
    0x5f: 'SUBTITLE', 0x7c: 'TEXT',
    0x77: 'RED', 0x76: 'GREEN', 0x72: 'YELLOW', 0x74: 'BLUE',
    0x58: 'STOP', 0x59: 'PLAY', 0x71: 'PAUSE',
    0x5b: 'REWIND', 0x5c: 'FORWARD',
    0x4c: 'STANDBY', 0x0a: 'ESC', 0x40: '0',
}


def decode(data):
    """Yield human-readable events for a raw keylog byte stream."""
    out = []
    for part in data.split(b'\xff\xff'):
        p = part[:7]
        if len(p) < 7:
            continue
        if p[0] == 0x8B and p[6] == 0x8B:
            continue  # heartbeat
        if p[0] == 0x5E and p[6] == 0x5E:
            out.append('RELEASE')
            continue
        if p[0] == 0x50 and p[5] == 0x00:
            addr, cmd = p[3], p[4]
            name = KEYS.get(cmd, '?')
            out.append(f'{name}  (rc5 0x{addr:02x}{cmd:02x})')
            continue
        out.append(p.hex())
    return out


def main(path):
    d = open(path, 'rb').read()
    i = d.find(b'==\n')  # skip the ==OPEN== marker libkeyhook writes
    body = d[i + 3:] if i >= 0 else d
    pressed = [e for e in decode(body) if e != 'RELEASE']
    print(f'{len(pressed)} Tastendrücke:')
    for e in decode(body):
        print('  ' + e)


if __name__ == '__main__':
    main(sys.argv[1])
