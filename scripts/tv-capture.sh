#!/usr/bin/env bash
# Mitschnitt des Fernseher-Verkehrs über diesen Rechner.
#
# Läuft im Container `tvcap` mit --net=host --privileged (das ist der Weg zu
# root-Rechten ohne sudo auf dem Wirt). Was es tut:
#   1. IPv4-Weiterleitung einschalten und Paketfilter für diese Schnittstelle öffnen.
#   2. Dem Fernseher per ARP sagen, das Gateway stehe hier. Nur der Fernseher
#      wird umgeleitet — die Gegenrichtung läuft weiter direkt über die Fritzbox,
#      damit möglichst wenig kaputtgeht.
#   3. Verkehr mitschreiben.
#   4. Beim Ende die ARP-Einträge und die Filterregeln wieder herstellen.
#
# Aufruf:  tv-capture.sh [Sekunden]
# Ergebnis: /out/tv-verkehr.pcap  (im Projekt: artefacts/tv-verkehr.pcap)
set -u

IF=${IF:-eno1}
TV_IP=${TV_IP:-192.168.0.0}  # TODO: set TV IP
GW_IP=${GW_IP:-192.168.0.1}  # TODO: set gateway
DUR=${1:-180}
OUT=${OUT:-/out/tv-verkehr.pcap}
# Snap-Länge begrenzt, damit ein Firmware-Download die Datei nicht flutet.
# 320 Byte reichen für DNS-Namen, HTTP-Kopfzeilen und TLS-SNI (ClientHello).
SNAP=${SNAP:-320}

mac_of() { ip neigh show "$1" | awk '{for(i=1;i<=NF;i++) if($i=="lladdr") print $(i+1)}'; }

MY_MAC=$(cat "/sys/class/net/$IF/address")
TV_MAC=$(mac_of "$TV_IP")
GW_MAC=$(mac_of "$GW_IP")
if [[ -z ${TV_MAC:-} || -z ${GW_MAC:-} ]]; then
  echo "MAC nicht ermittelbar (TV='${TV_MAC:-}' GW='${GW_MAC:-}')" >&2
  exit 1
fi
echo "Schnittstelle $IF  eigen=$MY_MAC  TV=$TV_IP/$TV_MAC  Gateway=$GW_IP/$GW_MAC"
echo "Dauer: ${DUR}s → $OUT"

arp_send() {  # arp_send <ziel-mac> <behauptete-ip> <behauptete-mac>
  python3 - "$IF" "$1" "$2" "$3" <<'PY'
import socket, struct, sys
iface, dst, claim_ip, claim_mac = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
mac = lambda s: bytes.fromhex(s.replace(':', ''))
frame = (mac(dst) + mac(claim_mac) + b'\x08\x06'
         + struct.pack('!HHBBH', 1, 0x0800, 6, 4, 2)
         + mac(claim_mac) + socket.inet_aton(claim_ip)
         + mac(dst) + socket.inet_aton(claim_ip))
s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
s.bind((iface, 0))
s.send(frame)
PY
}

poison() { while :; do arp_send "$TV_MAC" "$GW_IP" "$MY_MAC"; sleep 1; done; }
unpoison() { for _ in 1 2 3 4 5; do arp_send "$TV_MAC" "$GW_IP" "$GW_MAC"; sleep 0.2; done; }

cleanup() {
  echo "— Umleitung beenden —"
  [[ -n ${POISON_PID:-} ]] && kill "$POISON_PID" 2>/dev/null
  unpoison
  iptables -D FORWARD -i "$IF" -o "$IF" -s "$TV_IP" -j ACCEPT 2>/dev/null
  iptables -D FORWARD -i "$IF" -o "$IF" -d "$TV_IP" -j ACCEPT 2>/dev/null
  echo "— ARP und Filter wiederhergestellt —"
}
trap cleanup EXIT INT TERM

sysctl -qw net.ipv4.ip_forward=1
sysctl -qw "net.ipv4.conf.$IF.rp_filter=2"
# Alte Regeln aus einem abgebrochenen Lauf zuerst entfernen (idempotent).
while iptables -D FORWARD -i "$IF" -o "$IF" -s "$TV_IP" -j ACCEPT 2>/dev/null; do :; done
while iptables -D FORWARD -i "$IF" -o "$IF" -d "$TV_IP" -j ACCEPT 2>/dev/null; do :; done
iptables -I FORWARD 1 -i "$IF" -o "$IF" -s "$TV_IP" -j ACCEPT
iptables -I FORWARD 1 -i "$IF" -o "$IF" -d "$TV_IP" -j ACCEPT

poison & POISON_PID=$!
sleep 2

echo "— Weiterleitung prüfen —"
fwd_before=$(awk '/^Ip:/{getline; print $9}' /proc/net/snmp)

# -Z root: Ubuntus tcpdump wechselt sonst auf den Benutzer `tcpdump` und
# scheitert beim Anlegen der Rotationsdateien im eingehängten Ordner.
timeout "$DUR" tcpdump -i "$IF" -n -Z root -s"$SNAP" -U -C 25 -W 4 -w "$OUT" "host $TV_IP" &
TCPDUMP_PID=$!

# In Ein-Sekunden-Schritten warten, damit ein Abbruch sofort aufgeraeumt wird.
left=$DUR
while (( left > 0 )); do
  sleep 1
  left=$(( left - 1 ))
  if (( left == DUR / 2 )); then
    fwd_mid=$(awk '/^Ip:/{getline; print $9}' /proc/net/snmp)
    echo "weitergeleitete Pakete: vorher $fwd_before, nach $((DUR / 2))s $fwd_mid"
  fi
  kill -0 "$TCPDUMP_PID" 2>/dev/null || break
done

wait $TCPDUMP_PID 2>/dev/null
echo "— Mitschnitt fertig: $(du -ch /out/tv-verkehr.pcap* 2>/dev/null | tail -1 | cut -f1) —"
