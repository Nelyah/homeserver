"""Tests for the direct Restic command passthrough."""

# ruff: noqa: PT009

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from click.testing import CliRunner

from svc.cli.commands.restic_cmd import ResticArgs, ResticCommand
from svc.cli.parser import cli
from svc.controllers.restic import ResticRunner


class ResticCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_loads_repository_env_and_returns_restic_exit_code(self) -> None:
        runner = SimpleNamespace(run=AsyncMock(return_value=23))
        ctx = SimpleNamespace(
            config=SimpleNamespace(paths=SimpleNamespace(secrets_root="/run/secrets")),
            create_restic_runner=Mock(return_value=runner),
        )
        env_vars = {
            "RESTIC_PASSWORD": "secret",
            "RESTIC_REPOSITORY": "example:/backups",
        }

        with patch(
            "svc.cli.commands.restic_cmd.load_restic_env",
            return_value=env_vars,
        ) as load_env:
            status = await ResticCommand().execute(
                ResticArgs(env="remote", command=("unlock", "--remove-all")),
                ctx,
            )

        self.assertEqual(status, 23)
        load_env.assert_called_once_with("/run/secrets", "remote")
        ctx.create_restic_runner.assert_called_once_with(env_vars)
        runner.run.assert_awaited_once_with(["unlock", "--remove-all"])


class ResticParserTests(unittest.TestCase):
    def test_forwards_all_arguments_after_repository(self) -> None:
        with patch("svc.cli.commands.restic_cmd.run_command") as run_command:
            result = CliRunner().invoke(
                cli,
                ["restic", "remote", "snapshots", "--json", "--help", "-v"],
            )

        self.assertEqual(result.exit_code, 0, result.output)
        args = run_command.call_args.args[2]
        self.assertEqual(
            args,
            ResticArgs(
                env="remote",
                command=("snapshots", "--json", "--help", "-v"),
            ),
        )

    def test_preserves_restic_separator(self) -> None:
        with patch("svc.cli.commands.restic_cmd.run_command") as run_command:
            result = CliRunner().invoke(
                cli,
                ["restic", "local", "backup", "--", "-leading-dash"],
            )

        self.assertEqual(result.exit_code, 0, result.output)
        args = run_command.call_args.args[2]
        self.assertEqual(
            args,
            ResticArgs(
                env="local",
                command=("backup", "--", "-leading-dash"),
            ),
        )

    def test_requires_a_restic_command(self) -> None:
        result = CliRunner().invoke(cli, ["restic", "local"])

        self.assertEqual(result.exit_code, 2)
        self.assertIn("Missing Restic command.", result.output)

    def test_wrapper_help_is_available_before_repository(self) -> None:
        with patch("svc.cli.commands.restic_cmd.run_command") as run_command:
            result = CliRunner().invoke(cli, ["restic", "--help"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Usage:", result.output)
        self.assertIn("{local|remote}", result.output)
        run_command.assert_not_called()


class GlobalOptionTests(unittest.TestCase):
    def test_accepts_global_option_before_subcommand(self) -> None:
        with patch("svc.cli.parser.run_command") as run_command:
            result = CliRunner().invoke(
                cli,
                ["--dry-run", "backup", "remote", "all"],
            )

        self.assertEqual(result.exit_code, 0, result.output)
        root_options = run_command.call_args.args[0].find_root().obj
        self.assertTrue(root_options.dry_run)

    def test_rejects_global_option_after_regular_subcommand(self) -> None:
        result = CliRunner().invoke(
            cli,
            ["backup", "remote", "all", "--dry-run"],
        )

        self.assertEqual(result.exit_code, 2)
        self.assertIn("No such option: --dry-run", result.output)


class ResticRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_inherits_terminal_and_returns_exact_exit_code(self) -> None:
        process = SimpleNamespace(wait=AsyncMock(), returncode=17)
        runner = ResticRunner(
            {"RESTIC_PASSWORD": "secret", "RESTIC_REPOSITORY": "/backups"},
            restic_bin="/test/restic",
        )

        with patch(
            "svc.controllers.restic.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=process),
        ) as create_process:
            status = await runner.run(["unlock"])

        self.assertEqual(status, 17)
        process.wait.assert_awaited_once_with()
        create_process.assert_awaited_once()
        call = create_process.call_args
        self.assertEqual(call.args, ("/test/restic", "unlock"))
        self.assertEqual(set(call.kwargs), {"env"})
        self.assertEqual(call.kwargs["env"]["RESTIC_REPOSITORY"], "/backups")


if __name__ == "__main__":
    unittest.main()
