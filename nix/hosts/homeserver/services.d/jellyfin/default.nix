{config, pkgs, lib, ...}: {
  name = "jellyfin";
  compose = {
    enable = true;
    networks = ["frontend"];
    volumes = [
      "jellyfin_config"
      "jellyfin_cache"
    ];
  };
  backup = {
    enable = true;
    needsServiceStopped = true;
    volumes = [
      "jellyfin_config"
      "jellyfin_cache"
    ];
  };
}
