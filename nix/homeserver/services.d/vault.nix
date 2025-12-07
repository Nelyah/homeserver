{ config, ... }:
{
  name = "vault";
  compose = {
    enable = true;
    path = "${config.homeserver.homeserverRoot}/services/vault/docker-compose.yml";
    networks = [ "internal" ];
    volumes = [ "vault_data" ];
  };
  backup = {
    enable = true;
    volumes = [ "vault_data" ];
  };
}
