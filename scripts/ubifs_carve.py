#!/usr/bin/env python3
"""UBIFS-Abbild auslesen, ohne den B-Baum zu benutzen.

Hintergrund: Der Volume-Lesevorgang des Bootloaders liefert die logischen
Blöcke nicht in der Reihenfolge, die UBIFS erwartet (die Master-Knoten stehen
nicht in LEB 1/2). Deshalb scheitern ubireader, unblob und jedes Einhängen.

Dieses Skript geht den umgekehrten Weg: Es durchsucht das ganze Abbild nach
Knoten, ordnet sie über ihre Schlüssel einander zu und baut die Dateien daraus
zusammen. Der B-Baum wird nicht gebraucht.

Aufbau der Knoten (aus dem Abbild abgeleitet, Little-Endian):

  gemeinsamer Kopf  24 Byte: Magic 0x06101831, CRC, sqnum(8), len(4), typ(1)
  typ 0  INO   : key(16) @24, creat_sqnum @40, size @48, mode @104,
                 data_len @112, Inline-Daten ab 160
  typ 1  DATA  : key(16) @24, size @40, compr_type @44, Daten ab 48
  typ 2  DENT  : key(16) @24, inum @40, nlen @52, Name ab 56

Aufruf (im Container mit python3-lzo):
    ubifs_carve.py <abbild> <zielordner>
"""
import os
import struct
import sys

import lzo

MAGIC = b"\x31\x18\x10\x06"
T_INO, T_DATA, T_DENT = 0, 1, 2


def nodes(d):
    i = d.find(MAGIC)
    while i != -1:
        try:
            ln = struct.unpack("<I", d[i + 16:i + 20])[0]
            node_type = d[i + 20]
            if 24 <= ln <= 262144 and i + ln <= len(d) and node_type in (T_INO, T_DATA, T_DENT):
                yield i, ln, node_type
        except struct.error:
            pass
        i = d.find(MAGIC, i + 1)


def main(image, outdir):
    d = open(image, "rb").read()
    inodes, data, dents = {}, {}, []
    lzo_ok = lzo_fail = 0

    for off, ln, node_type in nodes(d):
        node = d[off:off + ln]
        if node_type == T_INO:
            if ln < 120:
                continue
            inum = struct.unpack("<I", node[24:28])[0]
            size = struct.unpack("<Q", node[48:56])[0]
            mode = struct.unpack("<I", node[104:108])[0]
            dlen = struct.unpack("<I", node[112:116])[0]
            inline = node[160:160 + dlen]
            sq = struct.unpack("<Q", node[8:16])[0]
            if inum not in inodes or sq > inodes[inum]["sq"]:
                inodes[inum] = {"size": size, "mode": mode, "inline": inline, "sq": sq}
        elif node_type == T_DATA:
            if ln < 48:
                continue
            inum = struct.unpack("<I", node[24:28])[0]
            block = struct.unpack("<I", node[28:32])[0] & 0x00FFFFFF
            size = struct.unpack("<I", node[40:44])[0]
            compr = struct.unpack("<H", node[44:46])[0]
            payload = node[48:]
            chunk = None
            sq = struct.unpack("<Q", node[8:16])[0]
            if compr == 1:
                for start in (0, -2, 2):
                    try:
                        cand = bytes(node[48 + start:])
                        chunk = lzo.decompress(cand, False, size)
                        lzo_ok += 1
                        break
                    except Exception:
                        continue
                if chunk is None:
                    lzo_fail += 1
            elif compr == 0:
                chunk = payload[:size]
                lzo_ok += 1
            if chunk is not None:
                slot = data.setdefault(inum, {})
                if block not in slot or sq > slot[block][0]:
                    slot[block] = (sq, chunk)
        else:
            if ln < 56:
                continue
            parent = struct.unpack("<I", node[24:28])[0]
            child = struct.unpack("<Q", node[40:48])[0]
            nlen = struct.unpack("<H", node[50:52])[0]
            name = node[56:56 + nlen].decode("utf-8", "replace")
            dents.append((parent, name, child))

    print(f"Knoten: {len(inodes)} Inodes, {len(data)} Daten-Inodes, {len(dents)} Verzeichniseinträge")
    print(f"Datenblöcke: {lzo_ok} entpackt, {lzo_fail} fehlgeschlagen")

    children = {}
    for parent, name, child in dents:
        children.setdefault(parent, []).append((name, child))

    written = 0
    for inum, info in inodes.items():
        if not (info["mode"] & 0o170000) == 0o100000:  # nur reguläre Dateien
            continue
        blocks = data.get(inum, {})
        content = b"".join(blocks[k][1] for k in sorted(blocks)) if blocks else b""
        if not content and info["inline"]:
            content = info["inline"]
        content = content[:info["size"]]
        if not content:
            continue
        path = os.path.join(outdir, "by_inode", str(inum))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(content)
        written += 1

    with open(os.path.join(outdir, "verzeichnis.txt"), "w", encoding="utf-8") as fh:
        for parent, name, child in sorted(dents):
            fh.write(f"{parent}\t{name}\t{child}\n")

    print(f"{written} Dateien nach 'by_inode' geschrieben, Pfade in 'verzeichnis.txt'")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    os.makedirs(sys.argv[2], exist_ok=True)
    main(sys.argv[1], sys.argv[2])
