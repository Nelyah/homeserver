"""Tests for backup failure and Kubernetes replica restoration."""

# ruff: noqa: PT009, PT027, SLF001

import asyncio
import unittest
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, call

from svc.controllers import DeploymentScale
from svc.core.backup_orchestrator import BackupOrchestrator
from svc.exceptions import EXIT_CONFIG_ERROR, EXIT_RESTIC_ERROR, KubernetesError


class BackupOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    def _orchestrator(
        self,
        *,
        scales: list[DeploymentScale],
        backup_result: int | BaseException = 0,
    ) -> tuple[BackupOrchestrator, Any, Any, Any]:
        kubernetes = SimpleNamespace(
            deployment_scale=AsyncMock(side_effect=scales),
            scale_deployment=AsyncMock(),
            wait_for_deployment_replicas=AsyncMock(),
        )
        restic = SimpleNamespace(
            dry_run=False,
            backup=AsyncMock(
                side_effect=backup_result if isinstance(backup_result, BaseException) else None,
                return_value=backup_result if isinstance(backup_result, int) else None,
            ),
            forget=AsyncMock(return_value=0),
        )
        service = SimpleNamespace(
            name="example",
            backup=SimpleNamespace(
                kubernetes=SimpleNamespace(
                    namespace="example",
                    deployments=[scale.name for scale in scales],
                ),
                tags=["example"],
                exclude=[],
                policy=None,
            ),
        )
        orchestrator = BackupOrchestrator(
            config=cast("Any", SimpleNamespace()),
            restic=cast("Any", restic),
            kubernetes=cast("Any", kubernetes),
            path_resolver=cast("Any", SimpleNamespace()),
        )
        orchestrator._prepare_backup_paths = AsyncMock(return_value=(["/data"], None))
        return orchestrator, service, restic, kubernetes

    async def test_restic_failure_restores_captured_replica_counts(self) -> None:
        app = DeploymentScale(namespace="example", name="app", replicas=2)
        database = DeploymentScale(namespace="example", name="database", replicas=1)
        orchestrator, service, _restic, kubernetes = self._orchestrator(
            scales=[app, database], backup_result=1
        )

        result = await orchestrator.backup_service(service)

        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, EXIT_RESTIC_ERROR)
        self.assertEqual(
            kubernetes.scale_deployment.await_args_list,
            [call(app, 0), call(database, 0), call(database, 1), call(app, 2)],
        )

    async def test_restic_exception_restores_before_propagating(self) -> None:
        app = DeploymentScale(namespace="example", name="app", replicas=1)
        orchestrator, service, _restic, kubernetes = self._orchestrator(
            scales=[app], backup_result=OSError("restic could not start")
        )

        with self.assertRaisesRegex(OSError, "restic could not start"):
            await orchestrator.backup_service(service)

        self.assertEqual(
            kubernetes.scale_deployment.await_args_list,
            [call(app, 0), call(app, 1)],
        )

    async def test_cancellation_restores_before_propagating(self) -> None:
        app = DeploymentScale(namespace="example", name="app", replicas=1)
        orchestrator, service, _restic, kubernetes = self._orchestrator(
            scales=[app], backup_result=asyncio.CancelledError()
        )

        with self.assertRaises(asyncio.CancelledError):
            await orchestrator.backup_service(service)

        self.assertEqual(
            kubernetes.scale_deployment.await_args_list,
            [call(app, 0), call(app, 1)],
        )

    async def test_restore_failure_marks_successful_backup_as_failed_and_continues(self) -> None:
        app = DeploymentScale(namespace="example", name="app", replicas=2)
        database = DeploymentScale(namespace="example", name="database", replicas=1)
        orchestrator, service, _restic, kubernetes = self._orchestrator(scales=[app, database])
        kubernetes.scale_deployment.side_effect = [
            None,
            None,
            KubernetesError("database did not start"),
            None,
        ]

        result = await orchestrator.backup_service(service)

        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, EXIT_CONFIG_ERROR)
        self.assertIn("example/database", result.message)
        self.assertEqual(
            kubernetes.scale_deployment.await_args_list,
            [call(app, 0), call(database, 0), call(database, 1), call(app, 2)],
        )

    async def test_deployment_originally_at_zero_remains_at_zero(self) -> None:
        app = DeploymentScale(namespace="example", name="app", replicas=0)
        orchestrator, service, _restic, kubernetes = self._orchestrator(scales=[app])

        result = await orchestrator.backup_service(service)

        self.assertTrue(result.success)
        kubernetes.scale_deployment.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
