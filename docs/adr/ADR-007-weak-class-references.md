# ADR-007: Weak class references and observable strong cycles

Status: accepted for B03 implementation; pending integration.

## Decision

Strong RC does not collect cycles. Test an unbroken strong cycle in an isolated
native process and expect a memory-leak diagnostic. The ordinary success corpus
must still pass leak detection. Keep the existing explicitly broken-cycle fixture.

Add the invariant builtin type `Weak[Class]`, `weak(object) -> Weak[Class]` and
`upgrade(handle) -> Class?`. Only concrete class types are accepted; structs,
interfaces, lists, scalars and optional class values require different operations
and cannot be weakened implicitly. Weak is a value handle with target identity,
including after expiration. Copies preserve identity and add weak ownership.
Expired references to distinct targets remain distinct. Display is `weak(alive)`
or `weak(expired)`; fields/methods require an explicit upgrade first.

Each native class object has a control block with strong/weak counts and a nullable
object pointer. Strong ownership has an implicit weak reference. At strong zero,
invalidate the pointer before releasing fields, destroy the object and drop the
implicit weak reference. Free the control block only when all weak references are
gone. Upgrade of a live target retains a strong reference before returning it;
upgrade after expiration returns None. Weak never keeps the object body alive.
This also supports weak handles stored in the target's own fields during teardown.

The interpreter uses Python weak references with a stable per-target identity
sentinel. Native memory/control-block reclamation is verified directly; Python GC
behavior is not claimed to model native strong-cycle leakage or every destruction
schedule. A successful upgrade itself keeps the returned object alive.

## Scope

Single-threaded RC; no atomics, collector or automatic conversion between
Weak[Base] and Weak[Derived]. The builtin family does not introduce generic class
support. W1 emits the supported concrete builtin operations; its broader generic
exclusions remain. Weak fields can be optional and can appear inside ordinary
value containers. Strong-only cycles still leak and must be broken explicitly.
