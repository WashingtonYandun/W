# C02 — Fully Resolved HIR and Explicit Lowering

## Completed checklist

- [x] Introduce semantic identifiers: `SymbolId` for variables/temporaries, `FieldId` (offset & name) for struct/class fields, and `VariantId` (tag index & name) for enum variants.
- [x] Structured `CallTarget` hierarchy (`DirectCallTarget`, `BuiltinCallTarget`, `VirtualCallTarget` with vtable slot and target class).
- [x] Native `HirPattern` hierarchy (`HirWildcardPattern`, `HirBindingPattern`, `HirLiteralPattern`, `HirEnumPattern`, `HirTuplePattern`).
- [x] Completely eliminate all `node.NodeType` AST imports from `hir/HirNodes.py`, `hir/HirVerifier.py`, `hir/HirBindings.py`, and `hir/HirCCodeGen.py`.
- [x] Explicit `HirCoerce` node for semantic coercions (`wrap_ok`, `wrap_some`, `int_to_float`, `upcast`).
- [x] Explicit Copy-on-Write paths (`CowPath`, `CowFieldProjection`, `CowIndexProjection`) with deterministic evaluation ordering.
- [x] Short-circuit operators (`and`, `or`, `??`) remain strictly conditional, never eagerly evaluating omitted sides.
- [x] Backend operates without AST or semantic string lookups for bindings; shadowing across nested blocks is preserved with unique symbol IDs (`v_x`, `v_x_2`).
- [x] Canonical deterministic HIR dumper (`dump_hir(hir_mod)`).
- [x] Dedicated comprehensive invariant test suite `test_resolved_hir.py`.
- [x] Full test pass: 392/392 checks in `./w test`, 55/55 in `test_hir_conformance.py`, 47/47 in `test_hir_codegen_conformance.py`.

## Reproduction

```bash
python3 test_resolved_hir.py
python3 test_hir_conformance.py
python3 test_hir_codegen_conformance.py
python3 test_compiler_boundaries.py
python3 test_compilation_session.py
python3 test_ci_harness.py
./w test
```

The full suite now passes with 392/392 checks (100% conformance across all engines, examples, and self-hosting harnesses).

## Boundaries and next step

C02 completes the structural and semantic resolution of the High-Level Intermediate Representation (HIR), decoupling the backend code generation, pattern matching, binding verification, and invariant validation completely from the surface AST.

C03 is next: Typed Generic Specialization, instantiation worklist, and structural mangling in HIR before D02 (porting the full pipeline to W1).
