# Nix Configuration

## Usage

To build this nix configuration:
```sh
# Defaults to current hostname
./nix-build.sh [hostname]
```

To rollback to the previous version
```sh
./nix-rollback.sh [hostname]
```

## Backups / Restore (homeserver)

- List configured backup services: `svc list`
- List restic snapshots for a service: `svc list-backups <local|remote> <service>`
- Run backups: `sudo svc backup <local|remote> <service|all>`
- Restore latest snapshot: `sudo svc restore <local|remote> <service> latest`
- Restore specific snapshot: `sudo svc restore <local|remote> <service> <SNAPSHOT_ID>`
- Kubernetes PVC backups scale configured deployments down, back up the PVC backing paths, and restore deployments afterwards.

## Resources

- [nix-darwin manual](https://nix-darwin.github.io/nix-darwin/manual/)
- [home-manager manual](https://nix-community.github.io/home-manager/)
- [Nix manual](https://nixos.org/manual/nix/stable/)
- [NixOS package search](https://search.nixos.org/packages)
