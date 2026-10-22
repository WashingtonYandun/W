# Known Limits and Deferred Decisions

This file records what W does **not** do, why, and what it would take to change it. It
tracks deferred decisions separately from defects. Items marked *open decision* change
the language surface and need an explicit decision before implementation.

---

## 1. Closures capture immutable snapshots

**What happens.** A lambda captures by value at creation time. The captured names are
rewritten into a synthetic environment struct and the lambda receives it as a hidden
first parameter (`checker/ClosureConversion.py`). Neither reading a later write nor
writing through the capture is possible:

```w
let mut n = 0
let f = |v: int| -> unit { let x = n; print(x + v) }
n = 10
f(1)          # prints 1, not 11 -- `n` was snapshotted at 0
```

```w
let mut xs = [1]
let f = |v: int| -> unit { xs.append(v) }
                          # W3001: Cannot call mutating method 'append' on a captured
                          # variable: closures capture values as immutable snapshots
```

Collections and structs are captured as copy-on-write snapshots, so capturing is cheap
and cannot alias the enclosing frame. Classes keep identity and a strong reference, so
mutating a captured *object* is visible to everyone holding it.

**Why it is this way.** A snapshot needs no shared mutable state, which is what makes
the single-threaded ARC model and the copy-on-write guarantees in SPEC §8 simple to
reason about.

**Cost.** The stateful-closure idiom is not expressible:

```w
fn make_counter() -> fn() -> int {
    # There is no way to write this. The usual workaround is a class with a private
    # field, or threading an explicit accumulator through every call.
}
```

**What a fix requires.** Real sharing needs one allocation per captured mutable
variable that both the enclosing frame and the closure read and write through. That
means the checker must decide which locals become cells (any local captured by a lambda
and mutated anywhere), the interpreter, the HIR and the W1 backend must all agree on the
representation, and the ARC/CoW interaction has to be re-verified with the sanitizers.
This is a language change, not a patch.

*Open decision.*

---

## 2. Error unions have restricted alternatives

**Behavior.** `T ! E1 | E2` allows `?` to propagate multiple error types and `match` to
exhaustively inspect the value bound by `else err`. A source error set can propagate when
it is a subset of the destination function's declared error set. Payloads are not
converted.

Supported alternatives are `int`, `float`, `bool`, `str`, non-generic `struct`, and
non-generic `enum`. Patterns use `Type(error)` or `Type(_)` and bind the full payload.
Duplicate alternatives are canonicalized; a union must contain at least two distinct
alternatives.

**Limit.** Classes, generic types, collections, tuples, functions, and other composite
types are not supported. Class hierarchies may overlap, and collections and functions do
not preserve their concrete parameter identity in `WVal`. Without additional runtime
type descriptors, patterns could not distinguish these alternatives safely. F03 keeps
the original payload and compares its runtime identity; it adds no boxing or implicit
conversion.

**Future work.** Expanding the set requires a runtime identity contract for each new
category, especially inherited classes and monomorphized generic types.

---

## 3. W1 support is bounded by the tested corpus

W1 is a self-hosted compiler with a narrower supported profile than W0. Its measured
coverage is maintained in the [engine parity matrix](ENGINE_PARITY_MATRIX.md); passing
the listed fixtures does not guarantee equivalent behaviour for every W program.

W1 expands imported modules into a token stream and qualifies module names, but it does
not share W0's typed compilation sessions or canonical declaration arena. The bootstrap
fixed point demonstrates deterministic self-hosting, not universal language parity or
semantic correctness outside the tested programs.

Installed wheels contain W0, its C runtime header and the standard library; Python
remains a prerequisite. W1 bootstrap, `w test` and `w bench` require a source checkout.
El instalador autónomo de Windows incluye un runtime Python privado y Zig como
toolchain C99 para W0; no necesita un entorno virtual ni un SDK C del host. Se prueba
por separado del wheel, incluida instalación, reparación y desinstalación. Su alcance
inicial es Windows 10/11 x64; las bibliotecas FFI externas no se incluyen. La generación
en CI no establece por sí sola una release publicada, firma o validación manual.
Missing W1 sources produce `W2013` before any bootstrap-cache write. W0 native builds
require a host C99 toolchain; an unavailable or invalid compiler command produces
`W5001` with stage `toolchain`, rather than an internal compiler error. This checks
command availability, not the completeness of a host SDK or external FFI libraries.


## 4. Native runtime panic locations have a defined supported scope

**What happens.**

