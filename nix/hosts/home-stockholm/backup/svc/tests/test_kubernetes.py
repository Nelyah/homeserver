"""Tests for Kubernetes backup coordination."""

# ruff: noqa: PT009, PT027, SLF001

import unittest
from unittest.mock import AsyncMock

from svc.controllers.kubernetes import (
    KubernetesCommandResult,
    KubernetesController,
    _non_terminal_pod_summaries,
)
from svc.exceptions import KubernetesError


def _pod(name: str, phase: str) -> dict[str, object]:
    return {
        "metadata": {"name": name},
        "status": {"phase": phase},
    }


class NonTerminalPodSummaryTests(unittest.TestCase):
    def test_ignores_succeeded_and_failed_pods(self) -> None:
        pods = {
            "items": [
                _pod("completed", "Succeeded"),
                _pod("stale-failure", "Failed"),
            ]
        }

        self.assertEqual(_non_terminal_pod_summaries(pods), [])

    def test_reports_running_pending_and_unknown_pods(self) -> None:
        pods = {
            "items": [
                _pod("running", "Running"),
                _pod("starting", "Pending"),
                _pod("uncertain", "Unknown"),
                _pod("stale-failure", "Failed"),
            ]
        }

        self.assertEqual(
            _non_terminal_pod_summaries(pods),
            ["running (Running)", "starting (Pending)", "uncertain (Unknown)"],
        )

    def test_missing_phase_is_treated_as_unknown(self) -> None:
        pods = {"items": [{"metadata": {"name": "missing-phase"}, "status": {}}]}

        self.assertEqual(
            _non_terminal_pod_summaries(pods),
            ["missing-phase (Unknown)"],
        )


class DeploymentScaleDownTests(unittest.IsolatedAsyncioTestCase):
    async def test_terminal_pods_do_not_block_scale_down(self) -> None:
        controller = KubernetesController(kubectl_bin="/bin/true")
        controller._deployment_selector = AsyncMock(return_value="app=homeassistant")
        run_mock = AsyncMock(return_value=KubernetesCommandResult(returncode=1))
        controller._run = run_mock
        controller._get_json = AsyncMock(
            return_value={"items": [_pod("old-homeassistant", "Failed")]}
        )

        await controller._wait_for_no_deployment_pods("homeassistant", "homeassistant", 180)

        run_mock.assert_awaited_once()
        awaited = run_mock.await_args
        if awaited is None:
            self.fail("kubectl wait was not called")
        wait_args = awaited.args[0]
        self.assertIn("status.phase!=Succeeded,status.phase!=Failed", wait_args)

    async def test_unknown_pod_blocks_scale_down(self) -> None:
        controller = KubernetesController(kubectl_bin="/bin/true")
        controller._deployment_selector = AsyncMock(return_value="app=homeassistant")
        controller._run = AsyncMock(return_value=KubernetesCommandResult(returncode=1))
        controller._get_json = AsyncMock(
            return_value={"items": [_pod("uncertain-homeassistant", "Unknown")]}
        )

        with self.assertRaisesRegex(
            KubernetesError,
            r"uncertain-homeassistant \(Unknown\)",
        ):
            await controller._wait_for_no_deployment_pods(
                "homeassistant",
                "homeassistant",
                180,
            )


if __name__ == "__main__":
    unittest.main()
