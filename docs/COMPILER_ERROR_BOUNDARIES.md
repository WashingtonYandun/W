# Compiler error boundaries

This increment addresses three concrete failures identified by the compiler audit.

- Generic constraints are validated after declaration collection, including unused templates. A constraint must name a declared interface; missing names, primitive constraints and compound constraints produce W2012. Forward-declared interfaces remain valid. Existing nominal satisfaction rules remain in place.
- Synthesized generic struct constructors are typechecked before entering the emitted declaration list. Their bodies and field arguments receive the same expression annotations as ordinary functions. This removes the eight TYPE_ERROR expressions previously observed in generic_pair.w.
- Unknown AST statements/expressions in HIR lowering and unknown HIR expressions in C emission raise structured W9999 diagnostics with source location and stage. They no longer silently become unit.

Regression coverage lives in test_compiler_boundaries.py and is included in the generic hardening suite used by the full conformance runner.

This increment does not implement the complete HIR verifier, canonical type unification or string ownership redesign. W1 generic parity is now covered by the F01 public corpus, but that does not make W1's token-expanded module frontend equivalent to W0's shared typed compilation sessions. W9999 represents a compiler defect, not a user type error. Constraints in W0 are checked using the current compilation unit's scope.
