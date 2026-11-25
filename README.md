# Root shell on a Vestel 17MB211 TV — standalone repository

This repository documents how to gain a **persistent root shell** on a 2017
Vestel-built smart TV (Telefunken B43F545B, chassis `17MB211`, codename
"Shredder") **without UART and without opening the case**.

The vendor shipped the last firmware update for this platform in **2018**.
The device has received no security updates since.

## Read

- **[VESTEL-MB211-ROOT-SHELL.md](VESTEL-MB211-ROOT-SHELL.md)** — the full
  writeup: the device, the three access channels, the path to root, a
  detailed **failures-and-fixes** log, and the **data-extraction steps**.
- **[UBIFS-LAYOUT-AND-WRITE-PATH.md](UBIFS-LAYOUT-AND-WRITE-PATH.md)** — the
  definitive UBI/UBIFS layout (the "scatter" resolved), the volume table, and
  the untested **write path** for patching `/vendor`.
- **[DUMPING-AND-READING.md](DUMPING-AND-READING.md)** — how to make a dump
  (root shell `tar` or offline `nand read`) and read it back (full via `tar`,
  partial via the carve parser), plus why the raw image resists standard UBI
  tools (the vendor's redundant page storage).
- **[LOGGING-AND-APP-CONTROL.md](LOGGING-AND-APP-CONTROL.md)** — the logging
  pipeline (`logd` → kernel/app/key/boot logs on the SMB share), turning off
  resident apps (Netflix), and the local `/conf` fallback so the TV boots
  even without the share.
- **[BOOT-LOOP-AND-RECOVERY.md](BOOT-LOOP-AND-RECOVERY.md)** — **read this
  before enabling the backdoor.** Why `remote.txt` without a reachable share
  puts the TV into an endless reboot, why a local payload copy does not save
  you, the USB flash rescue images, and how to read the state off the serial
  console.

## Repository layout

```
scripts/           DevTools reader, file-system harvester, UBIFS parser,
                   network capture, tvcat.py (stream a tree off the TV over
                   the root shell) — the tools used against the device
scripts/u-boot/    the .scr scripts (U-Boot text scripts) for reading and
                   writing NAND/SPI flash, in the order they were used
payload/           the ARM payload (telnetd + netcat starter) and its source
smb/               Samba config + Dockerfile for the CIFS share
```

## Redactions

Device-specific values (MAC address, Netflix ESN, `nfvdid`, HbbTV UID, LAN
IPs) are removed. The vendor-hardcoded MAC `D4:E2:CC:EC:45:E9` is kept — it is
identical on every `17MB211` unit. Raw dumps and captures are **not** part of
this repository.

## License

This repository is dual-licensed:

| Part | License |
| --- | --- |
| Documentation (`README.md`, `VESTEL-MB211-ROOT-SHELL.md`) | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) — see `LICENSE.docs` |
| Code (scripts, `payload/`) | [MIT](https://opensource.org/licenses/MIT) — see `LICENSE` |

## Status

The full German investigation log (225 evidence-tagged observations) and the
raw dumps live in a separate private workspace.

---

**Footnote.** This project took **two days**. The analysis was done mostly by
an AI assistant; the orchestration — deciding the next step, putting it into
the right direction, holding the remote, plugging cables — was done by the
human operator. A warning for
anyone with a similar idea: **this is not a one-prompt path.**
