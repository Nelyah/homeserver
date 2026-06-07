{...}: {
  name = "homeassistant";
  backup = {
    enable = true;
    kubernetes = {
      namespace = "homeassistant";
      deployments = ["homeassistant" "matter-server"];
      pvcs = ["homeassistant-config" "homeassistant-matter"];
    };
  };
}
