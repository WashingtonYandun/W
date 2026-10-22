# Changelog

## 0.5.0 — Release Candidate Preparation

### Language and Compilers

- Consolidates **Wysna** as the language identity and removes token aliases and
  internal prefixes inherited from experimental names.
- Adds newline and `;` statement separators. The rule covers LF, CRLF, and CR;
  newlines inside parentheses and brackets remain part of expressions.
- Unifies negative integer handling: the lexer emits a unary operator and the parser
  recognizes the `INT64_MIN` boundary.
- Aligns the self-hosted compiler's parser and semantic validator with the new
  separators and with newlines before `else`/`elif` and `else err` handlers.
- Adds a runtime regression covering statement boundaries, returns, branches, error
  handling, and multiline lists.

### Documentation and Scope

- Clarifies the roles of Wysna Seed and Wysna Compiler. Seed remains the reference
  AST/HIR/MIR pipeline; the self-hosted compiler retains its direct C99 emitter and
  measured profile in the parity matrix.
- Records the audit findings that remain open in [docs/KNOWN_LIMITS.md](docs/KNOWN_LIMITS.md):
  `WVal` representation, CoW cost, checking of uninstantiated generic functions,
  benchmarks, and parser recovery.
- Preserves the existing C ABI in this version; its documented types and names remain
  part of the current contract.

### Verification

Tag this version only after the `release` gates, conformance suite, deterministic
bootstrap, Python tests, and sanitizer and distribution checks pass on supported
systems. This branch does not claim that an official release has been published.
