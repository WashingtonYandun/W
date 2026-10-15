# B01 — Ownership across control flow

Status: implemented; verification results and PR are recorded in the project verification records.
Branch: feat/ownership-control-flow, based on develop at 8dae8e2.

## Resolved defects

- Earlier arguments, field reads, binary operands and collection entries could be
  evaluated after a later mutation. Retained snapshots now preserve their value
  and storage lifetime before subsequent expressions execute.
- Empty constructors and ranges used as discarded expressions could allocate
  without registering a release obligation. They now enter scope cleanup.
- Assignment RHS holds were not registered while targets were evaluated. A target
  that propagated an error could leak the RHS. Holds now register before target
  evaluation and move on successful storage.
- W1 previously emitted target effects before the RHS. It now restores emission
  state and replays target emission after the owned RHS, including nested target
  indices. Argument and receiver snapshots follow the same native conventions.
- W1 method metadata scanning could misread adjacent separators for temporary
  receivers. Separators are now parsed without overlapping matches.
- W1's supported non-generic profile now emits unqualified Ok/Err constructors
  with consuming payload ownership, allowing the B01 propagation fixture to run
  directly through W1.

## Contracts and evidence

The helper inventory and exit rules are in `docs/OWNERSHIP_LIFETIME.md`.
`python3 -m tests.unit.test_ownership_control_flow` checks interpreter output against sanitized
AST C, HIR C and standalone W1 C. W_MEM_CHECK is enabled everywhere; Linux also
uses LSan. The test is included in full conformance and both sanitizer CI jobs.

Against origin/develop before these changes, the AST backend's regression fixture
printed `1 1` instead of `0 1`, changed the first dictionary key/argument after a
later mutation, and exited with five live allocations (86 allocations, 81 frees).
This demonstrates both observable order defects and leaks; sanitizer success on
the corrected tree is recorded separately in the PR/session.

Covered paths: normal exits; local field/index returns; temporary receivers;
self-assignment; collection arguments; indexing once; nested for/while break and
continue; result/optional propagation; match and else handlers; failing assignment
targets; lazy and/or/coalesce; discarded empty values and ranges.

## Limits

Snapshots increase retain/release traffic and can force earlier CoW detachment.
B02 must measure this cost. Ownership is still encoded by emitter conventions,
not a dedicated typed ownership IR. W1 generic exclusions persist. Strong cycles
remain B03; explicit process exit/panics do not unwind scopes. This acceptance
corpus is dynamic evidence, not a proof of all programs or allocation-failure paths.
