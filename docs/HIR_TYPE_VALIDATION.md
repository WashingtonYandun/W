# HIR type validation boundary

HIR is verified after lowering and again before C emission. The verifier traverses HIR declarations, parameters, fields, blocks, tail expressions, methods, match arms and nested list/tuple children. It checks scalar type_id fields, type_id lists, function return types and interface method signature IDs against the current interner. TYPE_ERROR, negative/out-of-range IDs, None and booleans used as IDs produce W9999 at stage hir-verification.

The checker now records types on assignment targets and resolved type annotations. HirBuilder consumes those annotation IDs rather than reconstructing generic or builtin types from mangled strings. Imported functions are checked using the same interner before lowering; this repairs missing annotations without pretending to implement the planned CompilationSession/module cache.

Regression coverage verifies malformed parameter IDs and return types, including direct backend entry. The existing 48-file HIR corpus is exercised through the active verification boundary.

This is a type-decoration verifier. It does not yet prove operand/result compatibility, lexical binding correctness, ownership, arena provenance for an in-range ID from another arena, or the semantic validity of AST patterns retained in HIR. Canonical type identity, typed patterns, resolved symbols and module sessions remain separate roadmap tasks. Passing this boundary is not a claim of complete semantic HIR verification.


## Additional structural and control-flow checks

- Required type decorations on expressions, parameters, fields, typed declarations and function returns are checked even when an attribute was removed. Missing IDs are not silently skipped.
- Active-path cycle detection rejects cyclic HIR nodes and list/tuple containers before emission. Shared acyclic nodes are allowed and revisited in their control-flow context; a previous visit cannot hide an invalid placement.
- Break/continue require an enclosing loop body, return requires a function, and function boundaries reset loop context. While/if/elif conditions must carry the builtin bool TypeId.
- Tuple element metadata must match its interned tuple type and element count.
- Unknown HIR statements passed directly to the backend raise W9999 rather than disappearing from generated code.

Negative regression tests mutate checked HIR and assert rejection at the backend boundary. Positive tests preserve shared nodes and valid loop transfers. These checks do not yet establish lexical binding, value coercions, ownership, complete node schemas or operand/result compatibility for every expression.

The tuple check exposed an existing multi-payload enum lowering defect: the synthetic payload tuple carried the enum TypeId. Both qualified and unqualified variant construction now intern the actual payload tuple type. generic_tree_recursive.w covers the qualified multi-payload path in the conformance corpus.

## Operand and result relations

The verifier now checks literal kind/type agreement, numeric/string arithmetic, integer modulo, boolean logic, numeric comparisons, unary negation/not, range bounds/result and tuple operand metadata. Equality operators must return bool; alias-aware equality operand compatibility remains a frontend obligation until canonical Optional/Result identity is implemented.

List/dictionary element metadata must match the interned result type. Lowering now derives that metadata from the checked collection type instead of the first element or an arbitrary empty-container default. This fixes typed empty lists such as list[str] carrying int metadata. Contextual typing of an empty dictionary is a separate frontend limitation and is not introduced here.

Regression mutations cover wrong literal/operand/result types, bad range bounds, tuple element mismatch and collection metadata mismatch. Positive coverage includes typed empty lists and dictionaries with concrete key/value types. Collection element assignability, call/return contracts and all expression forms remain future verification work.
