# Root shell on a Vestel 17MB211 TV — full writeup

**Target:** Telefunken B43F545B (Vestel chassis `17MB211`, codename
"Shredder"). **Result:** persistent `root` shell via Telnet (port 23) and
Netcat (port 2323), achieved without UART and without opening the case.

This writeup is the cleaned, English, redacted account of a full
investigation. It covers **what failed and what fixed it**, and — because that
is what usually gets lost — **exactly how the data was extracted from the
device**.

---

## Contents

1. [The device](#1-the-device)
2. [Three channels we discovered](#2-three-channels-we-discovered)
3. [How we extracted data](#3-how-we-extracted-data)
4. [The path to root](#4-the-path-to-root)
5. [Failures and fixes](#5-failures-and-fixes)
6. [What we gave up](#6-what-we-gave-up)
7. [Redactions](#7-redactions)
8. [Responsible disclosure note](#8-responsible-disclosure-note)

---

## 1. The device

| Property | Value |
| --- | --- |
| Brand / model | Telefunken B43F545B, sold 2017 |
| OEM | Vestel (`17MB211`, platform codename "Shredder") |
| SoC | Novatek NT72563 (`nt72563tk`), ARMv7, 2 cores |
| Kernel | Linux 3.10.0+ (gcc 4.9.2, 2018) |
| Firmware | `Shredder_17MB211_V0_59_2_2`, revision `r278154` |
| **Last vendor update** | **2018 — the device is end-of-life** |
| RAM | 334 MB @ 0x1000000 + 256 MB @ 0x20000000 |
| NAND | 512 MB, 16 partitions, erase block 256 KiB |
| SPI flash | 6 MB |
| Browser | Opera/Vewd, Chromium 53, `OPR/40.0.2207.0` |
| Root filesystem | UBI volume `fs0` (mtd11), UBIFS, read-only |
| `/vendor` | UBI volume `ap0` (mtd12), UBIFS, 200 MB, read-only |

The boot chain is signature-verified (XBOOT → SECOS → U-Boot → kernel/DTB),
so a custom kernel or bootloader never stood a chance. The userspace,
however, contains a vendor debug backdoor — which is what we used.

---

## 2. Three channels we discovered

### 2.1 Chromium DevTools on TCP 4725

The TV's Opera browser exposes the Chrome DevTools protocol on the LAN,
unauthenticated:

```
GET http://<TV>/4725/json/list
```

This yields the list of open pages and a WebSocket per page. Over the
WebSocket we could call `Page.navigate`, `Runtime.evaluate`, and
`Page.captureScreenshot`.

### 2.2 The U-Boot script channel (read *and* write flash)

Holding the remote's **OK** button while applying mains power makes the
bootloader execute a plain-text file `shredder_usb_update.scr` from the root
of a FAT32 stick. The script is **not** signature-checked. Commands
available: `nand read`, `sf read`, `fatwrite`, `fatload`, `ubi part`,
`ubi read`, `ubi write`, `crc32`.

### 2.3 The USB-import menu ("USB operations")

The service menu (MENU + `4725`) has a "USB operations" item that copies a
fixed set of files from the stick into the device **without** signature
checks.

---

## 3. How we extracted data

Three channels, three extraction paths. All scripts referenced here are in
`scripts/`.

### 3.1 Reading the file system over DevTools (TCP 4725)

The TV renders `file://` URLs as directory listings and text files. The tool
`scripts/cdp_fileread.py` navigates a page to a `file://` URL and returns the
rendered text:

```bash
python3 cdp_fileread.py /etc/rc.local /vendor/data/nvt.app.ini
```

`scripts/dump_tv_files.py` does this for many paths at once, and
`scripts/dump_tv_tree.py` walks the whole visible tree and saves an inventory
(`inventar.tsv`) plus every text file.

**Limits:** only *text* formats render. Binaries are treated as downloads and
never reach us; `XMLHttpRequest` against `file://` throws `NetworkError`.
`/proc`, `/sys`, `/dev` are not readable this way.

What this channel yielded: the whole boot chain (`rc.local`,
`/usr/script/startup.sh`, `/vendor/run.sh`, `run_aurora.sh`), the app list
(`nvt.app.ini`), the IR key table, build flags, `version.txt`.

### 3.2 Dumping flash over the U-Boot `.scr` channel

Write `shredder_usb_update.scr` to a FAT32 stick and boot while holding OK
(details in the script comments). The scripts in `scripts/u-boot/` dump
regions with `nand read` / `sf read` and write them to the stick with
`fatwrite`.

The essential ones:

| Script | What it reads |
| --- | --- |
| `probe_v3.scr` | 1 MB NAND head (first working script — the `%` terminator) |
| `probe_v6.scr` | U-Boot environment (`env export`) → the full `mtdparts` |
| `probe_v14.scr` | kernel (`ker0`, `ker1`) + device tree (`fdt0`, `fdt1`) |
| `probe_v18.scr` | `/conf` (apdat0) + `/buffer` |
| `probe_v19_backup.scr` | `/conf` volume backup (read-only, before writing) |

Two details that cost hours and are easy to miss:

1. The script **must** end with the line `% <- this is end of file symbol`.
2. The OK-button trigger: plug in mains **while holding OK**, aim the remote
   at the **LED face**, release as soon as the LED blinks **fast**.

### 3.3 Core dumps over the USB-import menu

Put an empty file named `enable_coredump` on the stick and run "USB
operations". It copies the flag to `/conf`. After that, a crashing process
writes its core dump to the stick — a read channel into root-process memory
(we got two ARM core dumps of the TV app `idtv` this way).

### 3.4 Full extraction over the root shell

Once the root shell was up, every mounted volume could be read directly —
closing the ap0 gap that the carve parser could only sample. The definitive
UBI layout, the two remaining hurdles, and the write path are documented in
[UBIFS-LAYOUT-AND-WRITE-PATH.md](UBIFS-LAYOUT-AND-WRITE-PATH.md); the
practical dump-and-read recipe (full over the shell, partial offline) is in
[DUMPING-AND-READING.md](DUMPING-AND-READING.md).

---

## 4. The path to root

The decisive discovery was a vendor debug backdoor in `/vendor/run_aurora.sh`:

```sh
REMOTECONFIG=/conf/remote.txt
if [ -e ${REMOTECONFIG} ]; then
    insmod cifs.ko
    ifconfig eth0 hw ether D4:E2:CC:EC:45:E9      # hardcoded vendor MAC
    udhcpc
    mount -t cifs -o username=…,password=… //<ip>/mb211cifs /conf/remotelf
    $REMOTELF/aurora.elf                          # runs OUR binary as root
fi
```

If `/conf/remote.txt` exists, the TV mounts an SMB share and executes a binary
named `aurora.elf` from it **as root** — a factory test hook.

The steps:

1. **Dump `/conf`** (UBI volume `apdat0`, mtd13, 40 MB) via the U-Boot channel.
2. **Rebuild `/conf`** with `mkfs.ubifs -r conf-neu -m 4096 -e 253952 -x lzo`,
   containing only `remote.txt` with the guest-mode line `0:<ip>::`.
3. **Write it back** via `scripts/u-boot/probe_v20_write.scr`
   (`fatload` + `ubi part apdat0` + `ubi write`) with a CRC32 read-back.
4. **Serve a payload** over SMB: a static ARM binary `aurora.elf`
   (`payload/payload3.c`) that starts `telnetd` and `nc`, then execs the real
   TV app.
5. **Reboot** → the TV mounts the share and runs the payload as root.

The payload:

```c
mkdir -p /dev/pts; mount -t devpts devpts /dev/pts;
(setsid busybox telnetd -l /bin/sh -p 23 &);
(busybox nc -ll -p 2323 -e /bin/sh &);
exec /vendor/com.nvt.idtv/aurora.elf;   /* keep the TV working */
```

Result:

```
# telnet <TV>
# id
uid=0 gid=0
```

The shell is persistent across reboots and iterable without further flash
writes (copy a new `aurora.elf` to the share and reboot).

---

## 5. Failures and fixes

The actual log of the investigation — almost every step failed at least once.

### 5.1 "The TV isn't on the network"
**Fix:** get the exact IP from the device's network menu; a `--min-rate` port
scan of the whole subnet beats SSDP/mDNS, which the TV did not answer.

### 5.2 "tcpdump: operation not permitted"
**Fix:** run capture inside a `--privileged --net=host` Docker container —
the standard pattern for every root-only operation.

### 5.3 "DevTools can't create a page"
**Diagnosis:** Chromium 53 has no `/json/new` and no `Target`/`Browser` CDP
domain. **Fix:** attach to an existing page, never try to create one.

### 5.4 "file:// works for text, not binaries"
**Diagnosis:** Chromium renders text but downloads binaries to the *device*;
`XHR` on `file://` throws. **Fix:** harvest text only; treat binaries as out
of reach over this channel.

### 5.5 "The browser fetches the file but never saves it"
**Diagnosis:** the Vewd browser has no download manager. **Fix:** ruled out
the browser as a write channel.

### 5.6 "The U-Boot script does nothing (v1, v2)"
**Diagnosis:** missing the `% <- this is end of file symbol` terminator.
**Fix:** append it; v3 immediately wrote the marker and a 1 MB dump.

### 5.7 "The OK-button procedure doesn't trigger"
**Diagnosis:** cold start + IR receiver behind the LED face + one-key remote.
**Fix:** plug in while holding OK, aim at the LED, release on fast blink.

### 5.8 "`ubi read` returns the volume in the wrong order"
**Diagnosis:** the vendor scatters the logical blocks; the UBIFS master nodes
are absent. **Fix:** none for ap0 — worked around with a carve parser (5.9).
**Resolved:** the "scatter" is a PEB-size mismatch — the vendor's UBI PEB is
248 KiB, not the 256 KiB MTD block size. See
[UBIFS-LAYOUT-AND-WRITE-PATH.md](UBIFS-LAYOUT-AND-WRITE-PATH.md).

### 5.9 "All standard UBIFS tools fail"
**Diagnosis:** every tool walks the B-tree from the master node; there is no
master node. **Fix:** `scripts/ubifs_carve.py` scans for UBIFS nodes by magic,
joins them by (inode, block) keys, and LZO-decompresses them — recovering
1,227 file names and 712 files.
**Resolved:** with the root shell, `/vendor` mounts cleanly and all 3,876
files are readable directly — the carve parser was only needed while the
layout was unknown.

### 5.10 "`nand read` skips blocks and shifts everything"
**Diagnosis:** bad-block skipping breaks the block-boundary assumption.
**Fix:** none for ap0; irrelevant for the small apdat0 rewrite.
**Resolved:** the shift came from the same 248-vs-256 KiB PEB mismatch.

### 5.11 "We dumped the wrong partition" (self-inflicted)
**Diagnosis:** an offset error; the volume table named itself "buffer".
**Fix:** recompute offsets from `mtdparts`, verify the volume name inside the
image before trusting it.

### 5.12 "CIFS mount fails — kernel lacks NTLM crypto"
**Diagnosis:** kernel 3.10 has `md4` but no `hmac`/`des`/`arc4`/`ecb`.
**Fix:** guest session — `remote.txt` with empty credentials and Samba with
`map to guest = bad user` + `server min protocol = NT1`.

### 5.13 "telnetd starts but dies immediately"
**Diagnosis:** `/dev/pts` missing, `devpts` not mounted. **Fix:**
`mkdir -p /dev/pts` + `mount -t devpts devpts /dev/pts`, then `setsid telnetd`.

### 5.14 "Samba container kept dying"
**Diagnosis:** runtime `apt-get install` racing the container lifecycle.
**Fix:** build a proper image (`smb/Dockerfile.samba`).

---

## 6. What we gave up

| Lost | Consequence |
| --- | --- |
| `/conf` (settings) | replaced with a minimal volume |
| Channel list | gone; first-time setup re-ran |
| PlayReady / Netflix keys | gone; not recoverable without the vendor |

`/vendor` (the 120 MB application partition) was **never touched** — and is
now **fully readable** through the root shell (see
[UBIFS-LAYOUT-AND-WRITE-PATH.md](UBIFS-LAYOUT-AND-WRITE-PATH.md)); a future
write path exists but has not been attempted.

---

## 7. Redactions

Removed: device MAC (`48:6d:bb:XX:XX:XX`), Netflix ESN, `nfvdid`, HbbTV UID,
LAN IPs. Kept: the vendor-hardcoded MAC `D4:E2:CC:EC:45:E9` (identical on
every `17MB211` unit). Raw dumps and captures are not part of this repo.

---

## 8. Responsible disclosure note

The backdoor is a **vendor debug/test feature** (`/conf/remote.txt`), not an
exploit we developed; the same mechanism is already public for the related
`17MB230` platform. The target is a 2017 device whose last vendor update is
from **2018**. Publishing this documents an existing, vendor-built path.
