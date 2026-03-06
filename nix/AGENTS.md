# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Persona
Expert NixOS/Nix flake specialist for multi-host infrastructure management.
Understands declarative configuration, systemd integration, and homelab patterns.

## Build & Test Commands
- `nix flake check` - Validate flake syntax and evaluate all outputs
- `nix-instantiate --eval -E 'import ./flake.nix'` - Quick expression test
- `./nix-build.sh [hostname]` - Build and switch (auto-detects Darwin vs NixOS)
- `./nix-rollback.sh [hostname]` - Rollback to previous configuration
- `nix run .#switch` - Deploy to macOS (darwin) alternative

No CI pipeline; validation is manual via `nix flake check`.

## Project Architecture

### Two Hosts
- `darwinConfigurations.chloe-macbook-air` (aarch64-darwin) — macOS config
- `nixosConfigurations.homeserver` (x86_64-linux) — NixOS homeserver

### Key Directories
```
flake.nix                    # Entry point, defines both hosts
modules/                     # Shared: common.nix (packages), tailscale.nix
home/                        # Home Manager (macOS only)
hosts/macbook-air/           # Darwin config + homebrew.nix
hosts/homeserver/            # NixOS homeserver
  services.d/                # Service definitions (default.nix + compose/config)
  backup/                    # Restic backup system + svc CLI tool
  docker/                    # Docker daemon, prerequisites, maintenance, auto-update
  compose/                   # systemd service generation for docker-compose
  deployment/                # Activation scripts: file copy + secret symlinks
  lib/                       # Pure Nix helpers (docker.nix, deployment.nix)
```

### Module Import Order (matters!)
`options.nix` → `services.nix` → all other modules. `services.nix` populates `config.homeserver.services`, which everything else reads.

### Service Pipeline (end-to-end)
1. **Define**: Service `.nix` in `services.d/` returns metadata record
2. **Load**: `services.nix` discovers and imports all services, auto-detects `docker-compose.yml` and `.env.ctmpl`
3. **Secrets**: `deployment/secrets.nix` registers `secretFiles` into `homeserver.vault.secrets`
4. **Vault**: `vault-agent.nix` renders templates to `/var/lib/secrets/docker-services/<name>/`
5. **Deploy**: `deployment/files.nix` activation script rsyncs Nix store → `/var/lib/docker-services/<name>/`, symlinks secrets (or copies if `mountable = true`)
6. **Run**: `compose/systemd.nix` generates `docker-compose-<name>` systemd services
7. **Maintain**: `docker/` handles prereqs, auto-update (daily 04:00), log fixes, image cleanup

### Custom Options
Defined in `options.nix` — `config.homeserver.*`:
- `mainDrive` (`/data`), `backupDrive` (`/data2`), `homeserverRoot` (`/data/homeserver`)
- `paths.deployRoot` (`/var/lib/docker-services`), `paths.secretsRoot` (`/var/lib/secrets`)
- `paths.dockerDataRoot`, `paths.dockerVolumesRoot` (computed from mainDrive)
- `vault.address`, `vault.tokenPath`, `vault.unsealTokenPath`, `vault.secrets`
- `services` — attrset of all loaded service metadata

### Networking
- Hostname: `home-stockholm`
- dnsmasq resolves `*.nelyah.eu` to Tailscale IP, forwards rest to Cloudflare/Google DNS
- Dependency chain: `tailscale-online.target` → frp, dnsmasq
- TCP keepalive tuned for Matrix WebSocket bridges

### Key Infrastructure Services
- **docker-prereqs.service**: Creates all external networks/volumes before compose stacks start
- **vault-agent.service**: Renders secrets from Vault, cleans stale files on start
- **vault-unseal**: Timer-based auto-unseal (10 min interval)
- **docker-auto-update**: Daily pull + recreate all compose stacks (04:00)
- **disk-health**: SMART monitoring (quick daily, short weekly, long biannual) → `/var/lib/disk-health/status.json`

## Service Metadata Schema

Each service in `services.d/` must return:
```nix
{
  name = "service-name";           # Required: unique identifier
  compose = {
    enable = true;                 # Enable docker-compose systemd service
    path = null;                   # null = auto from deployRoot; or explicit path
    networks = ["network-name"];   # External docker networks (created by docker-prereqs)
    volumes = ["volume-name"];     # External docker volumes (created by docker-prereqs)
    build = false;                 # Pass --build to docker-compose up
  };
  files = {
    "config.yml" = {
      source = ./config.yml;
      destination = null;          # Defaults to key name when null
      executable = false;
    };
  };
  secretFiles = {
    ".env" = {
      template = ''{{ with secret "homeserver_secrets/data/svc" }}...{{ end }}'';
      destination = ".env";
      perms = "0400";
      mountable = false;           # true = copy instead of symlink (for Docker bind mounts)
    };
  };
  backup = {
    enable = true;
    needsServiceStopped = false;   # Stop compose unit during backup
    paths = ["/path/to/backup"];
    volumes = ["docker-volume"];
    tags = ["service-tag"];        # Defaults to [name]
    exclude = ["*.log"];
    policy = { daily = 10; weekly = 4; monthly = 4; };
    restore = {                    # Override restore behavior
      tag = null;
      volumes = null;
      paths = null;
      stopCompose = null;
      composeUnit = null;
      restic.target = null;
    };
  };
}
```

