# NixOS Homeserver Configuration Agent

## Persona
Expert NixOS/Nix flake specialist for multi-host infrastructure management.
Understands declarative configuration, systemd integration, and homelab patterns.

## Build & Test Commands
- `nix flake check` - Validate flake syntax and evaluate all outputs
- `nix-instantiate --eval -E 'import ./flake.nix'` - Quick expression test
- `nixos-rebuild switch --flake .#homeserver` - Deploy to homeserver
- `nix run .#switch` - Deploy to macOS (darwin)
- `./nix-build.sh [hostname]` - Build wrapper script

## Project Architecture

### Repository Structure
```
flake.nix                    # Entry point, defines two hosts
modules/                     # Shared modules (common.nix, tailscale.nix)
hosts/
  macbook-air/               # Darwin (macOS) config
  homeserver/                # NixOS Linux homeserver
    services.d/              # Service directories (default.nix + compose/config)
    backup/                  # Restic backup system
    deployment.nix           # Deploys service assets to /var/lib/docker-services
```

### Two Hosts
- `darwinConfigurations.chloe-macbook-air` (aarch64-darwin)
- `nixosConfigurations.homeserver` (x86_64-linux)

### Key Patterns
- **Custom options**: `config.homeserver.*` (mainDrive, backupDrive, vault.*)
- **Service metadata**: Each service dir/file returns `{name, compose, files, secretFiles, backup}` record
- **Dynamic loading**: `services.nix` loads dirs or `.nix` files, auto-imports `docker-compose.yml` and optional `.env.ctmpl`, validates `files/secretFiles`, `compose.path` optional
- **Systemd naming**: `docker-compose-{service}`, `backup-{service}`
- **Deployment**: `hosts/homeserver/deployment.nix` copies service assets from Nix store to `/var/lib/docker-services`, prunes stale dirs, symlinks Vault-rendered `.env`

## Service Metadata Schema

Each service in `services.d/` must return:
```nix
{
  name = "service-name";           # Required: unique identifier
  compose = {
    enable = true;                 # Enable docker-compose service
    path = "${config.homeserver.homeserverRoot}/services/..." or null; # null uses /var/lib/docker-services/<name>/docker-compose.yml
    networks = ["network-name"];   # External docker networks
    volumes = ["volume-name"];     # External docker volumes
  };
  files = {
    "prometheus_config.yml" = {
      source = ./prometheus_config.yml;
      destination = null;          # Defaults to key name when null
      executable = false;
    };
  };
  secretFiles = {
    ".env" = {
      template = ''vault-template-text''; # or readFile ./file.ctmpl
      destination = ".env";
      perms = "0400";
    };
    "deploy-key" = {
      template = ''{{ with secret "path" }}{{ .Data.data.key }}{{ end }}'';
      destination = "deploy-key";
      perms = "0400";
    };
  };
  backup = {
    enable = true;
    paths = ["/path/to/backup"];   # Files to backup
    volumes = ["docker-volume"];   # Docker volumes to backup
    tags = ["service-tag"];        # Restic tags
    pre = "script before backup";  # Pre-backup hook
    post = "script after backup";  # Post-backup hook
    exclude = ["*.log"];           # Exclude patterns
    policy = { daily = 10; weekly = 4; monthly = 4; };
  };
}
```

## Code Conventions
- Options defined in `hosts/homeserver/options.nix`
- Service paths: `${config.homeserver.homeserverRoot}/services/...`
- Package references: `${pkgs.docker}/bin/docker` not bare `docker`
- Pre/post hooks use heredoc strings with proper escaping
- Platform conditionals: `lib.mkIf pkgs.stdenv.isLinux { ... }`

## Security Requirements
- Secrets via Vault templates in `vault-agent.nix`, NEVER hardcode
- Secret files: `/var/lib/secrets/` with 0400 permissions
- Vault templating syntax: `{{ with secret "path" }}{{ .Data.data.key }}{{ end }}`
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

## svc CLI Tool

The `svc` module (`hosts/homeserver/backup/svc/`) is a Python CLI for managing service backups, restores, and lifecycle operations.

### Package Structure
```
svc/
├── svc.py                  # Entry point (~100 lines)
├── config.py               # Pydantic models for services.json
├── exceptions.py           # Custom exceptions + exit codes
├── cli/
│   ├── renderer.py         # Renderer protocol (Rich/Plain/future Textual)
│   ├── parser.py           # argparse setup with completers
│   └── commands/           # Command pattern implementations
│       ├── base.py         # AppContext + Command protocol
│       ├── list_cmd.py     # list, list-backups
│       ├── backup_cmd.py   # backup
│       ├── restore_cmd.py  # restore
│       └── service_cmd.py  # start/stop/restart/logs
├── core/                   # Business logic (no CLI knowledge)
│   ├── path_resolver.py    # Docker volume → filesystem path
│   ├── backup_orchestrator.py
│   ├── restore_orchestrator.py
│   ├── service_manager.py
│   └── service_helpers.py
└── controllers/            # External system interfaces (async)
    ├── systemctl.py        # SystemctlController
    ├── docker.py           # DockerController
    └── restic.py           # ResticRunner
```

### Commands
```bash
svc list                              # List services and backup status
svc list-backups <local|remote> <svc> # List snapshots for a service
svc backup <local|remote> <svc|all>   # Run backup
svc restore <local|remote> <svc> [id] # Restore from snapshot
svc start|stop|restart <svc|all>      # Manage docker-compose services
svc logs <svc> [--no-follow] [--tail] # Stream service logs
```

### Architecture Patterns
- **Async throughout**: All subprocess calls use `asyncio.create_subprocess_exec()` for Textual TUI compatibility
- **Renderer protocol**: Swap `RichRenderer` for `TextualRenderer` without changing business logic
- **Command pattern**: Add new commands by creating a file in `cli/commands/` and registering in `__init__.py`
- **Dependency injection**: `AppContext` provides controllers to commands
- **DRY service actions**: `start/stop/restart` share a single `ServiceActionCommand` base class

### Adding a New Command
1. Create `cli/commands/mycommand_cmd.py`:
```python
from .base import AppContext, Command

class MyCommand(Command):
    @property
    def name(self) -> str:
        return "mycommand"

    async def execute(self, args, ctx: AppContext) -> int:
        # Business logic here
        return 0
```
2. Register in `cli/commands/__init__.py`:
```python
from .mycommand_cmd import MyCommand
ALL_COMMANDS.append(MyCommand())
```
3. Add argparse subparser in `cli/parser.py`

### Configuration
The tool reads `/etc/svc/services.json` (generated by Nix from service metadata). Schema matches the `backup` section of service metadata plus `restore` config.
