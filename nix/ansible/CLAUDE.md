# Ansible (Pi Zero management)

- Use drop-in config dirs (`sshd_config.d/`, `apt.conf.d/`, etc.) instead of modifying default config files
- Prefer `ansible.builtin.copy`/`template` over `lineinfile` when managing whole config blocks
- Inventory uses Tailscale MagicDNS names or IPs
- Playbooks live in `ansible/` at the repo root
- Deploy with `nix run .#ansible-deploy`
