{config, pkgs, lib, ...}: {
  name = "vault";
  compose = {
    enable = true;
    # Keep Vault off shared Docker networks; Caddy reaches it via the host loopback bind in docker-compose.yml.
    # This reduces the blast radius if any other container joins a "trusted" network.
    networks = [];
    volumes = ["vault_data"];
  };
  files = {
    "config".source = ./config;
  };
  backup = {
    enable = true;
    needsServiceStopped = true;
    volumes = ["vault_data"];
  };
}
