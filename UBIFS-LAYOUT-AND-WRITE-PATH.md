# UBIFS layout, the "scatter", and the write path

This is the resolution to the failures in the main writeup (§5.8–5.10). After
we got a root shell, the Linux UBI driver answered every question that the
offline tools could not. Everything below was read **over the root shell** —
nothing was written to the device.

## 1. The "scatter" was a PEB-size mismatch

| Parameter | Value |
| --- | --- |
| NAND block size (MTD `erasesize`) | **256 KiB** (0x40000) |
| UBI physical eraseblock (PEB) | **248 KiB** (253952 B) |
| Difference = reserve per block | **8 KiB** (8192 B) |
| Minimum I/O size | 4096 B |
| Volume types | all `dynamic` |

The vendor reserves 8 KiB of every 256 KiB block, so the UBI PEB is 248 KiB,
not the block size. That single fact explains every offline failure:

- `ubireader`, `unblob`, `binwalk` assumed a 256/512 KiB PEB and never found
  the UBI structure (§5.9).
- U-Boot's `ubi read` computed PEBs from the 256 KiB MTD erase size and
  returned logical blocks in a scrambled order (§5.8).
- `nand read` looked block-aligned but the content was not (§5.10).

The Linux kernel knows the correct 248 KiB PEB (the vendor's board config), so
`/vendor` mounts cleanly and every file is readable through the mount.

## 2. The definitive volume table

Read from `/sys/class/ubi/`:

| MTD | UBI volume | `data_bytes` | Reserved EBs | Mount |
| --- | --- | --- | --- | --- |
| `fs0` (20 MiB) | `ubi0_0` `fs0` | 17.5 MB | 69 | `/` (ro) |
| `ap0` (200 MiB) | `ubi12_0` `ap0` | 193 MB | 760 | `/vendor` (ro) |
| `ap0` | `ubi12_127` `nvt_sign` | 248 KiB | 1 | — |
| `apdat0` (40 MiB) | `ubi13_0` `apdat0` | 37 MB | 146 | `/conf` (rw) |
| `buffer` (213 MiB) | `ubi14_0` `buffer` | 205 MB | 810 | `/buffer` (rw) |

Every volume is `dynamic` (no static data volumes). `/vendor` holds 3,876
files; `/conf` is the small writable volume we replaced earlier.

## 3. Hurdles on the way to a full extraction

With the shell, extracting the volumes was straightforward — except for two
hurdles that each needed a workaround:

1. **The CIFS share is read-only.** `smb.conf` has `read only = yes` and the
   Docker bind-mount is `ro`. Writing a dump from the TV to the share fails
   with `Permission denied` even though the mount shows `rw` (the server
   rejects the write). Do **not** make the share writable just to pull data —
   see the workaround below.
2. **A reverse connection is blocked.** `ufw` on the build host blocks an
   inbound `nc` listener, so the obvious `tar … | nc host 9999` fails.

**Workaround:** stream over the shell we already had. `scripts/tvcat.py`
connects to the `nc` fallback (port 2323), runs `tar cf - <tree>`, and
delimits the binary stream with an end marker so it can be saved raw on the
host. This needs no new port, no share change, and no firewall rule.

Result (files kept out of this repo by design — they are device dumps):

| Archive | Contents | Files |
| --- | --- | --- |
| `vendor.tar` | ap0 = `/vendor` | 3,876 |
| `rootfs.tar` | fs0 = `/` | 1,104 |
| `buffer.tar` | `/buffer` | 299 |
| `conf.tar` | apdat0 = `/conf` | 40 |

## 4. The write path (untested — read before you write)

With the layout known, patching `/vendor` (ap0) is possible in principle. Two
routes exist; **neither has been attempted**, and both are destructive.

### 4.1 Remount read-write (simplest, untested)

```sh
mount -o remount,rw /vendor
```

The kernel mounted `/vendor` read-only. Whether it will accept a remount
depends on the vendor's board config (`MS_RDONLY` may be forced). If it
works, files can be changed in place — no image building, no U-Boot.

### 4.2 Build a new image and write it

Correct geometry for the vendor layout:

```sh
# LEB = PEB (253952) − 2 headers (2 × 4096)
mkfs.ubifs -m 4096 -e 245760 -c 760 -r /path/to/new/vendor -o ap0.ubifs
ubinize    -p 253952 -m 4096 -O 4096 -o ap0.ubi ap0.cfg
```

The `ap0.cfg` declares one dynamic volume `ap0`. Then write `ap0.ubi`:

- **Via U-Boot `ubi write` — risky.** U-Boot's UBI reads the 256 KiB MTD erase
  size, not the vendor's 248 KiB PEB, which is exactly the mismatch behind the
  scrambled reads. Writing this way may lay out blocks wrongly. Do not trust
  it without verifying.
- **Via Linux** (`ubiupdatevol`, if present) is cleaner because the kernel
  driver knows the 248 KiB layout. `ubiupdatevol /dev/ubi12_0 ap0.ubi` writes
  the volume correctly; check whether the tool exists on the device first.

### 4.3 Safety

- Take a **full backup of the target volume first** (`tar cf - /vendor` over
  `tvcat.py`, or a raw `nand read` of the whole partition).
- Have a **recovery path**: the U-Boot `.scr` channel (probe scripts) reads
  and writes flash even with a dead `/vendor`, and the OK-button boot is the
  only way back if `/vendor` won't boot.
- Changing `/vendor` can brick the TV. This is the same risk class as the
  earlier `/conf` rewrite; treat it accordingly.

## 5. Redactions

No device identifiers, keys, or extracted data are in this document or this
repository. The dumps named above are intentionally not committed.
