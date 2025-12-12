# Register vault secrets for docker services
# Vault-agent will render these to /var/lib/secrets/docker-services/<name>/
{
  lib,
  config,
  ...
}: let
  homeserverLib = import ../lib { inherit lib; };

  # Read services from config (populated by services.nix module)
  services = config.homeserver.services;

  # Filter services with secret files defined
  servicesWithSecretFiles = homeserverLib.docker.filterWithSecretFiles services;

in lib.mkIf (servicesWithSecretFiles != {}) {
  # Register vault secrets for services with secret files
  homeserver.vault.secrets = lib.foldAttrs (a: b: a // b) {} (lib.mapAttrsToList (name: svc:
    lib.mapAttrs' (_fname: spec: {
      name = "docker-service-${name}-${lib.replaceStrings ["/"] ["-"] spec.destination}";
      value = {
        template = spec.template;
        destination = "docker-services/${name}/${spec.destination}";
        perms = spec.perms;
      };
    }) (svc.secretFiles or {})
  ) servicesWithSecretFiles);
}
