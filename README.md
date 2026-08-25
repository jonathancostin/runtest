# RunTest

RunTest is a command seam for routing coding-agent test commands. It gives every
RunTest process for the signed-in macOS account the same Local or Auto mode.

## Choose a mode

Check the current mode without changing it:

```sh
runtest status
runtest status --json
```

The JSON form reports the mode, whether it came from saved state or the safe
default, and whether Auto's background policy is available.

Change the mode for commands started later:

```sh
runtest mode local
runtest mode auto
```

RunTest saves the choice at
`~/Library/Application Support/RunTest/mode`. A mode update writes a complete
new file and then atomically replaces the old file, so processes reading or
writing at the same time cannot see a partial value.

If the state file is missing, RunTest uses Local. RunTest asks macOS for the
account's home folder instead of trusting a process's `HOME` value, so callers
cannot split the shared mode by changing their environment. Reading status does
not create or change the state file.

Local executes the requested command directly. Auto executes it through the
macOS background policy:

```sh
taskpolicy -b <command> [arguments ...]
```

If `taskpolicy` is unavailable, status names the configured fallback as
`direct local execution`. Auto prints the same fallback to standard error and
runs the command directly. It never claims that the background policy was
applied.

Each invocation reads the mode once before it starts the requested command.
Changing the mode affects later invocations and does not interrupt or migrate a
command that is already running.

## Run a command

Build the executable with the system C compiler:

```sh
make build
```

Then invoke it from this checkout:

```sh
./bin/runtest npm test
./bin/runtest python3 -m unittest
```

When `bin` is on your `PATH`, the canonical interface is:

```sh
runtest <command> [arguments ...]
```

RunTest passes each argument directly to the command. It also preserves the
caller's working directory and environment, keeps standard output and standard
error connected, and returns the command's exit code or termination signal.
Commands do not need to use npm.

RunTest does not interpret shell syntax. Invoke a shell explicitly when shell
behavior is wanted:

```sh
runtest sh -c 'printf "%s\n" "$HOME"'
```

Invoking `runtest` without a command prints usage and exits with status 64.

## Test the command seam

The test suite exercises the executable as an external process:

```sh
make test
```
