{...}: {
  name = "homeassistant";
  backup = {
    enable = true;
    kubernetes = {
      namespace = "homeassistant";
      deployments = ["homeassistant" "matter-server" "otbr"];
      pvcs = ["homeassistant-config" "homeassistant-matter" "homeassistant-otbr"];
    };
  };
}
