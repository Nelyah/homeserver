{config, pkgs, lib, ...}: {
  name = "navidrome";
  compose = {
    enable = true;
    networks = ["navidrome"];
    volumes = [
      "navidrome_data"
    ];
  };
  # navidrome uses paths, not secrets - include .env directly
  files = {
    ".env".source = ./.env;
  };
  backup = {
    enable = true;
    needsServiceStopped = true;
    volumes = [
      "navidrome_data"
    ];
  };
}