Native AST C99, HIR C99, and W1 builds now report exact source locations for the
operational panic cases `W4001` (division/modulo by zero) and `W4002` (invalid list,
string, or dictionary reads; invalid list index writes; and `list.pop()` on an empty
list). The location is attached to the runtime operation itself, so nested expressions
do not accidentally report the location of a later operand.

The runtime still falls back to `[Wxxxx] RuntimeError: ...` for calls made without a W
source span and for other runtime failures, especially internal `W4003` memory/type
invariant failures. This is deliberate: those failures are not reliably attributable to
one user expression. The interpreter continues to report its existing source spans.

---

## 5. Strong reference cycles leak unless detected explicitly

**What happens.** An acyclic heap cannot be guaranteed, because a value container can
hold a class reference and the class can hold that same container:

```w
class Node { public name: str, public children: list[Node] ... }
let n = Node("root")
n.children.append(n)           # value storage now reaches back to the object
```

Nothing is reclaimed. `WYSNA_MEM_CHECK=1` reports it at exit:

```
[W4003] RuntimeError: Memory leak detected at exit (alloc=3, free=0, live=3)
```

Without that environment variable the program exits 0 in silence.

**Why it is this way.** ARC alone cannot collect cycles, and a cycle collector would add
pause behaviour and complexity that the "deterministic refcounting" promise in SPEC §8
rules out.

**Policy.** `WYSNA_MEM_CHECK` is opt-in and checks logical runtime allocation counters during
normal cleanup. It does not collect cycles, run on panic-driven `exit()`, or replace
ASan/LSan byte-level checks in development and CI. Keeping it opt-in avoids changing
stderr or exit status for production programs that intentionally retain process-lifetime
objects.

**Cost.** `Weak[C]` is the sanctioned escape hatch and works, but nothing forces its use
and a strong cycle is silent unless the memory check or an external leak detector is on.

**Decision.** Keep `WYSNA_MEM_CHECK` explicitly opt-in in every execution mode. Runtime
defaults must not change stderr or exit status based on build mode. Native runtime diagnostics remain opt-in through `WYSNA_MEM_CHECK`.

---

## 6. The runtime is single-threaded, and that is the whole concurrency story

Refcounts are plain `int32_t`, there is no atomic operation anywhere, and there is no
thread, task or async primitive in the language or the stdlib. Wysna's current supported
profile is synchronous, single-threaded native programs. Adding concurrency would require
a separate memory-model decision, an explicit sharing/ownership contract, and cross-engine
runtime work; it is not part of the current language roadmap.

**Decision: closed for the current release line.** Keep the runtime single-threaded and
the standard library synchronous. Reopen this decision only with a concrete workload and
a proposed memory model; do not treat this as an implicit promise that ARC is thread-safe.

---

## 7. Smaller deferrals

| Item | State |
| :--- | :--- |
| Chained assignment | HIR uses `HirAssignment`; the value is preserved and each index is evaluated once. The artificial depth limit was removed. |
| Parser error recovery | Check and LSP recover up to 100 syntax diagnostics. JSON preserves the first error and adds `diagnostics`; recovered programs never execute. |
| `w fmt` coverage | The gate checks idempotence and AST preservation across fixtures, runtime programs, recursive examples, the standard library, and self-hosted sources. It also runs generated trees before and after formatting. |
| LSP | `initialize`, `didOpen/didChange/didClose`, `definition`, `hover`, `completion`, document formatting and `publishDiagnostics`. No references, rename, signature help, semantic tokens or incremental sync. |
| Dictionary keys | `int`, `str`, `bool`, `enum` only; `float` and composites containing it are rejected with `W2010`. |
| `NetError` | Declared in the prelude (`checker/SymbolTable.py`) and referenced by a parser fixture, but nothing produces one. Either implement a network module or remove the type. |
| Standard library size | `text` (3 functions), `algorithms` (3), `io` (2), `bytes` (2). `join` takes O(output bytes + parts) using a two-pass builder. No Unicode normalization. |

The CLI has POSIX and Windows adapters for cache locks, compiler processes, executable
names and RSS telemetry. The Windows smoke job must pass on that host before support
is announced. A successful macOS run does not establish Windows compatibility.

Class cycles format finitely as `<cycle>` but still require Weak or explicit breaking
to be reclaimed. `std/resources` does not make raw opaque aliases safe or unwind panic.

Standard File/Bytes owners now release host storage at last reference; they do not
extend that guarantee to arbitrary FFI pointers or strong cycles. IO remains
synchronous. JSON, task isolation, cancellation and nonblocking networking require
the acceptance contracts in [Service foundations](SERVICE_FOUNDATIONS.md).
