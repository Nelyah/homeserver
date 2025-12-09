{
  lib,
  config,
}: let
  servicesDir = builtins.path {
    path = ./services.d;
    name = "services-d";
  };
  # Load all *.nix service files from services.d/
  serviceFiles = builtins.readDir servicesDir;
  nixServices = lib.filterAttrs (_: v: v == "regular") serviceFiles;
  names = builtins.filter (n: lib.hasSuffix ".nix" n) (builtins.attrNames nixServices);

  raw = name: import (servicesDir + "/" + name) {inherit config;};

  assertListOfStrings = label: val:
    if lib.isList val && lib.all lib.isString val
    then val
    else builtins.throw "${label} must be a list of strings";

  assertString = label: val:
    if lib.isString val
    then val
    else builtins.throw "${label} must be a string";

  assertPolicy = name: policy:
    if policy == null
    then null
    else {
      last = policy.last or null;
      hourly = policy.hourly or null;
      daily = policy.daily or null;
      weekly = policy.weekly or null;
      monthly = policy.monthly or null;
      yearly = policy.yearly or null;
    };

  validate = svc: let
    baseName = assertString "service.name" svc.name;
    compose =
      if svc ? compose && svc.compose != null
      then {
        enabled = svc.compose.enabled or false;
        path = assertString "${baseName}.compose.path" svc.compose.path;
        networks = assertListOfStrings "${baseName}.compose.networks" (svc.compose.networks or []);
        volumes = assertListOfStrings "${baseName}.compose.volumes" (svc.compose.volumes or []);
      }
      else null;
    backup =
      if svc ? backup && svc.backup != null
      then {
        enabled = svc.backup.enabled or false;
        paths = assertListOfStrings "${baseName}.backup.paths" (svc.backup.paths or []);
        volumes = assertListOfStrings "${baseName}.backup.volumes" (svc.backup.volumes or []);
        tags = assertListOfStrings "${baseName}.backup.tags" (svc.backup.tags or [baseName]);
        pre = assertString "${baseName}.backup.pre" (svc.backup.pre or "");
        post = assertString "${baseName}.backup.post" (svc.backup.post or "");
        exclude = assertListOfStrings "${baseName}.backup.exclude" (svc.backup.exclude or []);
        policy = assertPolicy "${baseName}.backup.policy" (
          svc.backup.policy or {
            daily = 10;
            weekly = 4;
            monthly = 4;
          }
        );
      }
      else null;
  in {
    name = baseName;
    inherit compose backup;
  };

  services = map (file: validate (raw file)) names;
in {
  list = services;
  attrset = lib.listToAttrs (
    map (s: {
      name = s.name;
      value = s;
    })
    services
  );
}
