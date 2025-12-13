{config, pkgs, lib, ...}: {
  name = "vault";
  compose = {
    enable = true;
    networks = ["internal"];
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
