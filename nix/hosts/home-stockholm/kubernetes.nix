{
  pkgs,
  config,
  ...
}: {
  services.k3s = {
    enable = true;
    role = "server";
    clusterInit = true;
    extraFlags = [
      "--disable=traefik"
      "--disable=servicelb"
      "--write-kubeconfig-mode=0644"
      "--default-local-storage-path=${config.homeserver.mainDrive}/k3s/storage"
    ];
  };

  environment.systemPackages = with pkgs; [
    helmfile
    k3s
    k9s # TUI for kubernetes
    kubectl
    kubernetes-helm
  ];

  systemd.services.homeserver-local-image-refresh = {
    description = "Build and import homeserver local Kubernetes images";
    path = with pkgs; [
      docker
      k3s
      kubectl
      sudo
    ];
    environment.KUBECONFIG = "/etc/rancher/k3s/k3s.yaml";
    serviceConfig = {
      Type = "oneshot";
      WorkingDirectory = config.server.repoRoot;
      ExecStart = "${config.server.repoRoot}/k8s/build-local-images.sh";
    };
    wants = [
      "docker.service"
      "k3s.service"
      "network-online.target"
    ];
    after = [
      "docker.service"
      "k3s.service"
      "network-online.target"
    ];
  };

  systemd.timers.homeserver-local-image-refresh = {
    wantedBy = ["timers.target"];
    timerConfig = {
      OnCalendar = "04:30";
      Persistent = true;
      RandomizedDelaySec = "30m";
    };
  };
}
