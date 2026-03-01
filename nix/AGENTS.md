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