## Code Conventions
- Options defined in `hosts/homeserver/options.nix`
- Service paths: `${config.homeserver.homeserverRoot}/services/...`
- Package references: `${pkgs.docker}/bin/docker` not bare `docker`
- Pre/post hooks use heredoc strings with proper escaping
- Platform conditionals: `lib.mkIf pkgs.stdenv.isLinux { ... }`
- Systemd naming: `docker-compose-{name}`, `backup-{name}`, `backup-remote-{name}`

## Security Requirements
- Secrets via Vault templates in `vault-agent.nix`, NEVER hardcode
- Secret files: `/var/lib/secrets/` with 0400 permissions
- Vault templating syntax: `{{ with secret "homeserver_secrets/data/<key>" }}{{ .Data.data.<field> }}{{ end }}`
- Vault address: `https://vault.nelyah.eu`
- SSH: port 22, key-only auth (`services.openssh.settings.PasswordAuthentication = false`)
- Firewall: only ports 80, 443, 53, 22 (TCP) and 53 (UDP)
- fail2ban: 1 retry = permanent ban for SSH

## Dependencies
- Nixpkgs: `nixpkgs-25.11-darwin`
- Home Manager: `release-25.11`
- Unstable overlay: `pkgs.unstable` for latest packages

## Boundaries

### Always
- Run `nix flake check` before committing
- Use `lib.mkIf` for conditional configuration
- Follow existing service metadata schema
- Reference packages as `${pkgs.X}/bin/X`
- Use `set -euo pipefail` in shell scripts

### Ask First
- Modifying Vault templates (`vault-agent.nix`)
- Changing firewall rules (`networking.nix`)
- Adding new external networks/volumes (`docker.nix`)
- Changing backup retention policies
- Modifying systemd dependencies

### Never
- Hardcode secrets, passwords, or tokens
- Modify `hardware-configuration.nix`
- Remove fail2ban or weaken SSH security
- Use impure Nix features (`builtins.currentTime`, etc.)
- Skip `nix flake check` validation
- Use bare command names without `${pkgs.X}/bin/` prefix

## lib/ Pure Helpers
- `lib/docker.nix`: `collectNetworks`, `collectVolumes`, `mkPrereqScript`, `filterEnabledCompose`, `filterEnabledBackup`, `filterWithSecretFiles`
- `lib/deployment.nix`: `mkCleanupScript`, `mkCopyScript`, `mkSymlinkScript`

## svc CLI Tool

The `svc` module (`hosts/homeserver/backup/svc/`) is a Python CLI for managing service backups, restores, and lifecycle operations. Uses Click for CLI, Pydantic for config, Rich for rendering. Linted with ruff (ALL rules) and pyright (strict, Python 3.13).

### Package Structure
```
svc/
├── svc.py                  # Entry point, click argv normalization
├── config.py               # Pydantic models for services.json
├── exceptions.py           # SvcError hierarchy + exit codes (0-7)
├── cli/
│   ├── args.py             # Frozen dataclasses for typed CLI args
│   ├── renderer.py         # Renderer ABC (Rich/Plain, auto-detected by TTY)
│   ├── parser.py           # Click CLI definition + dynamic shell completion
│   └── commands/           # Command pattern implementations
│       ├── base.py         # AppContext (DI) + Command[TArgs] ABC
│       ├── list_cmd.py     # list, list-backups
│       ├── backup_cmd.py   # backup
│       ├── restore_cmd.py  # restore
│       ├── service_cmd.py  # start/stop/restart/logs
│       └── doctor_cmd.py   # doctor (timers, disk health, log scan)
├── core/                   # Business logic (no CLI knowledge)
│   ├── path_resolver.py    # Docker volume → filesystem path
│   ├── backup_orchestrator.py
│   ├── restore_orchestrator.py
│   ├── service_manager.py
│   └── service_helpers.py
└── controllers/            # External system interfaces (async)
    ├── systemctl.py        # SystemctlController
    ├── docker.py           # DockerController
    ├── restic.py           # ResticRunner
    ├── logs.py             # LogsController (docker-compose log scanning)
    └── disk_health.py      # Reads /var/lib/disk-health/status.json
```

### Commands
```bash
svc list [--backup-env local|remote] [--detailed]
svc list-backups <local|remote> <service>
svc backup <local|remote> <service|all>
svc restore <local|remote> <service> [snapshot|latest] [--verify-includes]
svc start|stop|restart <service|all> [--build] [--recreate]
svc logs <service> [--follow] [--tail N] [--timestamps]
svc doctor [--since "24 hours ago"] [--full]
svc docker health|prune-images|prune-orphans
```

### Architecture Patterns
- **Async throughout**: All subprocess calls use `asyncio.create_subprocess_exec()`
- **Renderer protocol**: RichRenderer for TTY, PlainRenderer for pipes
- **Command pattern**: Add new commands in `cli/commands/`, register in `__init__.py`
- **Dependency injection**: `AppContext` lazily provides controllers to commands
- **Config**: Reads `/etc/svc/services.json` (generated by Nix, overridable via `-c`)
