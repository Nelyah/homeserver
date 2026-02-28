# Backup system module
{pkgs, ...}: let
  svcPackage = import ./svc {inherit pkgs;};
in {
  imports = [
    ./config.nix # Generates /etc/svc/services.json
    ./svc-backup.nix # Scheduled backups using `svc`
    ./maintenance.nix
  ];

  environment.systemPackages = [svcPackage];
}
