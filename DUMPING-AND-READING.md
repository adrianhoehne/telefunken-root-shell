# Dumping and reading the flash — a practical recipe

How to make a dump of this TV and read it back into files. The device has no
UART and the case stays closed; everything below uses either the U-Boot
`.scr` channel or the root shell from the main writeup.

**Short version:** the only *complete* read path is the root shell (the whole
point of this repository). The offline `.scr` dump is for backups and gives a
*partial* recovery — the vendor's NAND controller stores every logical page
redundantly, which breaks standard UBI parsers on raw dumps. That structure is
documented at the end so the gap can be closed.

## 1. Making a dump

### 1.1 Full and easy — over the root shell

Once you have the root shell (writeup §4), stream each mounted volume off the
device with `scripts/tvcat.py`:

```sh
TV_IP=<tv> python3 scripts/tvcat.py "tar cf - /vendor" vendor.tar
TV_IP=<tv> python3 scripts/tvcat.py "tar cf - /conf --exclude=/conf/remotelf" conf.tar
TV_IP=<tv> python3 scripts/tvcat.py "tar cf - /buffer" buffer.tar
TV_IP=<tv> python3 scripts/tvcat.py \
  "tar cf - / --exclude=/proc --exclude=/sys --exclude=/dev --exclude=/tmp \
   --exclude=/vendor --exclude=/conf --exclude=/buffer --exclude=/media" rootfs.tar
```

These are plain tar archives — `tar xf vendor.tar` reads them. This is the
only path that yields **all** files (3,876 in `/vendor`).

### 1.2 Offline — a raw image over the U-Boot `.scr` channel

Boot while holding OK (writeup §3.2) and let a `.scr` script run:

```
nand read 0x2000000 ap0 0xc800000
fatwrite usb 0:1 0x2000000 ap0.bin 0xc800000
```

This writes the raw `ap0` partition (200 MiB) to a FAT32 stick. `ap0` has no
bad blocks, so the read is clean and contiguous. Do the same for `apdat0`
(40 MiB) and `buffer` (213 MiB) if wanted. The partition names and sizes come
from `env export` (writeup §3.2, `probe_v6.scr`).

## 2. Reading a dump

### 2.1 The tar archives (§1.1) — complete

Plain `tar xf`. Nothing else needed.

### 2.2 A raw image (§1.2) — partial, two tools

**Carve by UBIFS node magic** — `scripts/ubifs_carve.py` (needs `python3-lzo`,
run in a container):

```sh
python3 scripts/ubifs_carve.py ap0.bin ./out/
```

It scans for UBIFS node magic anywhere, joins nodes by (inode, block) key and
LZO-decompresses them. No UBI layer needed, so it works on the raw image. It
recovers a large fraction of the file contents and names, but not everything
(big files store data in nodes that the carver does not fully reassemble).

**Rebuild the UBI volume** — `scripts/ubi_leb_order.py` walks the UBI erase
and VID headers to map logical blocks to their data:

```sh
python3 scripts/ubi_leb_order.py ap0.bin ap0_vol.bin --vol 0
```

Then feed `ap0_vol.bin` to a UBIFS parser (`ubireader_extract_files`). **This
currently recovers only ~100 of the 760 logical blocks** — see §3 for why.

## 3. Why offline reconstruction is hard

The raw `nand read` image does not look like what the UBI/UBIFS tools expect.
Measured on the `ap0` raw image:

| Fact | Value |
| --- | --- |
| Block size | 256 KiB (64 pages of 4096 B) |
| UBI PEB | 248 KiB (62 pages) — 8 KiB reserve per block |
| EC header | `UBI#` at the start of a PEB |
| VID header | `UBI!` after the EC header |

**Every logical 4096-byte page is stored several times in a row** in the raw
read — the vendor's NAND controller writes redundant copies (1–5, varying).
Example of one physical block (page contents, 4096 B each):

```
UBI#  UBI#  UBI#  UBI!  UBI!  UBI!  FF FF FF FF ...
 \-----EC ×3-----/ \-----VID ×3-----/    (reserve)
```

and the data pages after the headers are duplicated the same way:

```
EC  VID  D0 D0 D0  D1 D1 D1 D1 D1  FF FF FF ...
 \1×/ \1×/ \--3×--/  \----5×----/    (reserve)
```

The Linux UBI driver knows this scheme and decodes it, which is why `/vendor`
mounts cleanly and the shell path (§1.1) is complete. Standard tools
(`ubireader`, `unblob`, `ubinize`) and U-Boot's own `ubi read` do **not** know
it: they assume one EC header per PEB at a fixed offset, so they either fail
or read logical blocks in the wrong order.

`ubi_leb_order.py` scans for the redundant headers but the copy count varies
per block and the VID header is not at a fixed offset, so it misses most of
the 760 logical blocks. The carve parser (§2.2) sidesteps the problem by
ignoring the UBI layer entirely.

### What it would take to finish this

A correct offline extractor must, per 256 KiB block:

1. collapse consecutive identical 4096-byte pages (drop the redundancy),
2. locate `UBI#` (erase counter) and `UBI!` (VID) in the collapsed pages,
3. read `vol_id` + `lnum` from the VID header,
4. take the 60 collapsed data pages after the headers (245,760 bytes) as the
   logical block, and
5. sort the blocks by `lnum` to rebuild the volume.

The de-duplication step is what the current tools get wrong; the copy count is
not constant and the header can sit at page 0 or page 1. If you implement
this, verify against the known numbers: `ap0` = volume `0`, 760 logical
blocks, 3,876 files, mount point `/vendor`.

## 4. Redactions

No device identifiers, keys, or dump contents are in this document. The dump
files themselves carry identifiers (MAC, Netflix ESN, `nfvdid`, HbbTV UID) —
that is exactly why they are not part of this repository.
