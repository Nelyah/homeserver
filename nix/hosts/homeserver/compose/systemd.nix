# Docker Compose systemd service generation
{
  lib,
  pkgs,
  config,
  ...
}: let
  # Use centralized paths from options
  deployRoot = config.homeserver.paths.deployRoot;

  # Read services from config (populated by services.nix module)
  # Service metadata is declared in services.d/ and must stay in sync with the
  # actual docker-compose.yml files (networks/volumes). External networks/volumes
  # are pre-created elsewhere so Compose can attach to them.
  services = config.homeserver.services;
  enabledCompose =
    lib.filterAttrs (
      _: service: (service.compose or null) != null && (service.compose.enable or false)
    )
    services;

  mkComposeService = name: service: let
    # Auto-derive compose path from deployment location if not explicitly set
    composeFile =
      if service.compose.path != null
      then service.compose.path
      else "${deployRoot}/${name}/docker-compose.yml";
    composeDir = builtins.dirOf composeFile;
    buildArg = lib.optionalString (service.compose.build or false) " --build";

    # Service needs vault-agent if it has secret files to render
    needsVault = (service.secretFiles or {}) != {};
  in {
    description = "docker-compose stack ${name}";
    after = [
      "docker.service"
      "network-online.target"
    ] ++ lib.optional needsVault "vault-agent.service";
    wants = [
      "network-online.target"
      "docker.service"
    ] ++ lib.optional needsVault "vault-agent.service";
    wantedBy = ["multi-user.target"];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      WorkingDirectory = composeDir;
      ExecStart = "${pkgs.docker-compose}/bin/docker-compose -f ${composeFile} up -d --remove-orphans --force-recreate${buildArg}";
      ExecStop = "${pkgs.docker-compose}/bin/docker-compose -f ${composeFile} down --remove-orphans";
      Restart = "on-failure";
    };
  };
in {
  systemd.services =
    lib.mapAttrs' (name: service: {
      name = "docker-compose-${name}";
      value = mkComposeService name service;
    })
    enabledCompose;
}
