## Description

<!-- Provide a concise description of the motivation and context behind these changes. -->

Fixes #(issue)

## Type of Change

- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding language or compiler capability)
- [ ] Breaking change (fix or feature modifying syntax, types, or runtime ABI)
- [ ] Refactoring (internal restructuring without observable behavioral change)
- [ ] Documentation / Specs (updates to specifications, README, or ADRs)
- [ ] Performance optimization (compiler throughput or runtime speedup)

## Quality & Conformance Checklist

- [ ] **Conformance Suite:** All 347 conformance tests pass (`./w test`).
- [ ] **Memory Safety:** Sanitizers report zero errors or leaks (`./w test --sanitize`).
- [ ] **Bootstrap Parity:** Fixed-point bootstrap SHA256 is verified (if compiler was modified).
- [ ] **Code Formatting:** Code is formatted with `./w fmt`.
- [ ] **Tests Added:** Added corresponding test cases in `tests/` covering new behavior or regressions.
- [ ] **Documentation Updated:** `SPEC.md`, `README.md`, or `docs/adr/` updated if architectural changes were introduced.
- [ ] **Language Boundary:** Commit messages, comments, identifiers, and docs are strictly in English.
