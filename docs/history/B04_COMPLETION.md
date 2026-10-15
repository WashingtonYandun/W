# B04 — Compiler integration gates

## Implemented checklist

- [x] Keep `feat/**` pushes and PRs to `develop` covered by CI.
- [x] Add Linux GCC C99 alongside Linux/macOS Clang conformance gates.
- [x] Execute interpreter, AST C99, verified HIR C99 and standalone W1 in the differential oracle.
- [x] Replace generic filename exclusions with an explicit feature manifest.
- [x] Run standalone W1 on supported negative fixtures without the W0 checker.
- [x] Exercise all acyclic runtime/example fixtures with ASan/UBSan; enable LSan on Linux.
- [x] Keep intentionally leaking strong cycles isolated in the B03 negative harness.
- [x] Bound frontend/C compilation to 120 seconds, execution to 30 seconds, compiler preparation to 600 seconds and CI jobs to 30 minutes.
- [x] Reject nonzero exits, signals, timeouts, sanitizer reports, compiler crashes and output/diagnostic differences.
- [x] Preserve failing source, generated C, commands, output and return codes; record toolchain/platform versions and source SHA.
- [x] Report passed/failed/unsupported coverage by engine and feature; reject unsupported rows in the release profile.

## Coverage contract

`tests/engine_profiles.json` assigns individual fixtures to features. Unlisted fixtures use the core profile and must execute on every engine. A name containing `generic` does not exclude a fixture. Stale declarations fail the corpus gate. The imported `math_lib.w` support unit is declared separately and exercised through `import_module.w`.

The current corpus contains 100 executable cases: 47 runtime fixtures, 7 examples and 46 negative fixtures. Interpreter, AST and HIR execute all 100. W1 executes 86; its 9 generic runtime and 5 generic diagnostic fixtures are reported as **unsupported**, pending D02. Integration success refers to supported rows; it does not assert complete W1 parity.

The release profile executes the supported rows but returns failure while any unsupported row remains. At this baseline it exits with 14 unsupported cases. It is available through `workflow_dispatch` and locally; integration is the default PR profile. Repository branch protection settings remain an administrator responsibility.

Successful programs must match expected stdout, exit zero and agree on stderr. Negative programs must fail in the frontend with a structured diagnostic. Differential runtime panics must agree on diagnostic code and exit status. Paths and wording in error messages are not treated as diagnostic identity.

## Defects exposed and corrected

Adding HIR to the differential exposed a verifier bug: a function ending in an exhaustive `match` or complete `if` whose branches explicitly return was rejected because the control expression had unit type. The verifier now recognizes terminating paths and still validates each returned value. Match termination requires unconditional exhaustive pattern coverage. Regression tests remove a match arm or an else branch from HIR and require rejection.

The old native/HIR checks could accept expected stdout despite a nonzero execution status. All modified harnesses now reject that result. Existing bootstrap and conformance compilation also honor `CC` and have bounded subprocesses.

## Reproduction

```bash
python3 -m tests.unit.test_ci_harness
python3 -m tests.unit.test_hir_return_paths
python3 tools/ci_conformance.py
CC=clang python3 tools/ci_conformance.py --sanitize
python3 tools/ci_conformance.py --profile=release # expected failure until D02
./w test
./w test --differential 20
./w test --fuzz 100
```

Local macOS evidence: 390/390 conformance including SHA256 bootstrap; 74/74 differential; 100/100 fuzz; 100/100 supported-profile corpus cases under ASan/UBSan, with 14 W1 rows explicitly unsupported. Harness regressions cover mismatched output, nonzero exit with expected output, sanitizer UAF reports, timeout, signal, standalone W1 invocation, invalid acceptance and incomplete HIR return paths. Linux GCC and LSan results are supplied by the PR workflow.

Coverage JSON is uploaded on every CI run. On failure, the full reproduction directory and logs are uploaded as separate artifacts. Integration and memory jobs have distinct artifact names. `bash` uses `pipefail`, so storing logs with `tee` cannot hide a failed command.

## Next step

C01: introduce a compilation session with reusable checked modules and stable module/declaration identities. HIR should consume checked modules instead of reopening and rechecking imported source. W1 generic parity remains D02.
