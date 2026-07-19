#!/usr/bin/env bash
# Apply /opt/ghawy/security/blocked_ips.txt to iptables.
#
# Blocks each listed source IP in both DOCKER-USER (forwarded traffic to the
# published nginx container port — this is where attack traffic actually lands)
# and INPUT (belt-and-suspenders for any host-mode port). Idempotent: a rule is
# only added if it is not already present, so it is safe to run repeatedly and
# on every boot.
#
# Remove an IP: delete its line from blocked_ips.txt, then remove the live rule:
#   iptables -D DOCKER-USER -s <ip> -j DROP ; iptables -D INPUT -s <ip> -j DROP
set -euo pipefail

LIST="/opt/ghawy/security/blocked_ips.txt"
[ -f "$LIST" ] || { echo "no blocklist at $LIST"; exit 0; }

# DOCKER-USER may not exist yet if Docker hasn't created it; create if missing so
# our rule survives even a very early boot ordering.
iptables -L DOCKER-USER -n >/dev/null 2>&1 || iptables -N DOCKER-USER 2>/dev/null || true

while read -r ip; do
    ip="${ip%%#*}"; ip="$(echo "$ip" | tr -d '[:space:]')"
    [ -z "$ip" ] && continue
    iptables -C DOCKER-USER -s "$ip" -j DROP 2>/dev/null || iptables -I DOCKER-USER 1 -s "$ip" -j DROP
    iptables -C INPUT -s "$ip" -j DROP 2>/dev/null || iptables -I INPUT 1 -s "$ip" -j DROP
    echo "blocked: $ip"
done < "$LIST"
