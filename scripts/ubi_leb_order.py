#!/usr/bin/env python3
"""Rohdump der ap0-Partition in die logische LEB-Reihenfolge bringen.

Warum: `nand read` liefert die physischen Blöcke, aber `ubi read` gab die
Daten in einer Reihenfolge zurück, in der die UBIFS-Master-Knoten fehlten.
Deshalb wird hier der Weg über die UBI-Kopfstrukturen gegangen:

  * Jeder Block beginnt mit einem EC-Kopf (`UBI#`). Er nennt `vid_hdr_offset`
    und `data_offset` — beide sind hier 4096 und 8192.
  * Am `vid_hdr_offset` steht der VID-Kopf (`UBI!`) mit `vol_id` und `lnum`.
  * Die Nutzdaten stehen ab `data_offset`, Länge = LEB-Größe (253952).

Weil `nand read` defekte Blöcke überspringt, wird nicht im festen Raster
gesucht, sondern an **jeder 4-KB-Grenze** nach `UBI#`.

Aufruf:
    ubi_leb_order.py <rohdump.bin> <ziel.bin> [--vol VOL_ID]
"""
import struct
import sys

EC_MAGIC = b"UBI#"
VID_MAGIC = b"UBI!"
LEB_SIZE = 253952
PAGE = 4096


def main(src, dst, want_vol=None):
    d = open(src, "rb").read()
    entries = {}
    ec_count = vid_count = 0

    for off in range(0, len(d) - 64, PAGE):
        if d[off:off + 4] != EC_MAGIC:
            continue
        ec_count += 1
        vid_off, = struct.unpack(">I", d[off + 16:off + 20])
        data_off, = struct.unpack(">I", d[off + 20:off + 24])
        v = off + vid_off
        if v + 64 > len(d) or d[v:v + 4] != VID_MAGIC:
            continue
        vol_id, lnum = struct.unpack(">II", d[v + 8:v + 16])
        vid_count += 1
        entries.setdefault(vol_id, {})[lnum] = off + data_off

    print(f"EC-Köpfe: {ec_count}, davon mit gültigem VID: {vid_count}")
    for vol, lebs in sorted(entries.items(), key=lambda kv: -len(kv[1]))[:6]:
        nums = sorted(lebs)
        print(f"  vol_id {vol:>10}: {len(lebs):4} LEBs, lnum {nums[0]}..{nums[-1]}")

    if not entries:
        sys.exit("keine UBI-Köpfe gefunden")

    vol = want_vol if want_vol is not None else max(entries, key=lambda k: len(entries[k]))
    lebs = entries[vol]
    hi = max(lebs)
    img = bytearray((hi + 1) * LEB_SIZE)
    written = 0
    for lnum, src_off in lebs.items():
        chunk = d[src_off:src_off + LEB_SIZE]
        img[lnum * LEB_SIZE:lnum * LEB_SIZE + len(chunk)] = chunk
        written += 1

    with open(dst, "wb") as fh:
        fh.write(img)
    print(f"Volume {vol}: {written} LEBs geschrieben, Bild {len(img)} Byte -> {dst}")
    missing = [n for n in range(hi + 1) if n not in lebs]
    print(f"fehlende lnum: {len(missing)} (z. B. {missing[:10]})")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    vol = None
    if "--vol" in sys.argv:
        vol = int(sys.argv[sys.argv.index("--vol") + 1])
    main(sys.argv[1], sys.argv[2], vol)
