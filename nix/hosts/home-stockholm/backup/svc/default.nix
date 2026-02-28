# Nix derivation for the svc CLI tool
{pkgs, ...}:
let
  pythonEnv = pkgs.python3.withPackages (ps: [
    ps.click
    ps.pydantic
    ps.rich
    (ps.buildPythonPackage {
      pname = "svc";
      version = "1.0.0";
      src = ./.;
      format = "other";
      doCheck = false;

      installPhase = ''
        runHook preInstall

        site="$out/${ps.python.sitePackages}"
        mkdir -p "$site"
        cp -r ${./svc} "$site/svc"

        runHook postInstall
      '';
    })
  ]);
in
  pkgs.writeShellApplication {
    name = "svc";
    runtimeInputs = [pythonEnv];
    text = ''
      exec ${pythonEnv}/bin/python3 -m svc.svc "$@"
    '';
  }
