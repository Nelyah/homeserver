{
  lib,
  pkgs,
  config,
  ...
}: let
  # Service metadata is declared in services.nix and must stay in sync with the
  # actual docker-compose.yml files (networks/volumes). External networks/volumes
  # are pre-created elsewhere so Compose can attach to them.
  servicesDef = (import ./services.nix {inherit lib config pkgs;}).attrset;
  enabledCompose =
    lib.filterAttrs (
      _: service: (service.compose or null) != null && (service.compose.enabled or false)
    )
    servicesDef;

  mkComposeService = name: service: let
    composeFile = service.compose.path;
    composeDir = builtins.dirOf composeFile;
  in {
    description = "docker-compose stack ${name}";
    after = [
      "docker.service"
      "network-online.target"
      "vault-agent.service"
    ];
    wants = [
      "network-online.target"
      "docker.service"
      "vault-agent.service"
    ];
    wantedBy = ["multi-user.target"];
    serviceConfig = {
      WorkingDirectory = composeDir;
      ExecStart = "${pkgs.docker-compose}/bin/docker-compose -f ${composeFile} up -d";
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
