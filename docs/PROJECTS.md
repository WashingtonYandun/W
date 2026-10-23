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

[targets.wasm]
entry = "src/main.wysna"
profile = "wasi-command"
fuel = 100000000
memory_limit_mb = 128
preopens = [{ path = "data", access = "read-only" }]

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

The `wasi-command` profile builds a `wasm32-wasip1` command from Seed-generated C99.
The CI compatibility baseline uses [wasi-sdk 34](https://github.com/WebAssembly/wasi-sdk/releases/tag/wasi-sdk-34)
and verifies its release archive checksum; set `WASI_SDK_PATH` to a compatible SDK installation.
Running the artifact requires [Wasmtime 50.0.0](https://github.com/bytecodealliance/wasmtime/releases/tag/v50.0.0).
Install the optional runner dependency with
`python -m pip install -e ".[wasi]"` in a checkout, or install the published package
with its `wasi` extra. WASI commands receive only their declared arguments, no inherited
environment, standard streams, clock/random access, and explicitly declared directory
preopens. A preopen maps to the same guest path; for example, `data` is available as
`data/input.txt`. `read-only` grants no filesystem writes. Each target defaults to 100
million fuel and 128 MiB of linear memory; `fuel` and `memory_limit_mb` can lower or
raise these values within manifest validation limits. Child processes, networking,
native C FFI, browser execution, and WASIp2 are outside this profile.

Target checks reject unsupported imports and capabilities before invoking the SDK.
WASI build provenance includes the target triple, artifact kind, compiler identity,
module imports/exports, configured capabilities, fuel limit, memory limit, and preopens.

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

`project check` type-checks the selected target and validates its required
capabilities without executing it. `project build` generates the artifact declared
by the target profile and reports source, lock, target, and toolchain provenance in
machine output. Native `project run` uses the reference interpreter and sets
`args()[0]` to "wysna"; arguments after `--` are passed unchanged. A `wasi-command`
target is compiled and executed in a fresh Wasmtime instance with the manifest's
capability and resource limits.

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
