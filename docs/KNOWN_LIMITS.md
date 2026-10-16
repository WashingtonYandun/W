# Known Limits and Deferred Decisions

This file records what W does **not** do, why, and what it would take to change it.
Everything here is a deliberate deferral with a stated cost, not an oversight. Items
marked *open decision* change the language surface and therefore need an explicit call
before any implementation work.

Last reviewed: `0.3.0.dev1`.

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

## 2. A function cannot propagate more than one error type

**What happens.** `?` requires the error type of the operand to match the declared error
type of the enclosing function exactly (SPEC §7, "Error types must match exactly"):

```w
struct E1 { a: int }
struct E2 { b: int }
fn one() -> int ! E1 { return Err(E1 { a: 1 }) }
fn two() -> int ! E2 { return Err(E2 { b: 2 }) }
fn both() -> int ! E1 {
    let x = one()?
    let y = two()?     # W2006: Error type mismatch in '?' propagation: 'E2' vs declared 'E1'
    return x + y
}
```

**Why it is this way.** Exact matching keeps `?` a pure type check with no implicit
conversions, which is consistent with "no hidden mutations" and keeps the diagnostic
deterministic.

**Cost.** Any function whose body can fail in more than one way has to map errors by
hand at every call site:

```w
let y = two() else err { return Err(E1 { a: err.b }) }
```

There is no error union, no error interface, and no `From`-style conversion. User-defined
error types do work (`struct MyErr { code: int }` with `Err(MyErr { code: 7 })` and `?`
propagation), so this is purely about composition.

**What a fix requires.** Either a union type `T ! E1 | E2` (checker work in
`is_assignable`, exhaustiveness for `else err`, plus interning and mangling for the new
type shape) or an implicit conversion step in `?` gated on a declared conversion. The
union is the honest option because it preserves exhaustiveness.

*Open decision.*

---

## 3. W1 is a compiler for a subset, not a second implementation

**What happens.** `selfhost/w1.w` (4.1k lines, bundled from `selfhost/src/*.w`) is a
genuine compiler: its own lexer, recursive-descent parser, a token-driven semantic pass
with type interning, and a direct-to-C emitter that reuses `runtime/w_runtime.h`. W1
supports first-class calls and closures for the forms exercised by the expansion suite,
but it does **not** implement:

| Feature | Diagnostic |
| :--- | :--- |
| Generic declarations, specialization | `W2013 W1 generic declarations are not implemented` |
| Enum payload layout | `W2013 W1 enum payload layout is not implemented` |
| Pattern matching on `Option` / `Result` | `W0001` / `W2001`, see below |
| W0-equivalent checked-module sessions and imported generic specialization | declared unsupported under D02 |

Basic imports are supported: W1 expands the module graph into a token stream, qualifies
module names, enforces `pub` exports, and detects cycles (`selfhost/src/03_modules.w`).
This is not the same architecture as W0's `CompilationSession`: W1 does not maintain a
shared typed-module cache or canonical cross-module declaration identities. The single
`checked_modules` corpus fixture also uses generic imports, which W1 cannot specialize.

Pattern matching on `Option` and `Result` fails in **every** form:

```w
match o { Some(v) => { ... } }        # unqualified: the match-arm scanner rejects '('
match o { Option.Some(v) => { ... } } # qualified: "pattern enum identity"
```

`selfhost/src/*.w` contains zero occurrences of `Some(`, `Ok(` or `Err(`, so the bootstrap
does not exercise the unsupported pattern forms. Separate W1 tests must carry those
contracts; the expansion suite currently exercises closures and first-class calls on W1,
but runs generic OOP, stdlib and C FFI cases only on W0 engines.

**Why it is this way.** W1 is a bootstrap: its purpose is to prove the language can
describe a compiler and reach a reproducible fixed point, not to duplicate W0.

**Cost.** "Self-hosting" here means "recompiles itself with `cc` and a 1.9k-line C runtime
header", and it says nothing about the expressiveness of the language subset it uses. The
three-stage fixed point proves determinism and convergence; it cannot prove correctness,
because a bug in the semantics is reproduced identically at every stage.

