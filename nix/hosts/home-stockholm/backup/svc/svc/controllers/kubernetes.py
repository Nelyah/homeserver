"""Kubernetes controller with async kubectl support."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from ..exceptions import KubernetesError

logger = logging.getLogger("svc.controllers.kubernetes")


@dataclass
class DeploymentScale:
    """Original replica count for a Kubernetes deployment."""

    namespace: str
    name: str
    replicas: int


@dataclass
class KubernetesCommandResult:
    """Result of a kubectl command."""

    returncode: int
    stdout: str = ""
    stderr: str = ""


class KubernetesController:
    """Controls Kubernetes operations needed for backup orchestration."""

    def __init__(
        self,
        kubectl_bin: str = "/run/current-system/sw/bin/kubectl",
        kubeconfig: str = "/etc/rancher/k3s/k3s.yaml",
        dry_run: bool = False,
    ):
        self.kubectl = kubectl_bin
        if not Path(self.kubectl).exists():
            found = shutil.which("kubectl")
            if found:
                self.kubectl = found
        self.kubeconfig = kubeconfig
        self.dry_run = dry_run

    async def _run(
        self,
        args: list[str],
        *,
        capture_output: bool = True,
        allow_dry_run: bool = False,
    ) -> KubernetesCommandResult:
        """Run kubectl asynchronously."""
        kubectl_exists = await asyncio.to_thread(Path(self.kubectl).exists)
        if not kubectl_exists:
            message = "kubectl not found"
            raise KubernetesError(message)

        cmd = [self.kubectl, "--kubeconfig", self.kubeconfig, *args]
        logger.debug("Running: %s", " ".join(cmd))

        if self.dry_run and not allow_dry_run:
            logger.info("[DRY RUN] Would run: kubectl %s", " ".join(args))
            return KubernetesCommandResult(returncode=0)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE if capture_output else None,
            stderr=asyncio.subprocess.PIPE if capture_output else None,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()
        return KubernetesCommandResult(
            returncode=proc.returncode or 0,
            stdout=stdout_bytes.decode() if stdout_bytes else "",
            stderr=stderr_bytes.decode() if stderr_bytes else "",
        )

    async def _get_json(self, args: list[str]) -> dict[str, Any]:
        """Run kubectl and parse a JSON object response."""
        result = await self._run([*args, "-o", "json"], allow_dry_run=True)
        if result.returncode != 0:
            message = result.stderr.strip() or f"kubectl {' '.join(args)} failed"
            raise KubernetesError(message)

        try:
            raw = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            message = f"Invalid JSON from kubectl {' '.join(args)}"
            raise KubernetesError(message) from error

        if not isinstance(raw, dict):
            message = f"Expected JSON object from kubectl {' '.join(args)}"
            raise KubernetesError(message)
        return cast("dict[str, Any]", raw)

    async def deployment_replicas(self, namespace: str, deployment: str) -> int:
        """Get the desired replica count for a deployment."""
        obj = await self._get_json(["-n", namespace, "get", "deployment", deployment])
        spec = _dict_field(obj, "spec")
        replicas = spec.get("replicas", 1)
        return replicas if isinstance(replicas, int) else 1

    async def deployment_scale(self, namespace: str, deployment: str) -> DeploymentScale:
        """Capture the current scale for a deployment."""
        replicas = await self.deployment_replicas(namespace, deployment)
        return DeploymentScale(namespace=namespace, name=deployment, replicas=replicas)

    async def scale_deployment(self, scale: DeploymentScale, replicas: int) -> None:
        """Scale a deployment to the requested replica count."""
        logger.info("Scaling deployment/%s in %s to %s...", scale.name, scale.namespace, replicas)
        result = await self._run(
            [
                "-n",
                scale.namespace,
                "scale",
                f"deployment/{scale.name}",
                f"--replicas={replicas}",
            ],
            capture_output=True,
        )
        if result.returncode != 0:
            message = result.stderr.strip() or f"Failed to scale deployment/{scale.name}"
            raise KubernetesError(message)

    async def wait_for_deployment_replicas(
        self,
        namespace: str,
        deployment: str,
        replicas: int,
        timeout_seconds: int = 180,
    ) -> None:
        """Wait until a deployment reaches the requested replica count."""
        if self.dry_run:
            logger.info(
                "[DRY RUN] Would wait for deployment/%s in %s to reach %s replicas",
                deployment,
                namespace,
                replicas,
            )
            return

        result = await self._run(
            [
                "-n",
                namespace,
                "rollout",
                "status",
                f"deployment/{deployment}",
                f"--timeout={timeout_seconds}s",
            ],
            capture_output=True,
        )
        if result.returncode != 0:
            message = result.stderr.strip() or f"Timed out waiting for deployment/{deployment}"
            raise KubernetesError(message)

        if replicas == 0:
            await self._wait_for_no_deployment_pods(namespace, deployment, timeout_seconds)

    async def pvc_filesystem_path(self, namespace: str, pvc: str) -> str:
        """Resolve a PVC to its backing host filesystem path for local PV backends."""
        pvc_obj = await self._get_json(["-n", namespace, "get", "pvc", pvc])
        pvc_spec = _dict_field(pvc_obj, "spec")
        volume_name = pvc_spec.get("volumeName")
        if not isinstance(volume_name, str) or not volume_name:
            message = f"PVC {namespace}/{pvc} is not bound to a PV"
            raise KubernetesError(message)

        pv_obj = await self._get_json(["get", "pv", volume_name])
        pv_spec = _dict_field(pv_obj, "spec")
        path = _nested_string(pv_spec, "hostPath", "path") or _nested_string(
            pv_spec, "local", "path"
        )
        if path is None:
            message = (
                f"PV {volume_name} for PVC {namespace}/{pvc} is not backed by "
                "spec.hostPath.path or spec.local.path"
            )
            raise KubernetesError(message)

        return path

    async def _wait_for_no_deployment_pods(
        self,
        namespace: str,
        deployment: str,
        timeout_seconds: int,
    ) -> None:
        """Wait until no pods remain for a deployment selector."""
        selector = await self._deployment_selector(namespace, deployment)
        result = await self._run(
            [
                "-n",
                namespace,
                "wait",
                "--for=delete",
                "pod",
                "-l",
                selector,
                f"--timeout={timeout_seconds}s",
            ],
            capture_output=True,
        )
        if result.returncode not in {0, 1}:
            message = result.stderr.strip() or f"Timed out waiting for pods of {deployment}"
            raise KubernetesError(message)

        pods = await self._run(
            ["-n", namespace, "get", "pods", "-l", selector, "-o", "name"],
            allow_dry_run=True,
        )
        if pods.returncode != 0:
            message = pods.stderr.strip() or f"Failed to list pods for deployment/{deployment}"
            raise KubernetesError(message)
        if pods.stdout.strip():
            message = f"Pods for deployment/{deployment} still exist after scale-down"
            raise KubernetesError(message)

    async def _deployment_selector(self, namespace: str, deployment: str) -> str:
        """Return a comma-separated matchLabels selector for a deployment."""
        obj = await self._get_json(["-n", namespace, "get", "deployment", deployment])
        spec = _dict_field(obj, "spec")
        selector = _dict_field(spec, "selector")
        match_labels = _dict_field(selector, "matchLabels")
        if not match_labels:
            message = f"Deployment {namespace}/{deployment} has no matchLabels selector"
            raise KubernetesError(message)

        parts: list[str] = []
        for key, value in sorted(match_labels.items()):
            if not isinstance(value, str):
                message = f"Deployment {namespace}/{deployment} selector label {key} is not a string"
                raise KubernetesError(message)
            parts.append(f"{key}={value}")
        return ",".join(parts)


def _dict_field(obj: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a nested dictionary field or an empty dictionary."""
    value = obj.get(key)
    return cast("dict[str, Any]", value) if isinstance(value, dict) else {}


def _nested_string(obj: dict[str, Any], first: str, second: str) -> str | None:
    """Return obj[first][second] when it is a string."""
    raw_nested = obj.get(first)
    if not isinstance(raw_nested, dict):
        return None
    nested = cast("dict[str, Any]", raw_nested)
    value = nested.get(second)
    return value if isinstance(value, str) else None
