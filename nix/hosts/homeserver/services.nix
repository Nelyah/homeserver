{
  lib,
  config,
  pkgs,
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

  # Build service attrset with auto-detected files/env templates
  buildService = name: let
    loaded = loadService name;
    raw = loaded.raw;
    svcName = raw.name or (normalizeName name);

    explicitFiles = raw.files or {};
    autoComposeFile =
      if loaded.isDir && loaded.serviceDir != null
         && builtins.pathExists (loaded.serviceDir + "/docker-compose.yml")
         && !(explicitFiles ? "docker-compose.yml")
      then {
        "docker-compose.yml" = {
          source = loaded.serviceDir + "/docker-compose.yml";
          destination = null;
          executable = false;
        };
      }
      else {};
    files = autoComposeFile // explicitFiles;

    explicitSecretFiles = raw.secretFiles or {};
    autoEnvSecret =
      if loaded.isDir && loaded.serviceDir != null
         && builtins.pathExists (loaded.serviceDir + "/.env.ctmpl")
         && !(explicitSecretFiles ? ".env")
      then {
        ".env" = {
          destination = ".env";
          perms = "0400";
          template = builtins.readFile (loaded.serviceDir + "/.env.ctmpl");
        };
      }
      else {};
    secretFiles = explicitSecretFiles // autoEnvSecret;
  in {
    inherit svcName;
    service = raw // {name = svcName; files = files; secretFiles = secretFiles;};
  };

  builtServices = map buildService serviceNames;

  # Attrset keyed by service name
  rawServices = lib.listToAttrs (
    map (entry: {
      name = entry.svcName;
      value = entry.service;
    })
    builtServices
  );

  # Use the typed option (from options.nix) to validate and apply defaults
  optionsModule = import ./options.nix {inherit lib;};
  validated = lib.evalModules {
    modules = [
      {
        options = optionsModule.options;
        config.homeserver.services = rawServices;
      }
    ];
  };

  servicesAttr = validated.config.homeserver.services;
  servicesList = map (n: servicesAttr.${n}) (lib.attrNames servicesAttr);
in {
  list = servicesList;
  attrset = servicesAttr;
}
