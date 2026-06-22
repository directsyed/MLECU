# infrastructure/networking/

Remote access + LAN configuration.

**Status:** LAN `10.0.0.0/24` up; WireGuard interface present (`10.10.0.1`) but the **VPN is non-functional** (DuckDNS still points at the old apartment IP; the port-forward was on the apartment router). Tailscale (Pi relay) planned.

**Will contain:** WireGuard config (subnet `10.10.0.0/24` — must not overlap the LAN), netplan (wildcard NIC match `en*` + `optional: true`), DuckDNS updater notes, Samba share config (`/home/syed/Shared/`).
