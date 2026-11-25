# Boot loop: why it happens and how to get out

A trap that cost us a full evening. Read this before you enable the backdoor
and **before** you wipe `/conf`.

## 1. The trap

`/vendor/run_aurora.sh` (read-only vendor code) does this:

```sh
if [ -e /conf/remote.txt ]; then
    mount -t cifs -o username=$usr,password=$pw //$ip/mb211cifs /conf/remotelf
    $REMOTELF/aurora.elf        # payload from the share
else
    $PWD/com.nvt.idtv/aurora.elf   # stock app
fi
```

There is **no fallback branch for a failed mount**. If the mount fails,
`$REMOTELF/aurora.elf` does not exist, nothing starts, and the watchdog
restarts the box. The result is an endless boot loop: the panel shows no
picture and the LED blinks slowly. Holding the power button does nothing.

## 2. A local copy does *not* save you

The obvious idea is to keep a copy of the payload inside `/conf/remotelf/`
(which lives in persistent, writable `/conf`), so that a failed mount leaves
the local copy visible:

```
if mount succeeds -> share overlays the directory -> payload from the share
if mount fails    -> local copy is visible         -> payload runs
```

**This works when the mount fails quickly. It does not work when the server is
unreachable.** A CIFS mount to a host that does not answer blocks far longer
than the watchdog waits. The mount never returns, the app never starts, and the
box resets — with the local copy sitting unused in the flash. We verified this:
a `/conf` containing both `remote.txt` and a local `remotelf/aurora.elf`
produced the same endless loop.

**Consequence:** `remote.txt` may only exist in `/conf` while the share is
actually reachable from the TV. Never write it "for later".

## 3. Triggering it by accident

We triggered it twice without touching `remote.txt`:

- Replacing `/conf` (which wipes the network settings) while `remote.txt` was
  part of the new image. The TV came up without an IP, so the mount had no
  server to reach.
- Turning the Samba container off while the TV was off.

The TV then boots into the loop, and because there is no network there is also
no way in over telnet.

## 4. How to get out: flash `/conf` over USB

The only path that works without network is the U-Boot script channel
(writeup §3.2). You need a FAT32 stick with exactly two files:

| File | Purpose |
| --- | --- |
| `shredder_usb_update.scr` | the U-Boot script |
| `<image>.ubifs` | the new `/conf` volume image |

Three useful images (build them with `mkfs.ubifs`, geometry in
[UBIFS-LAYOUT-AND-WRITE-PATH.md](UBIFS-LAYOUT-AND-WRITE-PATH.md)):

| Image | `remote.txt` | local payload copy | Use |
| --- | --- | --- | --- |
| stock | no | no | get the TV working again |
| safe | yes | yes | backdoor when the share is reachable |
| jb | yes | no | the first attempt |

**The stock image is the rescue.** It contains only `friendlyname.txt`, so
`run_aurora.sh` takes the `else` branch and starts the stock app. The TV boots
with a picture again — without backdoor, which is exactly what you want until
the network is configured.

Script skeleton (values: image size in hex, CRC32 of the image):

```
fatload usb 0:auto 0x3400000 conf_stock.ubifs
ubi part apdat0
ubi write 0x3400000 apdat0 0x326000
mw.l 0x3400000 0x00000000 1
ubi read 0x3400000 apdat0 0x326000
if crc32 0x3400000 0x326000 0xca392e00; then
    echo VERIFIED
else
    echo CRC MISMATCH
fi
% <- this is end of file symbol
```

Boot while holding **OK** on the remote, aimed at the LED face, release when
the LED blinks **fast**.

### Do not trust the CRC result alone

In every one of our flash runs the stick ended up with **both** an `ok` and a
`fail` marker: the script runs more than once and the read-back path is
unreliable (the 248 KiB PEB versus 256 KiB block mismatch). A mixed result says
nothing about the volume. **The only reliable verdict is the device itself:** a
picture, or the serial signature below.

## 5. Diagnosing without opening the case

You cannot see the loop over the network — there is no network. The serial
console on the SCART connector tells you the state in seconds.

| Signal | SCART pin | Adapter |
| --- | --- | --- |
| `TX_STBY` | 12 | RX |
| `RX_STBY` | 10 | TX |
| GND | 14 | GND |

Use a **3.3 V** USB-UART adapter, never connect VCC. Baud rate **115200 8N1**:

```sh
stty -F /dev/ttyUSB0 115200 cs8 -cstopb -parenb raw -echo clocal
picocom -b 115200 -g /tmp/serial.log /dev/ttyUSB0
```

Run it inside `tmux` with `set-option remain-on-exit on`, otherwise the window
vanishes silently when the reader dies and you think you are still recording.

On power-up the stand-by controller prints:

```
NO
Spi Su:0x00
SPI ID:0xC22015
SPI type:0x00
Read back data from SPI....
P:0001
B:01
sysidx:0213
Pwr on:01
RstCode:00000000
PowerOnEvent: 0x02
```

The last line is the one that matters:

| `PowerOnEvent` | State |
| --- | --- |
| `0x02`, `0x03` | normal start |
| **`0x24`** | **reset loop** |

`RstCode` stayed `00000000` in every capture, including the loop, so the loop
is not reported as a hardware reset — it is a watchdog restart.

Nothing else follows, even on a healthy boot: the Linux console is on a
different UART (`ttyS0`, `ARM_UART_B`, `GPC_4`/`GPC_5`), which are BGA balls
under the SoC and not reachable on the board.

Note that `SPI ID` varies by build: our unit reported `0xC22015` (Macronix,
2 MiB) while the community wiki documents `0xEF4015` (Winbond). A different ID
is not a fault.

## 6. Checklist before you enable the backdoor

1. Samba share running and reachable **from the TV's subnet**.
2. TV has a working network configuration (IP visible in the menu).
3. `/conf` contains `remote.txt` **and** a local copy in `remotelf/`.
4. You have a stick with the **stock** image ready before you start.
5. You know the serial signature of a healthy boot, so you can tell them apart.

## 7. Redactions

Host addresses and device identifiers are replaced with placeholders. Nothing
in this document identifies a specific unit.
