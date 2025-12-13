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

- List restic snapshots for a service: `sudo bash -c 'source /var/lib/secrets/restic/local.env && restic snapshots --tag <service>'`
- Restore latest snapshot: `sudo restore <local|remote> <service> latest`
- Restore specific snapshot: `sudo restore <local|remote> <service> <SNAPSHOT_ID>`
- Default restore does **not** delete extra files; pass `--delete` to make the target match the snapshot.
- `restore` stops/starts `docker-compose-<service>.service` when compose is enabled.

## Resources

- [nix-darwin manual](https://nix-darwin.github.io/nix-darwin/manual/)
- [home-manager manual](https://nix-community.github.io/home-manager/)
- [Nix manual](https://nixos.org/manual/nix/stable/)
- [NixOS package search](https://search.nixos.org/packages)
