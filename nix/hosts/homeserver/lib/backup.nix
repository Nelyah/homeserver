# Pure helper functions for backup script generation
# These functions take data and return strings - no pkgs or config dependencies
{ lib }:

{
  # Build restic forget flags from a policy attrset
  # policy: { last?, hourly?, daily?, weekly?, monthly?, yearly? }
  # Returns: "--keep-daily 10 --keep-weekly 4 --prune" etc.
  mkForgetFlags = policy:
    if policy == null
    then ""
    else lib.concatStringsSep " " (lib.filter (s: s != "") [
      (lib.optionalString ((policy.last or null) != null) "--keep-last ${toString policy.last}")
      (lib.optionalString ((policy.hourly or null) != null) "--keep-hourly ${toString policy.hourly}")
      (lib.optionalString ((policy.daily or null) != null) "--keep-daily ${toString policy.daily}")
      (lib.optionalString ((policy.weekly or null) != null) "--keep-weekly ${toString policy.weekly}")
      (lib.optionalString ((policy.monthly or null) != null) "--keep-monthly ${toString policy.monthly}")
      (lib.optionalString ((policy.yearly or null) != null) "--keep-yearly ${toString policy.yearly}")
      "--prune"
    ]);

  # Build restic tag flags from a list of tags
  # tags: ["service-name" "extra-tag"]
  # Returns: "--tag service-name --tag extra-tag"
  mkTagFlags = tags:
    lib.concatMapStringsSep " " (t: "--tag ${t}") tags;

  # Build restic exclude flags from a list of patterns
  # excludes: ["*.log" "cache/"]
  # Returns: "--exclude '*.log' --exclude 'cache/'"
  mkExcludeFlags = excludes:
    lib.concatMapStringsSep " " (p: "--exclude '${p}'") excludes;

  # Build backup paths from volumes and explicit paths
  # dockerVolumesRoot: "/data/docker-data/volumes"
  # volumes: ["nextcloud_data" "nextcloud_db"]
  # paths: ["/tmp/dump.sql"]
  # Returns: ["/data/docker-data/volumes/nextcloud_data/" "/data/docker-data/volumes/nextcloud_db/" "/tmp/dump.sql"]
  mkBackupPaths = { dockerVolumesRoot, volumes, paths }:
    (map (v: "${dockerVolumesRoot}/${v}/") volumes) ++ paths;

  # Build the backup arguments string
  mkBackupArgsStr = { dockerVolumesRoot, volumes, paths }:
    lib.concatStringsSep " " (
      (map (v: "${dockerVolumesRoot}/${v}/") volumes) ++ paths
    );
}
