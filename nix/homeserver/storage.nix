{ lib, config, ... }:
{
  fileSystems."${config.homeserver.mainDrive}" = {
    device = "/dev/disk/by-uuid/52154ddd-f269-459e-88d9-19b7dbfc2c65";
    fsType = "ext4";
    options = [
      "nofail"
      "x-systemd.automount"
    ];
    neededForBoot = false;
  };

  fileSystems."${config.homeserver.backupDrive}" = {
    device = "/dev/disk/by-uuid/c51e82c3-e726-4d66-ac21-9425c0c7520b";
    fsType = "ext4";
    options = [
      "nofail"
      "x-systemd.automount"
      "x-systemd.idle-timeout=5min"
    ];
    neededForBoot = false;
  };

}
