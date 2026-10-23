# Wysna Projects

Project mode adds a manifest, deterministic local dependency resolution, explicit
lockfile updates, project commands, and isolated user test entries. Single-file
commands remain available and `wysna test` continues to run compiler maintenance
tests.

## Manifest version 1

Create `wysna.toml` at the package root:

```toml
manifest_version = 1

[package]
name = "example-tool"
version = "0.1.0"
language = "0.5"

[toolchain]
compiler = "0.5.0"
stdlib = "bundled"

[sources]
root = "src"

[targets.app]
entry = "src/main.wysna"
profile = "native-cli"

[dependencies.stats]
path = "vendor/stats"

[[tests]]
name = "valid-input"
entry = "tests/valid_input.wysna"
timeout_ms = 10000
```

The compiler and standard library versions must match the installed toolchain.
Manifest keys are strict; unsupported fields and profiles fail instead of being
silently ignored. Dependency paths must remain inside the declaring package. Each
dependency has its own `wysna.toml` and source root. Project manifests do not run
install hooks, plugins, or registry lookups.

Imports use existing Wysna syntax. Relative imports resolve inside the declared
`sources.root`; tests outside that directory can import package modules through
the same root. Declared dependencies use `pkg/<alias>/<module-path>`, for example:

```wysna
import "pkg/stats/summary.wysna"
```

Project resolution never falls back to the current working directory. Physical
path containment, symlink boundaries, and portable case/Unicode collisions are
checked before compiling.

## Commands

```sh
wysna project lock [--manifest path/to/wysna.toml] [--offline]
wysna project check [--manifest path/to/wysna.toml] [--frozen] [--offline]
wysna project build [--target app] [-o build/app] [--frozen] [--output-format=json-v1]
wysna project run [--target app] [-- args...]
wysna project test [--filter name] [--report-json report.json]
```

Without `--manifest`, Wysna searches from the current directory toward its parents.
`project lock` is the explicit lockfile writer. Its versioned JSON lock records
package identities, dependency aliases, exact compiler and standard-library
versions, and ordered hashes for dependency inputs. `--frozen` requires the lock
to exist and rejects manifest or dependency drift. Root-package source edits do
not require a lock refresh. Resolution is local and offline by design.

`project check` type-checks the selected target without executing it. `project
build` generates a native executable and reports source, lock, toolchain, target,
and C compiler provenance in machine output. `project run` uses the reference
interpreter and sets `args()[0]` to `"wysna"`; arguments after `--` are passed
unchanged. The built executable receives the operating system's native argument
vector.

Each `[[tests]]` entry runs in its own process. Tests execute sequentially, use
their declared timeout, and preserve stdout/stderr with a 1 MiB cap per stream.
`--filter` selects names by substring and fails if it matches nothing. An empty
suite exits nonzero and is reported as empty; it is not treated as functional
coverage. The aggregate report records each case's status, duration, exit code,
source hash, timeout, and bounded-output hashes.

## Scripting APIs

`std/environment` exposes the runner's argument vector and optional environment
lookup. `std/time` exposes Unix epoch seconds. `std/process.run` invokes an
executable with a separate argument list, without invoking a shell implicitly,
and enforces a timeout. Child stdout and stderr inherit the Wysna program's
streams. See [`examples/automation`](../examples/automation) for a project that
orchestrates a child command and has a user test entry.

`wysna api std/json --output-format=json-v1` returns public symbol signatures,
error channels, documentation when present, and explicit `unknown` values for
ownership and effect facts that are not currently encoded in the language metadata.
`wysna api --manifest path/to/wysna.toml` indexes a checked project module graph.
`wysna capabilities --output-format=json-v1` reports commands and targets
supported by the installed compiler.
