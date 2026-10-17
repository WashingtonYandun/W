# Known Limits and Deferred Decisions

This file records what W does **not** do, why, and what it would take to change it.
Incluye decisiones diferidas y límites conocidos; no convierte defectos en decisiones. Items
marked *open decision* change the language surface and therefore need an explicit call
before any implementation work.

Last reviewed: `2026-10-16`.

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

## 2. Las uniones de error tienen alternativas restringidas

**Qué ocurre.** `T ! E1 | E2` permite propagar distintos errores con `?` y hacer un
`match` exhaustivo sobre el valor ligado por `else err`. El origen se propaga si su
conjunto de errores es subconjunto del conjunto declarado por la función destino. No se
convierten los payloads.

Las alternativas admitidas son `int`, `float`, `bool`, `str`, `struct` no genéricos y
`enum` no genéricos. El patrón es `Tipo(error)` o `Tipo(_)` y liga el payload completo.
Las alternativas repetidas se canonicalizan; la unión necesita al menos dos alternativas
distintas.

**Límite.** No se admiten clases, tipos genéricos, colecciones, tuplas, funciones ni otros
tipos compuestos. Las clases pueden pertenecer a jerarquías superpuestas; colecciones y
funciones no conservan en `WVal` la identidad concreta de sus parámetros. Permitirlos sin
un descriptor runtime adicional haría que los patrones no pudieran distinguir las
alternativas de forma segura. F03 mantiene el payload original y compara su identidad
runtime; no añade una caja ni una conversión implícita.

**Trabajo futuro.** Ampliar este conjunto requiere un contrato de identidad runtime para
cada nueva categoría, especialmente clases con herencia y tipos genéricos monomorfizados.

---

## 3. W1 support is bounded by the tested corpus

W1 is a self-hosted compiler with a narrower supported profile than W0. Its measured
coverage is maintained in the [engine parity matrix](ENGINE_PARITY_MATRIX.md); passing
the listed fixtures does not guarantee equivalent behaviour for every W program.

W1 expands imported modules into a token stream and qualifies module names, but it does
not share W0's typed compilation sessions or canonical declaration arena. The bootstrap
fixed point demonstrates deterministic self-hosting, not universal language parity or
semantic correctness outside the tested programs.


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

Nothing is reclaimed. `W_MEM_CHECK=1` reports it at exit:

```
[W4003] RuntimeError: Memory leak detected at exit (alloc=3, free=0, live=3)
```

Without that environment variable the program exits 0 in silence.

**Why it is this way.** ARC alone cannot collect cycles, and a cycle collector would add
pause behaviour and complexity that the "deterministic refcounting" promise in SPEC §8
rules out.

**Policy.** `W_MEM_CHECK` is opt-in and checks logical runtime allocation counters during
normal cleanup. It does not collect cycles, run on panic-driven `exit()`, or replace
ASan/LSan byte-level checks in development and CI. Keeping it opt-in avoids changing
stderr or exit status for production programs that intentionally retain process-lifetime
objects.

**Cost.** `Weak[C]` is the sanctioned escape hatch and works, but nothing forces its use
and a strong cycle is silent unless the memory check or an external leak detector is on.

**Decision.** Keep `W_MEM_CHECK` explicitly opt-in in every execution mode. Runtime
defaults must not change stderr or exit status based on build mode. See
Native runtime diagnostics remain opt-in through `W_MEM_CHECK`.

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
| Asignación encadenada | HIR usa `HirAssignment`; se conserva el valor y cada índice se evalúa una vez. El límite artificial de profundidad fue eliminado. |
| Parser error recovery | None. The first syntax error aborts the parse, so one diagnostic per run is the maximum. `--json` reports a single object, not an array. |
| `w fmt` coverage | El gate verifica idempotencia y AST preservado en fixtures, runtime, ejemplos recursivos, stdlib y selfhost; también ejecuta árboles generados antes y después del formato. |
| LSP | `initialize`, `didOpen/didChange/didClose`, `definition`, `completion` and `publishDiagnostics`. No hover, references, rename, formatting, signature help, semantic tokens or incremental sync. |
| Dictionary keys | `int`, `str`, `bool`, `enum` only; `float` and composites containing it are rejected with `W2010`. |
| `NetError` | Declared in the prelude (`checker/SymbolTable.py`) and referenced by a parser fixture, but nothing produces one. Either implement a network module or remove the type. |
| Standard library size | `text` (3 functions), `algorithms` (3), `io` (2), `bytes` (2). `join` cuesta O(bytes de salida + partes), con un builder de dos pasadas. No Unicode normalisation. |
