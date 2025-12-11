{config, pkgs, lib, ...}: {
  name = "uptime_kuma";
  compose = {
    enable = true;
    networks = ["internal"];
    volumes = ["uptime_kuma_data"];
  };
  backup = {
    enable = true;
    volumes = ["uptime_kuma_data"];
    policy = {
      daily = 10;
      weekly = 25;
      monthly = 12;
    };
  };
}
