{config, pkgs, lib, ...}: {
  name = "homeassistant";
  compose = {
    enable = true;
    networks = [];
    volumes = [
      "homeassistant_config"
      "homeassistant_matter"
    ];
  };
  backup = {
    enable = true;
    needsServiceStopped = true;
    volumes = [
      "homeassistant_config"
      "homeassistant_matter"
    ];
  };
}
