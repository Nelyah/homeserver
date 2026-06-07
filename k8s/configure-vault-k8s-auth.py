#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import json
import os
import pwd
import re
import shlex
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
POLICY_PREFIX = "homeserver-"
ROLE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
MOUNT_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
PATH_RE = re.compile(r"^[A-Za-z0-9_.@/-]+$")


@dataclass(frozen=True, order=True)
class SecretPath:
    mount: str
    path: str


@dataclass(frozen=True)
class Role:
    name: str
    namespace: str
    service_account: str
    secrets: tuple[SecretPath, ...]

    @property
    def policy(self) -> str:
        return f"{POLICY_PREFIX}{self.name}"


def die(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def run(args: list[str], env: dict[str, str], *, stdin: str | None = None, capture: bool = False) -> str:
    try:
        result = subprocess.run(
            args,
            cwd=ROOT,
            env=env,
            input=stdin,
            text=True,
            check=True,
            capture_output=capture,
        )
    except FileNotFoundError:
        die(f"required command not found: {args[0]}")
    except subprocess.CalledProcessError as exc:
        if capture and exc.stdout:
            print(exc.stdout, file=sys.stderr, end="")
        if capture and exc.stderr:
            print(exc.stderr, file=sys.stderr, end="")
        die(f"command failed ({exc.returncode}): {shlex.join(args)}")
    return result.stdout if capture else ""


def default_kubeconfig(explicit: str | None) -> str:
    if explicit:
        return explicit
    if os.environ.get("KUBECONFIG"):
        return os.environ["KUBECONFIG"]
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user and sudo_user != "root":
        try:
            return str(Path(pwd.getpwnam(sudo_user).pw_dir) / ".kube/config")
        except KeyError:
            pass
    return str(Path.home() / ".kube/config")


def read_token(token_file: str) -> str:
    if os.environ.get("VAULT_TOKEN"):
        return os.environ["VAULT_TOKEN"].strip()
    try:
        token = Path(token_file).read_text().strip()
    except OSError as exc:
        die(
            f"Vault token is not readable: {token_file}\n"
            f"{exc}\n"
            "Run with sudo, or set VAULT_TOKEN to a token that can write "
            "auth/kubernetes roles and policies."
        )
    if not token:
        die(f"Vault token file is empty: {token_file}")
    return token


class VaultError(RuntimeError):
    pass


class Vault:
    def __init__(self, addr: str, token: str):
        self.addr = addr.rstrip("/")
        self.token = token

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        expected: tuple[int, ...] = (200, 204),
    ) -> dict[str, object]:
        url = f"{self.addr}/v1/{path.lstrip('/')}"
        data = None
        headers = {"X-Vault-Token": self.token}
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return self._parse_response(response.status, response.read(), expected, url)
        except urllib.error.HTTPError as exc:
            return self._parse_response(exc.code, exc.read(), expected, url)
        except urllib.error.URLError as exc:
            raise VaultError(f"failed to connect to Vault at {self.addr}: {exc}") from exc

    def data(self, method: str, path: str) -> dict[str, object]:
        response = self.request(method, path)
        data = response.get("data", response)
        if not isinstance(data, dict):
            return {}
        return data

    @staticmethod
    def _parse_response(status: int, body: bytes, expected: tuple[int, ...], url: str) -> dict[str, object]:
        text = body.decode(errors="replace")
        parsed: dict[str, object] = {}
        if text:
            try:
                value = json.loads(text)
                if isinstance(value, dict):
                    parsed = value
            except json.JSONDecodeError:
                parsed = {"errors": [text]}

        if status not in expected:
            errors = parsed.get("errors")
            detail = f": {errors}" if errors else f": {text}" if text else ""
            raise VaultError(f"Vault request failed ({status}) {url}{detail}")
        return parsed


def vault_health(addr: str, timeout: float = 2.0) -> bool:
    url = (
        f"{addr.rstrip('/')}/v1/sys/health"
        "?standbyok=true&sealedcode=200&uninitcode=200"
    )
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except urllib.error.HTTPError:
        return True
    except urllib.error.URLError:
        return False


def vault_service_addr(env: dict[str, str]) -> str | None:
    service = json.loads(
        run(["kubectl", "-n", "vault", "get", "service", "vault", "-o", "json"], env, capture=True)
    )
    spec = service.get("spec", {})
    if not isinstance(spec, dict):
        return None

    cluster_ip = spec.get("clusterIP")
    if not isinstance(cluster_ip, str) or cluster_ip in {"", "None"}:
        return None

    ports = spec.get("ports", [])
    if not isinstance(ports, list) or not ports:
        return None

    selected = next(
        (port for port in ports if isinstance(port, dict) and port.get("name") == "http"),
        ports[0],
    )
    if not isinstance(selected, dict) or not isinstance(selected.get("port"), int):
        return None

    return f"http://{cluster_ip}:{selected['port']}"


