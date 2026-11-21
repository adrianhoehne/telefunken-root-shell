# Logging, app control, and boot resilience

What we built *after* the root shell: a logging pipeline that streams the
TV's own logs to the SMB share, a way to turn off resident apps, and a
fallback so the TV still boots when the share is unreachable.

## 1. The logging pipeline

A small static ARM daemon, `logd`, runs in the background (started by the
payload). It reads four sources and writes them into `log/` on the SMB share
(`/conf/remotelf/log/` on the TV):

| Source | Written to | Content |
| --- | --- | --- |
| `/proc/kmsg` | `log/kernel.log` | kernel ring buffer (boot log, driver messages) |
| `/tmp/app.log` | `log/app.log` | stdout/stderr of the TV app (redirected by the payload) |
| `/tmp/tv.log` | `log/tv.log` | boot events from the payload |
| `/tmp/keylog.bin` | `log/keys.log` | remote key presses, decoded to names |

`logd` is best-effort: a failed SMB write is dropped, never blocking. The
critical boot path never touches the share — the payload only writes to
`/tmp` (a tmpfs, always available) and lets `logd` forward in the background.

### Decoding the remote keys

The key hook (`libkeyhook.so`, see the writeup §4) logs the raw STBC byte
stream to `/tmp/keylog.bin`. `logd` parses it: each event is `FF FF` + 7
bytes, a key press is `50 00 00 <addr> <cmd> 00 <chk>`. The RC5 command byte
`<cmd>` maps to a key name via the same table as `/vendor/data/nvt.key.tk.ini`.

See `scripts/keydecode.py` (offline) and `scripts/livekeys.py` (live viewer).

## 2. Turning off resident apps

The app list `/vendor/data/nvt.app.ini` is read-only, but the payload runs at
boot and can kill anything. Netflix is resident (`netflix=y`,
`is_delay_launch=1`) and preloads ~78 MB of RAM even when unused.

`payload7.c` kills it once after boot:

```sh
(sleep 20; for i in 1 2 3 4 5 6 7 8; do p=$(pidof netflix); \
  [ -n "$p" ] && { kill $p; break; }; sleep 5; done &)
```

One kill is enough — the app manager does not restart Netflix. A manual
launch (Netflix button) still works; only the resident preload is gone.
YouTube was already `youtube=n` in the app list and needs no change.

## 3. Boot resilience — the local fallback

The vendor backdoor (`run_aurora.sh`, read-only `/vendor`) has **no
fallback**: if the CIFS mount fails, `$REMOTELF/aurora.elf` does not exist
and the TV app never starts (the app manager reboots in a loop).

The fix uses the fact that the mount point `/conf/remotelf` itself lives in
writable, persistent `/conf`. We keep a local copy of the payload there:

```
/conf/remotelf/            (in /conf, persistent)
├── aurora.elf             ← local snapshot of the payload
├── libkeyhook.so
└── logd
```

- Share reachable → the CIFS mount overlays the directory; the share's copy runs.
- Share unreachable → the mount fails; the local copy is visible and runs.

So the TV always boots. The local copy is a snapshot: `payload/deploy.sh`
refreshes it on every build (build → copy to share → refresh the local
fallback over `scripts/tvsh.py`).

## 4. Redactions

No device identifiers, keys, or dump contents are in this document.
