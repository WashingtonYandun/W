# ADR-008: Whole-program compilation sessions and checked module units

Status: accepted for W0 (C01). W1 adoption remains D02.

## Problem

Each import previously created a separate TypeInterner. HIR opened the source again, parsed it and ran another checker while attempting to replace its arena. Numeric TypeIds could therefore refer to unrelated types, generic annotations were lost and imported nominal declarations were not lowered consistently. The interpreter and AST backend also loaded imports independently.

## Decision

A CompilationSession owns a SourceManager, one TypeInterner, checked units, active import paths and declaration identities. All dependency checkers use that same arena. Existing `TypeChecker.check(program)` creates or uses a session; callers that need reuse pass `session=` or call `session.check_source(...)`. The old `checked_modules`/`active_imports` constructor dictionaries are replaced by the session because they cannot establish checked-AST or arena provenance.

- ModuleId is the canonical real path expressed relative to an explicit project root. Symlink aliases identify the same module.
- DeclId is `(ModuleId, declaration kind, source name)`. Concrete specializations use their generated names; this is an internal identity, not a persistent ABI or a replacement for C03 mangling.
- TypeInterner assigns a process-local arena identity. Synthesized nominal annotations and HIR modules carry provenance, and mismatched arenas are rejected.
- CheckedModule retains its checked AST, checker, export scope, dependency edges, source hash and cache key. The key includes content, options, entry role and dependency keys.
- In-memory reuse applies to a fixed entry point. Content, options or entry changes conservatively invalidate all units and create a new arena. File timestamps are not a correctness key. Old checked units cannot be linked against a new generation. There is no persistent disk cache.
- Active imports are checked before cache lookup. W1003 reports the complete canonical logical import chain at the importing source span.

## Lowering and execution

Consumers link the checked dependency graph once in dependency order. A shared dependency contributes declarations and top-level initialization once, even through multiple namespaces. Imported functions named `main` are ordinary functions; only the root entry follows the existing top-level/main selection rule.

Imported declarations receive unambiguous internal names derived from ModuleId, with lexical value/type bindings preserved. `__wm_` is reserved for compiler identifiers. Runtime identity retains the qualified name, while normal value display uses the source name. Type diagnostics use readable `module::name` identities. The adapter is transitional: C02 must introduce resolved SymbolId/FieldId/VariantId instead of treating this naming pass as complete semantic resolution.

Static namespace members resolve to the checked export declarations. Imported generic functions specialize in their defining checker and shared arena; caller nominal types retain trusted arena provenance. New specializations are added to the owning checked unit without reparsing its source. Both inferred and explicit module function type arguments are supported.

Module namespaces have no runtime value representation in these backends. Storing, passing or printing a namespace now fails with W2003 rather than reaching an unresolved variable or invalid HIR. Public export rules, module values and qualified type syntax are not introduced by this ADR; E03 retains that language-design scope.

HIR spans retain source paths and ModuleId as file identity, so dependency verification errors report the dependency file. HIR and AST emission require checked import units; they no longer open dependency source files. The interpreter also uses the checked graph.

## Consequences

Whole-program checking and lowering share the same type meanings. Diamond and symlink imports preserve declaration identity and execute initialization once. Reuse avoids repeated parsing/checking; invalidation prioritizes correctness over fine-grained incremental compilation.

This changes previously inconsistent import behavior, including duplicate module initialization and running imported `main` functions. These behaviors are now explicitly defined and tested. W1 has not acquired this pipeline; the checked-module fixture is declared unsupported for W1 in the engine manifest. Release coverage remains blocked until D02.