def free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextlib.contextmanager
def port_forward_vault(env: dict[str, str]):
    port = free_local_port()
    addr = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        [
            "kubectl",
            "-n",
            "vault",
            "port-forward",
            "--address",
            "127.0.0.1",
            "service/vault",
            f"{port}:80",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if vault_health(addr, timeout=0.5):
                print(f"Using Vault service through local port-forward: {addr}")
                yield addr
                return
            if proc.poll() is not None:
                output = proc.stdout.read() if proc.stdout else ""
                die(f"kubectl port-forward exited before Vault was reachable:\n{output}")
            time.sleep(0.2)
        die("timed out waiting for Vault port-forward to become reachable")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


@contextlib.contextmanager
def vault_addr(args: argparse.Namespace, env: dict[str, str]):
    if args.vault_addr:
        yield args.vault_addr.rstrip("/")
        return

    direct = vault_service_addr(env)
    if direct and vault_health(direct):
        print(f"Using Vault service ClusterIP: {direct}")
        yield direct
        return

    if direct:
        print(f"Vault service ClusterIP is not reachable from here: {direct}")
    with port_forward_vault(env) as addr:
        yield addr


def render(args: argparse.Namespace, env: dict[str, str]) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if args.rendered:
        path = Path(args.rendered)
        if not path.is_file():
            die(f"rendered manifest file is not readable: {path}")
        return path, None

    tmp = tempfile.TemporaryDirectory(prefix="vault-k8s-auth.")
    path = Path(tmp.name) / "rendered.yaml"
    print("Rendering Helm manifests for Vault auth discovery.")
    path.write_text(run(["helmfile", "--file", "helmfile.yaml", "template"], env, capture=True))
    return path, tmp


def rendered_docs(path: Path, env: dict[str, str]) -> list[dict[str, object]]:
    raw = run(["yq", "-c", ".", str(path)], env, capture=True)
    docs: list[dict[str, object]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        doc = json.loads(line)
        if isinstance(doc, dict):
            docs.append(doc)
    return docs


def nested(doc: dict[str, object], dotted: str) -> object:
    value: object = doc
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def required_string(doc: dict[str, object], dotted: str, kind: str) -> str:
    value = nested(doc, dotted)
    if not isinstance(value, str) or not value:
        die(f"{kind} is missing required string field: {dotted}")
    return value


def discover(path: Path, env: dict[str, str]) -> list[Role]:
    auths: dict[tuple[str, str], tuple[str, str]] = {}
    roles_seen: dict[str, str] = {}
    pending_secrets: list[tuple[tuple[str, str], SecretPath]] = []

    for doc in rendered_docs(path, env):
        kind = doc.get("kind")
        if kind == "VaultAuth":
            ns = required_string(doc, "metadata.namespace", "VaultAuth")
            name = required_string(doc, "metadata.name", "VaultAuth")
            role = required_string(doc, "spec.kubernetes.role", "VaultAuth")
            service_account = required_string(doc, "spec.kubernetes.serviceAccount", "VaultAuth")

            if not ROLE_RE.fullmatch(role):
                die(f"Vault role name contains unsupported characters: {role}")
            if (ns, name) in auths:
                die(f"duplicate VaultAuth resource rendered: {ns}/{name}")
            if role in roles_seen:
                die(f"duplicate Vault Kubernetes auth role rendered: {role}")

            auths[(ns, name)] = (role, service_account)
            roles_seen[role] = f"{ns}/{name}"

        elif kind == "VaultStaticSecret":
            ns = required_string(doc, "metadata.namespace", "VaultStaticSecret")
            auth_ref = required_string(doc, "spec.vaultAuthRef", "VaultStaticSecret")
            mount = nested(doc, "spec.mount") or "homeserver_secrets"
            path_value = required_string(doc, "spec.path", "VaultStaticSecret")

            if not isinstance(mount, str) or not MOUNT_RE.fullmatch(mount):
                die(f"Vault secret mount contains unsupported characters: {mount}")
            if not PATH_RE.fullmatch(path_value):
                die(f"Vault secret path contains unsupported characters: {mount}/{path_value}")

            pending_secrets.append(((ns, auth_ref), SecretPath(mount, path_value)))

    secrets_by_auth: dict[tuple[str, str], set[SecretPath]] = defaultdict(set)
    for auth_key, secret in pending_secrets:
        if auth_key not in auths:
            die(f"VaultStaticSecret references missing VaultAuth: {auth_key[0]}/{auth_key[1]}")
        secrets_by_auth[auth_key].add(secret)

    roles = [
        Role(role, ns, service_account, tuple(sorted(secrets_by_auth[key])))
        for key, (role, service_account) in auths.items()
        for ns, _name in [key]
        if secrets_by_auth.get(key)
    ]
    roles.sort(key=lambda role: role.name)

    if not roles:
        die("no VaultAuth roles with VaultStaticSecret paths were discovered; refusing to continue")
    return roles


def print_plan(roles: list[Role]) -> None:
    print(f"Discovered {len(roles)} Vault auth role(s).")
    for role in roles:
        paths = ", ".join(f"{secret.mount}/{secret.path}" for secret in role.secrets)
        print(f"- {role.name} ({role.namespace}/{role.service_account}): {paths}")


def vault_path(*parts: str) -> str:
    return "/".join(urllib.parse.quote(part, safe="") for part in parts)


def policy_hcl(role: Role) -> str:
    return "".join(
        f'path "{secret.mount}/data/{secret.path}" {{\n'
        '  capabilities = ["read"]\n'
        "}\n\n"
        for secret in role.secrets
    )


def sync_vault(vault: Vault, roles: list[Role], *, prune: bool, kubernetes_host: str) -> None:
    auths = vault.data("GET", "sys/auth")
    if "kubernetes/" not in auths:
        vault.request("POST", "sys/auth/kubernetes", {"type": "kubernetes"})

    vault.request(
        "POST",
        "auth/kubernetes/config",
        {
            "kubernetes_host": kubernetes_host,
            "disable_iss_validation": True,
        },
    )

    mounts = vault.data("GET", "sys/mounts")
    for mount in sorted({secret.mount for role in roles for secret in role.secrets}):
        if f"{mount}/" not in mounts:
            vault.request(
                "POST",
                vault_path("sys/mounts", mount),
                {"type": "kv", "options": {"version": "2"}},
            )

    for role in roles:
        vault.request(
            "PUT",
            vault_path("sys/policies/acl", role.policy),
            {"policy": policy_hcl(role)},
        )
        vault.request(
            "POST",
            vault_path("auth/kubernetes/role", role.name),
            {
                "bound_service_account_names": role.service_account,
                "bound_service_account_namespaces": role.namespace,
                "policies": role.policy,
                "ttl": "24h",
            },
        )

    if prune:
        desired = {role.policy for role in roles}
        policies = vault.data("LIST", "sys/policies/acl").get("keys", [])
        if not isinstance(policies, list):
            return
        for policy in sorted(str(policy) for policy in policies):
            if not policy.startswith(POLICY_PREFIX) or policy in desired:
                continue
            role = policy.removeprefix(POLICY_PREFIX)
            print(f"- pruning stale Vault role/policy: {role} / {policy}")
            vault.request("DELETE", vault_path("auth/kubernetes/role", role), expected=(200, 204, 404))
            vault.request("DELETE", vault_path("sys/policies/acl", policy), expected=(200, 204, 404))


def apply(roles: list[Role], args: argparse.Namespace, env: dict[str, str]) -> None:
    token = read_token(args.token_file)

    print("Applying Vault TokenReview RBAC.")
    run(["kubectl", "apply", "-f", "vault/global/vault-tokenreview.yaml"], env)

    print("Synchronizing Vault Kubernetes auth roles.")
    try:
        with vault_addr(args, env) as addr:
            sync_vault(
                Vault(addr, token),
                roles,
                prune=not args.no_prune,
                kubernetes_host=args.kubernetes_host,
            )
    except VaultError as exc:
        die(str(exc))

    print("Restarting Vault Secrets Operator reconciliation.")
    run(
        [
            "kubectl", "-n", "vault-secrets-operator-system", "rollout", "restart",
            "deployment/vault-secrets-operator-controller-manager",
        ],
        env,
    )
    run(
        [
            "kubectl", "-n", "vault-secrets-operator-system", "rollout", "status",
            "deployment/vault-secrets-operator-controller-manager", "--timeout=180s",
        ],
        env,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synchronize Vault Kubernetes auth from Helm manifests.")
    parser.add_argument("--kubeconfig")
    parser.add_argument("--vault-addr", default=os.environ.get("VAULT_ADDR"), help="Vault API address")
    parser.add_argument(
        "--kubernetes-host",
        default="https://kubernetes.default.svc:443",
        help="Kubernetes API address Vault should use from inside the cluster",
    )
    parser.add_argument("--rendered", help="use an already-rendered manifest file")
    parser.add_argument("--dry-run", action="store_true", help="discover and print the plan only")
    parser.add_argument("--no-prune", action="store_true", help="do not prune stale managed Vault roles/policies")
    parser.add_argument(
        "--token-file",
        default=os.environ.get("VAULT_TOKEN_FILE", "/var/lib/secrets/vault/access-token"),
        help="file containing a Vault token; ignored when VAULT_TOKEN is set",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env = os.environ.copy()
    env["KUBECONFIG"] = default_kubeconfig(args.kubeconfig)

    rendered, tmp = render(args, env)
    try:
        roles = discover(rendered, env)
        print_plan(roles)
        if args.dry_run:
            print("Dry run only. Vault was not changed.")
            return 0
        apply(roles, args, env)
        print("Vault Kubernetes auth synchronization complete.")
        return 0
    finally:
        if tmp:
            tmp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