**State.** The public core corpus passes on W1. The 15 generic fixtures and one checked-
module fixture are declared unsupported in `tests/engine_profiles.json`; the `release`
profile of `tools/ci_conformance.py` deliberately fails while those exclusions exist.
Closing them is milestone D02.

---

## 4. Runtime panics carry no source location in native builds

**What happens.**

```
$ ./w run div.w                # [W4001] div.w:3:14 - Division by zero
$ ./w build div.w -o div && ./div
                               # [W4001] RuntimeError: Division by zero
```

**Why it is this way.** Panic sites are inline `fprintf`/`exit` calls in
`runtime/w_runtime.h`, which has no notion of the source position of the operation that
failed. Adding one means the emitter must pass a file/line pair into every potentially
failing runtime entry (`w_div`, `w_mod`, `w_index_get`, `w_unwrap_optional`, ...).

**Cost.** A native binary that panics tells you *what* failed but not *where*. Debuggable
enough for a small tool, not for production.

**Fix.** Thread a `(const char* file, int line)` pair, or a per-statement
`w_set_position()` before each panicking operation, and have the panic helpers print it.
Mechanical but broad.

---

## 5. Strong reference cycles leak unless detected explicitly

**What happens.** An acyclic value subgraph cannot be built, because a value container can
hold a class reference and the class can hold that same container:

```w
class Node { public name: str, public children: list[Node] ... }
let n = Node("root")
n.children.append(n)           # value storage now reaches back to the object
```

Nothing is reclaimed. `W_MEM_CHECK=1` reports it at exit:

```
[W4003] RuntimeError: Memory leak detected at exit (alloc=3, free=0, live=3)
```

Without that environment variable the program exits 0 in silence.

**Why it is this way.** ARC alone cannot collect cycles, and a cycle collector would add
pause behaviour and complexity that the "deterministic refcounting" promise in SPEC §8
rules out.

**Cost.** `Weak[C]` is the sanctioned escape hatch and works, but nothing forces its use
and nothing reports the mistake unless the memory check is on.

**Suggested next step (small, no language change).** Make the runtime report the leak
count unconditionally at exit when the process is terminating normally, or enable the
existing check by default in `w run` and `w build` during development. Detecting the cycle
is already implemented; only the reporting policy is missing.

*Open decision* (policy, not semantics).

---

## 6. The runtime is single-threaded, and that is the whole concurrency story

Refcounts are plain `int32_t`, there is no atomic operation anywhere, and there is no
thread, task or async primitive in the language or the stdlib. This is consistent and
documented, but it bounds the audience: W is for single-threaded native tools. Anything
that needs to overlap I/O or use more than one core is out of scope until the memory model
gains either atomics or a "no shared state" discipline with a runtime that enforces it.

*Open decision* — the largest one in this file.

---

## 7. Smaller deferrals

| Item | State |
| :--- | :--- |
| Chained assignment | `a = b = 1` works. `d = e = f = 9` is rejected with `W2013`: assignment is an expression, the HIR has no node for it, and each level synthesises a temporary, so only one nested level is verified. Split the chain. |
| Parser error recovery | None. The first syntax error aborts the parse, so one diagnostic per run is the maximum. `--json` reports a single object, not an array. |
| `w fmt` coverage | Idempotence is verified on `tests/formatter` and `tests/runtime`; `selfhost/` and `examples/` are not in that gate (they were verified by hand and formatting `selfhost/w1.w` produces byte-identical C). |
| LSP | `initialize`, `didOpen/didChange/didClose`, `definition`, `completion` and `publishDiagnostics`. No hover, references, rename, formatting, signature help, semantic tokens or incremental sync. |
| Dictionary keys | `int`, `str`, `bool`, `enum` only; `float` and composites containing it are rejected with `W2010`. |
| `NetError` | Declared in the prelude (`checker/SymbolTable.py`) and referenced by a parser fixture, but nothing produces one. Either implement a network module or remove the type. |
| Standard library size | `text` (3 functions), `algorithms` (3), `io` (2), `bytes` (2). `join` is O(n). No Unicode normalisation. |
| Benchmark baselines | `bench/BASELINE.md` has no numbers from any compiler other than W's own engines, so "speedup" only describes how slow the Python interpreter is. A hand-written C equivalent is the missing reference point. |
