# RunTest

RunTest is a command seam for routing coding-agent test commands. The current
tracer bullet runs commands locally without changing their observable behavior.

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
