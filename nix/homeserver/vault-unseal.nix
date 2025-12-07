{
  pkgs,
  config,
  ...
}:
let
  tokenFile = "${config.homeserver.vault.unsealTokenPath}";
  unsealScript = pkgs.writeShellScript "unseal-vault" ''
    #!${pkgs.bash}/bin/bash
    set -euo pipefail
    VAULT_ADDR="${config.homeserver.vault.address}"
    if [[ ! -f "${tokenFile}" ]]; then
      echo "unseal token not found at ${tokenFile}" >&2
      exit 1
    fi
    token="$(cat ${tokenFile})"
    sealed="$(${pkgs.curl}/bin/curl -s ${config.homeserver.vault.address}/v1/sys/health | ${pkgs.jq}/bin/jq -r .sealed)"
    if [[ "$sealed" != "true" ]]; then
      exit 0
    fi
    ${pkgs.curl}/bin/curl -s --fail \
      --request PUT \
      --header "Content-Type: application/json" \
      --data "{\"key\":\"${"$"}{token}\"}" \
      ${config.homeserver.vault.address}/v1/sys/unseal >/dev/null
  '';
in
{
  systemd.services.vault-unseal = {
    description = "Unseal Vault instance";
    after = [
      "docker-compose-vault.service"
      "network-online.target"
    ];
    wants = [
      "docker-compose-vault.service"
      "network-online.target"
    ];
    serviceConfig = {
      Type = "oneshot";
      ExecStart = unsealScript;
    };
  };

  systemd.timers.vault-unseal = {
    wantedBy = [ "timers.target" ];
    timerConfig = {
      OnBootSec = "10min";
      OnUnitActiveSec = "10min";
    };
  };
}
