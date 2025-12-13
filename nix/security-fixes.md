  ## [HIGH] filterWithSecretFiles can crash evaluation when compose = null

  File: hosts/homeserver/lib/docker.nix:60
  Issue: Predicate uses svc.compose.enable without guarding compose != null. Services like hosts/homeserver/services.d/music.nix have
  no compose, so compose defaults to null.
  Risk: NixOS evaluation/build can fail; deployment/secret registration can break unexpectedly.
  Remediation: Guard compose properly (or filter only on secretFiles if that’s the intent).

  Before:

  filterWithSecretFiles = services:
    lib.filterAttrs (
      _: svc: (svc.compose.enable or false) && (svc.secretFiles or {}) != {}
    ) services;

  After:

  filterWithSecretFiles = services:
    lib.filterAttrs (
      _: svc:
        (svc.compose or null) != null
        && (svc.compose.enable or false)
        && (svc.secretFiles or {}) != {}
    ) services;

  ———

  ## [HIGH] Service metadata does not match compose networks (Atuin)

  File: hosts/homeserver/services.d/atuin/default.nix:5
  Issue: compose.networks = [] but docker-compose.yml uses frontend and backend. Your prereq creation logic uses metadata to create
  external networks.
  Risk: Deploy may fail (network frontend not found) or drift between declared infra and runtime.
  Remediation: Align metadata with compose file (and consider asserting drift).

  Before:

  compose = {
    enable = true;
    networks = [];
  };

  After:

  compose = {
    enable = true;
    networks = ["frontend" "backend"];
  };

  ———

  ## [HIGH] watchtower has full Docker socket access

  File: hosts/homeserver/services.d/watchtower/docker-compose.yml:8
  Issue: Mounts /var/run/docker.sock read-write.
  Risk: Container compromise = host-level Docker control (create privileged containers, mount host FS, steal secrets).
  Remediation: Prefer removing Watchtower, or interpose a restricted docker-socket-proxy and point Watchtower at it.

  Before:

  volumes:
    - /var/run/docker.sock:/var/run/docker.sock

  After:

  # example direction: use a socket proxy instead of direct socket mount
  environment:
    - DOCKER_HOST=tcp://socket-proxy:2375

  ———

  ## [HIGH] promtail has Docker socket access (even if :ro)

  File: hosts/homeserver/services.d/grafana/docker-compose.yml:30
  Issue: Promtail mounts Docker socket.
  Risk: Significant attack surface; in many threat models, Docker socket read access is still too powerful (enumeration, metadata
  leaks; often escalates via daemon/API misuse depending on setup).
  Remediation: Use a socket proxy with least-permission endpoints, or switch to a logging approach that doesn’t require the socket.

  Before:

  - /var/run/docker.sock:/var/run/docker.sock:ro

  After:

  # example direction: point to restricted socket proxy instead
  environment:
    - DOCKER_HOST=tcp://socket-proxy:2375

  ———

  ## [MEDIUM] Vault listener runs with TLS disabled

  File: hosts/homeserver/services.d/vault/config/config.hcl:5
  Issue: tls_disable = 1 and binds 0.0.0.0:8200.
  Risk: If the Docker network is ever joined by an untrusted container (or traffic is observable), Vault tokens/secrets can be
  exposed.
  Remediation: Enable TLS in Vault (recommended), or ensure it’s only reachable via a trusted local proxy and the network is tightly
  controlled.

  Before:

  listener "tcp" {
    address     = "0.0.0.0:8200"
    tls_disable = 1
  }

  After:

  listener "tcp" {
    address = "0.0.0.0:8200"
    tls_disable = 0
    tls_cert_file = "/etc/vault/tls/cert.pem"
    tls_key_file  = "/etc/vault/tls/key.pem"
  }

  ———

  ## [LOW] services.nix allows silent duplicate service-name overrides

  File: hosts/homeserver/services.nix:91
  Issue: listToAttrs will keep the last duplicate key without warning.
  Risk: A service can silently disappear/override another; backup/deploy expectations drift.
  Remediation: Add an assertion that builtServices contains unique svcName.

  Before:

  rawServices = lib.listToAttrs (map (entry: { name = entry.svcName; value = entry.service; }) builtServices);

  After:

  assertions = [{
    assertion = lib.length (lib.unique (map (e: e.svcName) builtServices))
             == lib.length (map (e: e.svcName) builtServices);
    message = "Duplicate service name detected in services.d/";
  }];

  ———

  ## Review Summary

  | Severity | Count |
  |----------|-------|
  | Critical | 1     |
  | High     | 4     |
  | Medium   | 3     |
  | Low      | 1     |

  ### Top Priority Fixes

  1. [CRITICAL] hosts/homeserver/services.d/grafana/grafana.ini:691 remove/rotate leaked SMTP password.
  2. [HIGH] hosts/homeserver/lib/docker.nix:60 fix null-guard to avoid evaluation failures.
  3. [HIGH] hosts/homeserver/services.d/watchtower/docker-compose.yml:8 remove/contain Docker socket access.

  ### Positive Observations

  - Vault templating is used correctly in multiple services (secretFiles with 0400 defaults).
  - SSH is hardened (PasswordAuthentication = false, PermitRootLogin = no) and firewall ports are minimal.
  - Backups have structure (retention policies, service stop options, health-check style maintenance timers).


