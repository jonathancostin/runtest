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


class RunTestCommandTests(unittest.TestCase):
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
