# B03 — Strong cycles and weak class references

Branch: feat/b03-weak-references. Base: develop at 58a3c08.
Implementation status: complete; integration pending. See ADR-007 for the contract.

## Delivered gates

- Isolated unbroken strong cycle with an expected memory-leak diagnostic; Linux
  also requires LSan's leak report. The existing broken-cycle fixture must pass.
- Concrete invariant Weak[C] type, weak(object) and upgrade(handle) -> C?. W0 and
  HIR enforce class-only targets, arity, result types and no direct member access.
- Native control blocks with strong/weak counts, pre-destruction invalidation,
  retained live upgrades, expired upgrades returning None and final weak cleanup.
- Copy/identity semantics preserved after expiration; distinct targets stay
  distinct. Default weak fields have valid empty expired handles.
- Interpreter implementation and AST C/HIR C/W1 emission. W1 has dynamic type
  safeguards; its static checker and generic parity remain separate limitations.
- Sanitized success cases for containers of weak handles, class fields, promotion
  across return cleanup, multiple weak references and weak back-references.
- Direct native assertions cover weak stored inside its own object, destruction
  order, control block reclamation and strong ownership after promotion.

## Reproduction

```sh
python3 -m tests.unit.test_weak_control_block
python3 -m tests.unit.test_weak_references
./w test
./w test --differential 20
./w test --fuzz 100
python3 tools/bundle_w1.py --check
```

The targeted acceptance harness runs three fixture profiles across three native
backends (nine isolated processes), plus the native control-block contract and
W0/HIR negative cases. Generic identity specialization with a weak argument is
checked in W0/HIR without claiming W1 generic support. Full results and the exact
commit/CI run are recorded in the PR and public verification record.

Strong-only cycles still leak; there is no collector or concurrent RC. Python GC
behavior is not used to certify native strong-cycle collection. No stable public
C ABI is promised. Weak control blocks require additional allocation per class
object; performance optimization is separate from these lifetime guarantees.

The isolated Linux cycle negative sets LSAN_OPTIONS=use_stacks=0:use_registers=0
to ignore stale machine roots after create_cycle returns. Success cases retain
normal root scanning and leak detection. This changes conservative reachability
for the expected-leak process only; it does not suppress leaked allocations.
