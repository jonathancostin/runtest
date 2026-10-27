# RunTest

RunTest is a small C17 command seam, `runtest <command> [arguments ...]`, that routes coding-agent test commands by one shared mode per macOS account: Local runs the command directly, Auto runs it under the macOS background policy (`taskpolicy -b`). It passes arguments without shell parsing, keeps the caller's working directory, environment and stdio, and returns the command's exit code or signal.

## Status

- Early stage. Only the Local and Auto modes exist today; the remote execution mentioned in the GitHub description is not built yet.
- The open GitHub issues describe the roadmap (as of 2026-10-20): shared test-command router (#1), Crabbox remote routing (#5), local timing evidence (#6), recommending remote suites (#7), guided Local/Auto and Remote setup (#8, #9), a native menu-bar app and project routing (#10, #11), SketchyBar controls (#12), diagnosing stuck installs (#13), Homebrew tap install and releases (#14, #15).
- macOS only (`taskpolicy`, Application Support path).
- No CI.

## Stack

- C (`src/runtest.c`), built with `cc -std=c17 -Wall -Wextra -Wpedantic -Werror`.
- Python `unittest` test suite that runs the binary as an external process.
- Make.

## Build and run

```sh
make build
./bin/runtest npm test
./bin/runtest python3 -m unittest
```

With `bin` on `PATH`: `runtest <command> [arguments ...]`. Commands do not need to use npm. RunTest does not interpret shell syntax; call a shell explicitly when needed:

```sh
runtest sh -c 'printf "%s\n" "$HOME"'
```

`runtest` with no command prints usage and exits 64.

## Modes

```sh
runtest status
runtest status --json
runtest mode local
runtest mode auto
```

- `status --json` reports the mode, whether it came from saved state or the safe default, and whether Auto's background policy is available. Reading status does not create or change the state file.
- The mode is stored at `~/Library/Application Support/RunTest/mode`. An update writes a complete new file and atomically replaces the old one, so concurrent readers never see a partial value. A missing file means Local.
- RunTest asks macOS for the account's home folder instead of trusting `HOME`, so callers cannot split the shared mode by changing their environment.
- Auto runs `taskpolicy -b <command> [arguments ...]`. If `taskpolicy` is missing, status names the fallback as `direct local execution`, and Auto prints the same notice to stderr and runs the command directly. It never claims the background policy was applied.
- Each invocation reads the mode once before it starts the command; changing it affects later invocations only and never interrupts a running command.

## Tests

```sh
make test    # builds bin/runtest-test with -DRUNTEST_TESTING, runs the unittest suite in tests/
make check   # syntax-only compile of both builds + python3 -m compileall tests
```

## Configuration

No configuration environment variables; commands are looked up on the caller's `PATH`. The test build alone reads `RUNTEST_TEST_ACCOUNT_HOME`, and `make test` passes the test binary to the suite as `RUNTEST_UNDER_TEST`.

## Layout

```text
src/runtest.c     the command seam
tests/            Python unittest suite (test_cli.py)
Makefile          build, test, check
AGENTS.md         agent guide
docs/agents/      domain.md, issue-tracker.md, triage-labels.md
```

## License

MIT. See [LICENSE](LICENSE).

## Links

- Issues: https://github.com/jonathancostin/runtest/issues
- Related: [execution-target-switch](https://github.com/jonathancostin/execution-target-switch), a related project built around the same Local / low-impact / remote idea.
