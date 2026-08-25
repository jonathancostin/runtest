from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNTEST = Path(os.environ.get("RUNTEST_UNDER_TEST", ROOT / "bin" / "runtest"))


def isolated_environment(account_home: str | Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["HOME"] = str(account_home)
    environment["RUNTEST_TEST_ACCOUNT_HOME"] = str(account_home)
    return environment


def install_taskpolicy_test_double(
    account_home: str | Path,
    environment: dict[str, str],
    *,
    append_log: bool = False,
) -> Path:
    account_home = Path(account_home)
    taskpolicy_directory = account_home / "bin"
    taskpolicy_directory.mkdir()
    taskpolicy_log = account_home / "taskpolicy.log"
    redirection = ">>" if append_log else ">"
    taskpolicy = taskpolicy_directory / "taskpolicy"
    taskpolicy.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$1" {redirection} "$RUNTEST_TASKPOLICY_LOG"\n'
        "shift\n"
        'exec "$@"\n'
    )
    taskpolicy.chmod(0o755)
    environment["PATH"] = f"{taskpolicy_directory}{os.pathsep}{environment['PATH']}"
    environment["RUNTEST_TASKPOLICY_LOG"] = str(taskpolicy_log)
    return taskpolicy_log


class RunTestCommandTests(unittest.TestCase):
    def test_status_reports_local_when_no_mode_has_been_saved(self) -> None:
        with tempfile.TemporaryDirectory() as home_directory:
            environment = isolated_environment(home_directory)

            result = subprocess.run(
                [RUNTEST, "status", "--json"],
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            state_path = (
                Path(home_directory)
                / "Library"
                / "Application Support"
                / "RunTest"
                / "mode"
            )
            self.assertFalse(state_path.exists())

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {
                "auto": {
                    "available": True,
                    "fallback": "direct local execution",
                    "policy": "taskpolicy -b",
                },
                "mode": "local",
                "source": "default",
            },
        )

    def test_missing_home_uses_safe_local_default(self) -> None:
        with tempfile.TemporaryDirectory() as account_home:
            environment = isolated_environment(account_home)
            environment.pop("HOME")

            result = subprocess.run(
                [RUNTEST, sys.executable, "-c", "print('ran locally')"],
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "ran locally\n")

    def test_mode_change_is_shared_with_later_processes(self) -> None:
        with tempfile.TemporaryDirectory() as home_directory:
            environment = isolated_environment(home_directory)

            change = subprocess.run(
                [RUNTEST, "mode", "auto"],
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            status = subprocess.run(
                [RUNTEST, "status", "--json"],
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(change.returncode, 0, change.stderr)
        self.assertEqual(change.stdout, "Mode set to Auto.\n")
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)["mode"], "auto")
        self.assertEqual(json.loads(status.stdout)["source"], "saved")

    def test_callers_with_different_home_values_share_the_account_mode(self) -> None:
        with tempfile.TemporaryDirectory() as test_directory:
            shared_account_home = Path(test_directory) / "account-home"
            first_caller_home = Path(test_directory) / "first-caller-home"
            second_caller_home = Path(test_directory) / "second-caller-home"
            shared_account_home.mkdir()
            first_caller_home.mkdir()
            second_caller_home.mkdir()

            first_environment = os.environ.copy()
            first_environment["HOME"] = str(first_caller_home)
            first_environment["RUNTEST_TEST_ACCOUNT_HOME"] = str(
                shared_account_home
            )
            second_environment = first_environment.copy()
            second_environment["HOME"] = str(second_caller_home)

            change = subprocess.run(
                [RUNTEST, "mode", "auto"],
                env=first_environment,
                check=False,
                capture_output=True,
                text=True,
            )
            status = subprocess.run(
                [RUNTEST, "status", "--json"],
                env=second_environment,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(change.returncode, 0, change.stderr)
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)["mode"], "auto")

    def test_auto_mode_uses_taskpolicy_for_new_commands(self) -> None:
        with tempfile.TemporaryDirectory() as home_directory:
            environment = isolated_environment(home_directory)
            taskpolicy_log = install_taskpolicy_test_double(
                home_directory, environment
            )

            change = subprocess.run(
                [RUNTEST, "mode", "auto"],
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            command = subprocess.run(
                [RUNTEST, sys.executable, "-c", "print('ran in Auto')"],
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(change.returncode, 0, change.stderr)
            self.assertEqual(command.returncode, 0, command.stderr)
            self.assertEqual(command.stdout, "ran in Auto\n")
            self.assertEqual(taskpolicy_log.read_text(), "-b\n")

    def test_auto_mode_reports_and_uses_direct_fallback_without_taskpolicy(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as home_directory:
            empty_path = Path(home_directory) / "empty-path"
            empty_path.mkdir()
            environment = isolated_environment(home_directory)
            environment["PATH"] = str(empty_path)

            change = subprocess.run(
                [RUNTEST, "mode", "auto"],
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            status = subprocess.run(
                [RUNTEST, "status"],
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            command = subprocess.run(
                [RUNTEST, sys.executable, "-c", "print('used fallback')"],
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(change.returncode, 0, change.stderr)
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(
            status.stdout,
            "Mode: Auto\n"
            "Auto policy: taskpolicy -b (unavailable)\n"
            "Auto fallback: direct local execution\n",
        )
        self.assertEqual(command.returncode, 0)
        self.assertEqual(command.stdout, "used fallback\n")
        self.assertEqual(
            command.stderr,
            "runtest: Auto policy is unavailable; falling back to direct local "
            "execution\n",
        )

    def test_mode_change_does_not_migrate_an_active_command(self) -> None:
        with tempfile.TemporaryDirectory() as home_directory:
            environment = isolated_environment(home_directory)
            taskpolicy_log = install_taskpolicy_test_double(
                home_directory, environment, append_log=True
            )

            local = subprocess.run(
                [RUNTEST, "mode", "local"],
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            active = subprocess.Popen(
                [
                    RUNTEST,
                    sys.executable,
                    "-c",
                    "print('started', flush=True); input(); print('finished')",
                ],
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert active.stdout is not None
            self.assertEqual(active.stdout.readline(), "started\n")

            auto = subprocess.run(
                [RUNTEST, "mode", "auto"],
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            remaining_output, active_error = active.communicate("\n", timeout=5)

            self.assertEqual(local.returncode, 0, local.stderr)
            self.assertEqual(auto.returncode, 0, auto.stderr)
            self.assertEqual(active.returncode, 0, active_error)
            self.assertEqual(remaining_output, "finished\n")
            self.assertFalse(taskpolicy_log.exists())

            later = subprocess.run(
                [RUNTEST, sys.executable, "-c", "print('later command')"],
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(later.returncode, 0, later.stderr)
            self.assertEqual(later.stdout, "later command\n")
            self.assertEqual(taskpolicy_log.read_text(), "-b\n")

    def test_concurrent_mode_readers_and_writers_only_observe_complete_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as home_directory:
            environment = isolated_environment(home_directory)
            initial = subprocess.run(
                [RUNTEST, "mode", "local"],
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)

            def write_mode(mode: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [RUNTEST, "mode", mode],
                    env=environment,
                    check=False,
                    capture_output=True,
                    text=True,
                )

            def read_status() -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [RUNTEST, "status", "--json"],
                    env=environment,
                    check=False,
                    capture_output=True,
                    text=True,
                )

            with ThreadPoolExecutor(max_workers=32) as executor:
                writers = [
                    executor.submit(write_mode, "auto" if index % 2 else "local")
                    for index in range(24)
                ]
                readers = [executor.submit(read_status) for _ in range(24)]

            for writer in writers:
                result = writer.result()
                self.assertEqual(result.returncode, 0, result.stderr)

            for reader in readers:
                result = reader.result()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(json.loads(result.stdout)["mode"], {"local", "auto"})

            state_directory = (
                Path(home_directory) / "Library" / "Application Support" / "RunTest"
            )
            self.assertIn(
                (state_directory / "mode").read_text(),
                {"local\n", "auto\n"},
            )
            self.assertEqual(list(state_directory.glob("mode.*")), [])

    def test_requires_a_command(self) -> None:
        result = subprocess.run(
            [RUNTEST],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 64)
        self.assertEqual(
            result.stderr,
            "Usage: runtest <command> [arguments ...]\n",
        )

    def test_preserves_argument_vector(self) -> None:
        arguments = [
            "contains spaces",
            "semi;colon",
            "$(not-a-command)",
            "single'quote",
            'double"quote',
            "*.txt",
        ]

        result = subprocess.run(
            [
                RUNTEST,
                sys.executable,
                "-c",
                "import json, sys; print(json.dumps(sys.argv[1:]))",
                *arguments,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), arguments)

    def test_preserves_working_directory_environment_and_output_streams(self) -> None:
        environment = os.environ.copy()
        environment["RUNTEST_TEST_VALUE"] = "visible to child"

        with tempfile.TemporaryDirectory() as working_directory:
            result = subprocess.run(
                [
                    RUNTEST,
                    sys.executable,
                    "-c",
                    (
                        "import json, os, sys; "
                        "print(json.dumps([os.getcwd(), os.environ['RUNTEST_TEST_VALUE']])); "
                        "print('standard error stays visible', file=sys.stderr)"
                    ),
                ],
                cwd=working_directory,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            json.loads(result.stdout),
            [str(Path(working_directory).resolve()), "visible to child"],
        )
        self.assertEqual(result.stderr, "standard error stays visible\n")

    def test_passes_the_same_environment_as_direct_execution(self) -> None:
        environment = os.environ.copy()
        environment["RUNTEST_TEST_VALUE"] = "visible to child"
        environment["OLDPWD"] = "/a/caller-controlled/path"
        environment["_"] = "caller-controlled-value"
        print_environment = (
            "import json, os; print(json.dumps(dict(os.environ), sort_keys=True))"
        )

        direct = subprocess.run(
            [sys.executable, "-c", print_environment],
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        routed = subprocess.run(
            [RUNTEST, sys.executable, "-c", print_environment],
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(routed.returncode, direct.returncode, routed.stderr)
        self.assertEqual(json.loads(routed.stdout), json.loads(direct.stdout))

    def test_preserves_exit_code(self) -> None:
        result = subprocess.run(
            [RUNTEST, sys.executable, "-c", "raise SystemExit(37)"],
            check=False,
        )

        self.assertEqual(result.returncode, 37)

    def test_preserves_termination_signal(self) -> None:
        result = subprocess.run(
            [
                RUNTEST,
                sys.executable,
                "-c",
                "import os, signal; os.kill(os.getpid(), signal.SIGTERM)",
            ],
            check=False,
        )

        self.assertEqual(result.returncode, -signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
