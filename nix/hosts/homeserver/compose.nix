{
  lib,
  pkgs,
  config,
  ...
}: let
  deployRoot = "/var/lib/docker-services";

  # Service metadata is declared in services.nix and must stay in sync with the
  # actual docker-compose.yml files (networks/volumes). External networks/volumes
  # are pre-created elsewhere so Compose can attach to them.
  servicesDef = (import ./services.nix {inherit lib config pkgs;}).attrset;
  enabledCompose =
    lib.filterAttrs (
      _: service: (service.compose or null) != null && (service.compose.enable or false)
    )
    servicesDef;

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
      WorkingDirectory = composeDir;
      ExecStart = "${pkgs.docker-compose}/bin/docker-compose -f ${composeFile} up${buildArg}";
      ExecStop = "${pkgs.docker-compose}/bin/docker-compose -f ${composeFile} stop";
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
