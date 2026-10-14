# Phase A implementation report — PR #36

Date: 2026-10-14. Base: develop at 4cb919a. Branch: feat/hir-type-validation.
Status: implementation complete for the contracts below; integration pending.

## Acceptance gates

- [x] A01 — Reproducible regressions: compiler boundaries, canonical identity, constructor payloads, grouped types, propagation and string ownership have executable cases. The full suite, differential oracle, frontend fuzzing and W1 bundle check provide distinct evidence; W1 exclusions remain explicit.
- [x] A02 — Managed strings: immutable RC buffers record byte length and storage origin. Dynamic string producers, argv, collections and ADT payloads obey ownership transfer/clone contracts. Linux sanitizer CI includes leak detection.
- [x] A03 — Canonical type identity: Option/Result aliases share IDs and specialization keys with sugar. Nested nullable depth is retained; a generic identity call through both spellings emits one specialization.
- [x] A04 — Canonical runtime semantics: Result constructors use dedicated success/error values; optional operations preserve present-null, nested values and user-defined Err variants. See ADR-006 for the deliberate unboxed optional ABI adapter retained for W1.
- [x] A05 — Current HIR verification: types, structure, bindings, constructors, member/direct calls, return/assignment contracts, typed patterns and propagation are checked before emission. Malformed HIR regression mutations are rejected with W9999.
- [x] A06 — Error composition: grouped type parsing and formatting preserve nesting; optional binds tighter than right-associative result. Each postfix propagation unwraps one outer layer and requires a compatible enclosing return channel.

## Observable changes

Explicit Some displays its payload, so Some(42) prints 42. Some(None) remains distinct from missing None for equality and matching. Dictionary queries preserve that distinction. Bare success values are successful even when the result success/error types are equal; Err must be explicit. Guarded match arms now execute their guards and do not establish unconditional coverage. Implicit conversions cannot add nullable depth.

## Reproduction

Run from the repository root:

```sh
./w test
./w test --differential 20
./w test --fuzz 100
python3 tools/bundle_w1.py --check
python3 test_compiler_boundaries.py
python3 test_phase_a.py
```

The baseline at 0d76d99 passed 371/371 conformance checks, 74/74 differential cases, 100/100 fuzz cases and the bundle check. CI run 38589965423 passed on Linux and macOS, including ASan/UBSan and Linux LSan. The closing commit adds constructor/member verification and negative cases; its exact final SHA and CI evidence are recorded in the PR and Engineering Brain session.

## Scope limits and next work

ADR-006 revises the earlier demand for one physical optional layout: logical identity and operations are canonical, while unboxed non-none payloads remain a supported entry adapter. W1 still excludes generic-language fixtures; D02 owns parity. HIR remains name-based; SymbolIds and module sessions are later work. This corpus does not prove universal memory safety, embedded-NUL semantics or RC cycle collection. B01–B04 remain the next release gates. Roadmap integration checkboxes remain open until PR #36 is merged.
