{...}: {
  name = "jellyfin";
  backup = {
    enable = true;
    kubernetes = {
      namespace = "jellyfin";
      deployments = [
        "jellyfin"
        "prowlarr"
        "sonarr"
        "radarr"
        "bazarr"
        "qbittorrent"
        "jellyseerr"
      ];
      pvcs = [
        "jellyfin-config"
        "jellyfin-cache"
        "prowlarr-config"
        "sonarr-config"
        "radarr-config"
        "bazarr-config"
        "qbittorrent-config"
        "jellyseerr-config"
      ];
    };
  };
}
