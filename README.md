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

## Repository layout

```
scripts/           DevTools reader, file-system harvester, UBIFS parser,
                   network capture — the tools used against the device
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

## Status

The full German investigation log (218 evidence-tagged observations) and the
raw dumps live in a separate private workspace.
