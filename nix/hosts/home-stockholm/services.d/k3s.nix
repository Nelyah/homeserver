{pkgs, ...}: {
  name = "k3s";
  backup = {
    enable = true;
    preBackupCommands = [
      [
        "${pkgs.k3s}/bin/k3s"
        "etcd-snapshot"
        "save"
        "--name"
        "svc-backup"
        "--snapshot-retention"
        "5"
      ]
    ];
    paths = [
      "/var/lib/rancher/k3s/server/db/snapshots"
      "/var/lib/rancher/k3s/server/token"
    ];
    tags = ["k3s" "cluster-state"];
    restore = {
      paths = [];
    };
  };
}
