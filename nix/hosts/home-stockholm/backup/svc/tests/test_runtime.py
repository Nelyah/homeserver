"""Tests for graceful command cancellation."""

# ruff: noqa: PT009, PT027

import asyncio
import signal
import unittest
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from svc.cli.runtime import _execute_command


class RuntimeCancellationTests(unittest.IsolatedAsyncioTestCase):
    async def test_sigterm_handler_cancels_active_command_once(self) -> None:
        loop = asyncio.get_running_loop()
        handlers: dict[int, Any] = {}
        cleaned_up = False

        class WaitingCommand:
            async def execute(self, _args: object, _ctx: object) -> int:
                nonlocal cleaned_up
                handlers[signal.SIGTERM]()
                handlers[signal.SIGTERM]()
                try:
                    await asyncio.Event().wait()
                finally:
                    cleaned_up = True

        def add_signal_handler(sig: int, callback: Any, *args: object) -> None:
            handlers[sig] = lambda: callback(*args)

        with (
            patch.object(loop, "add_signal_handler", side_effect=add_signal_handler),
            patch.object(loop, "remove_signal_handler", return_value=True) as remove_signal_handler,
            self.assertRaises(asyncio.CancelledError),
        ):
            await _execute_command(
                cast("Any", WaitingCommand()),
                object(),
                cast("Any", SimpleNamespace()),
            )

        self.assertTrue(cleaned_up)
        remove_signal_handler.assert_called_once_with(signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
