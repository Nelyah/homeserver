# Service discovery and loading module
# Discovers services from services.d/ and populates config.homeserver.services
{
  lib,
  config,
  pkgs,
  ...
}: let
  servicesDir = builtins.path {
    path = ./services.d;
    name = "services-d";
  };

  # Read all entries in services.d/
  entries = builtins.readDir servicesDir;

  # Get service names: directories or .nix files (without extension)
  serviceNames = lib.filter (name:
    let entry = entries.${name}; in
    (entry == "directory") ||
    (entry == "regular" && lib.hasSuffix ".nix" name)
  ) (builtins.attrNames entries);

  # Normalize name (remove .nix extension if present)
  normalizeName = name:
    if lib.hasSuffix ".nix" name
    then lib.removeSuffix ".nix" name
    else name;

  # Load a service from either a directory or a .nix file
  loadService = name: let
    entry = entries.${name};
    isDir = entry == "directory";
    importPath =
      if isDir
      then servicesDir + "/${name}/default.nix"
      else servicesDir + "/${name}";
    serviceDir =
      if isDir
      then servicesDir + "/${name}"
      else null;
  in {
    raw = import importPath {inherit config pkgs lib;};
    inherit serviceDir isDir;
    entryName = name;
  };

  # Build service attrset from backup metadata modules.
  buildService = name: let
    loaded = loadService name;
    raw = loaded.raw;
    svcName = raw.name or (normalizeName name);
  in {
    inherit svcName;
    service = raw // {name = svcName;};
  };

  builtServices = map buildService serviceNames;

  # Attrset keyed by service name
  serviceNamesList = map (e: e.svcName) builtServices;
  rawServices = lib.listToAttrs (
    map (entry: {
      name = entry.svcName;
      value = entry.service;
    })
    builtServices
  );

in {
  config.assertions = [
    {
      assertion = lib.length (lib.unique serviceNamesList) == lib.length serviceNamesList;
      message = "Duplicate service name detected in services.d/";
    }
  ];

  # Set the services config directly - options.nix provides the schema
  config.homeserver.services = rawServices;
}
