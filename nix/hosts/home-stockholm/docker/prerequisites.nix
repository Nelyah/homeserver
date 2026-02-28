# Create external Docker networks and volumes for compose stacks
{
  pkgs,
  lib,
  config,
  ...
}: let
  homeserverLib = import ../lib { inherit lib; };

  # Read services from config (populated by services.nix module)
  services = config.homeserver.services;
  enabledCompose = homeserverLib.docker.filterEnabledCompose services;

  networks = homeserverLib.docker.collectNetworks enabledCompose;
  volumes = homeserverLib.docker.collectVolumes enabledCompose;
in {
  # Create external networks/volumes referenced by compose stacks.
  # Run as a systemd oneshot so we can order it after docker.service and get logs in journald.
  systemd.services.docker-prereqs = {
    description = "Create external Docker networks/volumes for compose stacks";
    after = ["docker.service"];
    wants = ["docker.service"];
    wantedBy = ["multi-user.target"];

    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      Restart = "on-failure";
      RestartSec = "5s";
    };

    script =
      homeserverLib.docker.mkPrereqScript {
        dockerBin = "${pkgs.docker}/bin/docker";
        inherit networks volumes;
      };
  };
}
