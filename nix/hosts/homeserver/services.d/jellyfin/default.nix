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
  secretFiles = {
    ".env" = {
      destination = ".env";
      template = ''
      MOVIE_FOLDER=/data/Movies/
      TVSHOWS_FOLDER=/data/TvShows/
      '';
    };
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
