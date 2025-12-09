FRP hardening checklist (frps + frpc)
=====================================

Goal: only your frpc can register tunnels; keep the control channel private; reduce abuse risk.

Assumptions
- frps runs on the remote server with public 80/443 forwarded by the router.
- frpc runs at home; both servers are on Tailscale (100.x addresses).
- Control port (default 7000) must not be exposed to the public internet.

frps (server) config
- Bind control to Tailscale only: set `bind_addr = 100.x.y.z` (the frps Tailscale IP) and keep `bind_port = 7000`. Ensure the router does NOT forward 7000.
- Require auth: set `authentication_method = token` and a strong `token`.
- Encrypt control channel: set `tls_enable = true`.
- Limit what can be exposed: set `allow_ports = 80,443` so rogue clients cannot open arbitrary ports.
- Keep public vhost listeners on 80/443 as needed: `vhost_http_port = 80`, `vhost_https_port = 443`.
- Firewall: allow 80/443 from the internet; allow 7000 only from Tailscale (or trusted source IPs).

Example `/etc/frp/frps.ini`:
```
[common]
bind_addr = 100.x.y.z          # frps Tailscale IP
bind_port = 7000
vhost_http_port = 80
vhost_https_port = 443
authentication_method = token
token = <strong-random-token>
tls_enable = true
allow_ports = 80,443
```

frpc (client) config
- Point to frps via Tailscale: `server_addr = 100.x.y.z`, `server_port = 7000`.
- Match auth/TLS: same `authentication_method = token`, same `token`, and `tls_enable = true`.
- Define only the tunnels you need (HTTP/HTTPS).

Example `/etc/frp/frpc.ini`:
```
[common]
server_addr = 100.x.y.z   # frps Tailscale IP
server_port = 7000
authentication_method = token
token = <strong-random-token>
tls_enable = true

[forward-https]
type = tcp
local_ip = 127.0.0.1
local_port = 443
remote_port = 443
proxy_protocol_version = v2

[forward-http]
type = tcp
local_ip = 127.0.0.1
local_port = 80
remote_port = 80
proxy_protocol_version = v2
```

Operational checks
- Confirm router forwards only 80/443 to frps; 7000 is not forwarded.
- On frps, verify `ss -tlnp` shows 7000 bound to 100.x.y.z (not 0.0.0.0).
- From a non-Tailscale host on the internet, 7000 should be unreachable.
- Rotate the token if compromised; restart frps/frpc after changes.
