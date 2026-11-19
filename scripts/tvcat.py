#!/usr/bin/env python3
"""Stream a tree off the TV over the nc-2323 shell and save it raw.

Usage: tvcat.py "<tar command on the TV>" <output file>

The command MUST write a tar stream to stdout (`tar cf - ...`). The script
runs it over the shell, delimits the binary stream with an end marker, and
saves everything before the marker to <output file>. Needs no new port and no
share change — it reuses the root shell from the writeup.

Example:
    tvcat.py "tar cf - /vendor" vendor.tar
"""
import socket, sys, time, os

HOST = os.environ.get("TV_IP", "192.168.0.0")  # TODO: set TV IP
PORT = int(os.environ.get("TV_PORT", "2323"))
cmd = sys.argv[1]
outfile = sys.argv[2]
MARKER = b'__X7f9Q2_TRANSFER_END__'

s = socket.socket()
s.settimeout(900)
s.connect((HOST, PORT))
time.sleep(0.4)
# run the command, then print an end marker so we can cut the stream cleanly
s.sendall(cmd.encode() + b'; echo ' + MARKER + b'$?\n')
time.sleep(1.0)

data = b''
while True:
    try:
        x = s.recv(262144)
    except socket.timeout:
        break
    if not x:
        break
    data += x
    idx = data.find(MARKER)
    if idx != -1:
        data = data[:idx]
        break

# drop a possible command echo and trailing newlines
data = data.lstrip(b'\r\n').rstrip(b'\r\n')

with open(outfile, 'wb') as f:
    f.write(data)
print(f"wrote {len(data)} bytes -> {outfile}")
s.close()
