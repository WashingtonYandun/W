# C01 — Compilation sessions and reusable checked modules

## Completed checklist

- [x] One SourceManager and TypeInterner per whole-program session.
- [x] Canonical project-relative ModuleId and per-module DeclId registry, including generic templates and specializations.
- [x] CheckedModule retains checked AST, exports, dependency edges and content/options/dependency fingerprints.
- [x] Dependency parsing/checking reused across diamond imports and symlink aliases.
- [x] HIR, AST emission and interpreter consume the checked graph without reopening or rechecking dependencies.
- [x] Homonymous nominal types and functions remain distinct across modules.
- [x] Imported generic functions support inference, explicit type arguments and nominal arguments from another module.
- [x] Preserve lexical parameter/type-parameter bindings and readable nominal value display.
- [x] Initialize a dependency once; preserve the root entry point in the presence of imported globals.
- [x] Invalidate on changed content, options or entry; reject stale checked units and foreign HIR arenas.
- [x] Detect import cycles before cache lookup and retain dependency source paths/spans in diagnostics.
- [x] Reject runtime namespace values with a structured diagnostic before lowering.
- [x] Add the checked-module fixture to the differential and sanitizer corpora with explicit W1 unsupported status.

## Reproduction

```bash
python3 -m tests.unit.test_compilation_session
W_SANITIZE=1 CC=clang python3 -m tests.unit.test_compilation_session
./w test
./w test --differential 20
./w test --fuzz 100
python3 tools/ci_conformance.py --sanitize
```

The full suite includes one C01 contract-suite result, bringing the baseline to 391 checks. That result covers multiple independent contracts; it does not count each assertion as a separate language fixture.

The CI corpus now contains 101 cases: the previous 100 plus `tests/modules/checked_session/main.w`. Interpreter, AST C and HIR C execute all 101. W1 executes the existing 86 and reports 15 unsupported rows (14 generic rows plus the new checked-module case). The differential has 75 cases, 294 executed engine rows and 6 unsupported W1 rows. These counts supersede B04's initial coverage snapshot.

The fixture combines a diamond import, global initialization, three homonymous Item types, imported generics, type-parameter shadowing, enum values and namespace calls. Contract tests also cover symlinks, no source/checker calls during consumption, content changes with unchanged mtime, option invalidation, checker reuse, cycles, readable dependency diagnostics, HIR source provenance and arena mismatches.

## Boundaries and next step

[ADR-008](adr/ADR-008-compilation-sessions.md) records the lifecycle, identity and import semantics. This is an in-memory whole-program cache with conservative invalidation. It does not implement persistent incremental compilation, a stable ABI, new public export rules, qualified type annotations or W1 module parity.

C02 is next: resolve HIR names, fields, variants and calls into semantic IDs and remove the transitional dependence on AST patterns/name lookup. C03 retains typed specialization/worklist and structural mangling work. D02 ports the full pipeline to W1.
