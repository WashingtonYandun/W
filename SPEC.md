# W Language Specification

> **Status:** The current toolchain is `0.3.0.dev1`. Sections 1–11 describe the frozen core grammar and are normative; sections 12–14 describe implementation contracts.
>
> **Targets:** `W0` is the reference implementation and the authority on whether a program is valid. `W1` is an experimental self-hosted compiler whose supported subset is measured by the public release corpus. That corpus now includes generic fixtures, checked modules, `Option`/`Result` patterns and F03 error unions; passing it does not establish universal parity. See [docs/ENGINE_PARITY_MATRIX.md](docs/ENGINE_PARITY_MATRIX.md) and §12.
>
> **Thesis:** W is a compact, statically typed language for small native tools, with deterministic diagnostics and inspectable C99 output. Expansion beyond this core is documented in [docs/EXPANSION.md](docs/EXPANSION.md).

---

## 1. The Four Foundational Pillars

1. **Compact:** Maximum semantic intention expressed per token. No unnecessary syntactic ceremony.
2. **Deterministic:** Canonical syntax with zero whitespace ambiguity, zero hidden mutations, and zero implicit nullability.
3. **Statically Typed:** Strict type safety with full local inference and mandatory explicit types on function boundaries.
4. **Self-Hostable:** Minimalist micro-kernel designed to compile its own compiler to standard C without heavy external dependencies.

---

## 2. Lexical Inventory (Keywords)

The language defines the following reserved keywords:

```text
DECLARATIONS (6):
fn        let       mut       struct    enum      import

OBJECT-ORIENTED (9):
class     interface extends   implements new       this      super     public    private

CONTROL FLOW (10):
if        elif      else      for       while     in        match     return    break     continue

PRIMITIVE LITERALS (3):
true      false     none

LOGICAL OPERATORS (3):
and       or        not
```

*Note on built-in types:* Primitive types (`int`, `float`, `bool`, `str`, `unit`) and standard library symbols (`len`, `enumerate`, `bytes`) are prelude identifiers in the global namespace, **not** language keywords.

---

## 3. Lexical Structure

### 3.1 Identifiers
Identifiers must start with an ASCII letter (`a-z`, `A-Z`) or underscore `_`, followed by letters, digits, or underscores. Identifiers cannot match any of the reserved keywords.

### 3.2 Literals, Integer Arithmetic & IEEE-754 Floating-Point Semantics
* **Integers (`int`):** 64-bit signed two's complement integers (`-9_223_372_036_854_775_808` to `9_223_372_036_854_775_807`). Supports optional `_` digit separators:
  `0`, `42`, `-10`, `1_000_000`.
* **Integer Overflow & Division:** Integer addition (`+`), subtraction (`-`), multiplication (`*`), and unary negation (`-`) use **defined 64-bit two's complement wrapping semantics** (via unsigned cast arithmetic in C99, never undefined behavior). Integer division (`/`) truncates toward zero; division or modulo (`%`) by zero triggers a deterministic runtime panic.
* **Floats (`float` — IEEE-754 `binary64`):** IEEE-754 64-bit double-precision floating-point numbers. Literals must include digits both before and after the decimal point (`3.14`, `-0.5`, `100.0`; forms such as `.5` or `1.` are invalid):
  - **Signed Zero:** `+0.0 == -0.0` evaluates to `true`, and `+0.0 != -0.0` evaluates to `false`.
  - **`NaN` Semantics:** Following IEEE-754, `NaN` is unordered and irreflexive: `NaN == x` is always `false` (including `NaN == NaN`, which is `false`), `NaN != x` is always `true` (including `NaN != NaN`, which is `true`), and all relational comparisons (`<`, `<=`, `>`, `>=`) where either operand is `NaN` evaluate to `false`.
  - **Infinities (`+Inf` / `-Inf`):** Overflowing floating-point operations or conversions (`float("inf")`, `float("-inf")`) obey IEEE-754 ordering (`-Inf < finite < +Inf`, `+Inf == +Inf` is `true`, `-Inf == -Inf` is `true`). Doing arithmetic such as `Inf - Inf` yields `NaN`.
  - **Float Division by Zero:** Explicit division by zero (`x / 0.0` or `x / -0.0`) triggers a deterministic runtime panic (`RuntimeError: Division by zero`) rather than silently producing `NaN` or `±Inf`.
* **Booleans (`bool`):** `true` and `false`.
* **None (`none`):** The singular value of an empty optional.

### 3.3 Strings (`str`) & Unicode Scalar Semantics
* **UTF-8 Storage:** Strings are immutable and stored as UTF-8 in memory.
* **Unicode Scalar Value Indexing:** `len(s)`, `s[i]`, `slice(s, start, end)`, `ord(s)`, and `chr(c)` operate strictly on **Unicode Scalar Values (Code Points)** (`U+0000..=U+D7FF` and `U+E000..=U+10FFFF`), returning a single code-point string (`str`) or code-point count:
  ```w
  let s = "José"
  s[3]    # returns "é" (4th Unicode scalar value)
  len(s)  # returns 4
  ```
* **Grapheme Clusters:** Extended grapheme cluster segmentation (e.g., multi-code-point emoji sequences joined by ZWJ) is not performed by core string indexing and is reserved for future Unicode library utilities.
* **Byte Access:** Low-level UTF-8 byte access is explicitly provided via `bytes(s) -> list[int]`.
* **Escape Sequences:** `\n`, `\r`, `\t`, `\\`, `\"`, `\0`, `\u{HHHH}` (1 to 6 hex digits).

### 3.4 Comments and Delimiters
* **Comments:** Only line comments starting with `#`. Doc-comments start with `##`.
* **Delimiters:** Braces `{}` are mandatory for blocks (`if`, `for`, `while`, `fn`, `match`, `struct`, `class`, `interface`). Semicolons are not used.

---

## 4. Type System & Nullability

### 4.1 Primitive & Built-in Types
* `int`: 64-bit signed integer.
* `float`: 64-bit floating point.
* `bool`: Boolean truth value.
* `str`: Immutable UTF-8 text with code-point indexing.
* `unit`: Type indicating the absence of a meaningful value for functions that return nothing.

> **`any` is not a user-facing type.** The compiler uses it internally as the wildcard
> parameter type of variadic builtins (`print`, `len`, `enumerate`, ...) and as a
> placeholder during generic inference. It is deliberately unreachable from source:
> `let x: any = ...` is rejected with `W1001`. A bidirectionally-assignable top type
> would let a function declared `-> int` return a string unobserved, and would launder
> the invariance of `list[T]` and `Weak[C]`.

### 4.2 Explicit Nullability (`T?`)
* Types are **non-nullable by default**. Assigning `none` to a non-optional type is a compile-time error:
  ```w
  let name: str = none     # COMPILE ERROR
  let name: str? = none    # VALID: explicit optional
  ```
* Functions returning no value return `unit`:
  ```w
  fn greet(name: str) -> unit {
      print("Hello, ", name)
      return               # Bare return allowed only in unit functions
  }
  
  # Syntactic sugar: omitting return type defaults to -> unit
  fn log_msg(msg: str) {
      print(msg)
  }
  ```

A bare `return` is one that is followed by `}`, `)`, `]`, `,`, `else`, `elif` or EOF.
It is **not** decided by line breaks: `return` followed by an expression on the next
line returns that expression, and the value may span lines.

### 4.3 Composite Collections
* `list[T]`: Dynamically sized contiguous homogeneous array (`[1, 2, 3]`).
* `dict[K, V]`: Associative key-value table (`{"key": 42}`).
  - **Reads:** `d[k]` yields `V` and panics with `W4002` when the key is absent. The
    optional form is `d.get(k)`, which returns `V?` and never panics. W has no
    auto-narrowing, so a single optional-deducing operator for the common case would
    force every dictionary read through unwrapping ceremony.
  - **Key Domain & `float` Restriction (`W2010`):** Dictionary keys `K` must belong to W's predictable key domain (`int`, `str`, `bool`, or `enum`). While some languages permit floating-point dictionary keys by defining custom canonicalization rules for `NaN` bit patterns and signed zeros (`+0.0` vs `-0.0`), W deliberately restricts the dictionary key model for predictability and rejects `float` (and any composite type containing `float`) as a key type `K` at compile time with diagnostic `W2010` (`INVALID_DICT_KEY_TYPE`).
* `tuple[T1, T2, ...]`: Fixed-size heterogeneous immutable product type (`(1, "ok", true)`).

### 4.4 Sum Types (`enum`)
Closed enumerations for modeling variant states:
```w
enum TokenKind {
    Ident
    Number
    String
    Keyword
    Op
    Eof
}
```

### 4.5 Value-Type Records (`struct`) with Mandatory Named Initialization
`struct` defines pure Copy-on-Write value records:
```w
struct Token {
    kind: TokenKind
    value: str
    line: int
    col: int
}

# Named initialization is strictly required:
let tok = Token {
    kind: TokenKind.Ident,
    value: "foo",
    line: 1,
    col: 10,
}
```

### 4.6 Object-Oriented Programming (`class` & `interface`)
Alongside value-type `struct` and `enum`, W supports Java-style reference-type classes, single inheritance (`extends`), multiple interface contracts (`implements`), visibility modifiers (`public` / `private`), constructors (`fn init`), and runtime polymorphism:

```w
interface Describable {
    fn describe() -> str
}

class Animal {
    public name: str
    private energy: int

    fn init(name: str, energy: int) {
        this.name = name
        this.energy = energy
    }

    public fn speak() -> str {
        return this.name + " makes a sound"
    }

    public fn get_energy() -> int {
        return this.energy
    }
}

class Dog extends Animal implements Describable {
    public breed: str

    fn init(name: str, breed: str) {
        super.init(name, 100)
        this.breed = breed
    }

    public fn speak() -> str {
        return this.name + " (" + this.breed + ") barks: Woof!"
    }

    public fn describe() -> str {
        return this.speak()
    }
}

let d: Describable = Dog("Rex", "Husky")  # Preferred constructor syntax (new Dog(...) also valid in v0.1.x)
print(d.describe())
```
* **Reference Semantics vs Value Semantics:** `struct` values use Copy-on-Write (`W_STRUCT`), whereas `class` instances allocated via `ClassName(...)` (or `new ClassName(...)`) have reference identity (`W_OBJECT`) managed via deterministic reference counting.
* **Constructor Syntax Policy:** Direct invocation `ClassName(...)` is the preferred constructor syntax starting in `v0.1.1`. The `new ClassName(...)` form remains valid throughout `v0.1.x` for backwards compatibility and is slated for deprecation in `v0.2`.
* **Functional Programming Synergy:** Interfaces with a single method (`interface`) and `fn(...) -> R` signatures are designed to interoperate seamlessly with functional programming constructs.

---

## 5. Expressions, Operators, Precedence & Evaluation Order

Evaluation follows an explicit 12-level precedence hierarchy:

| Level | Operator | Description | Associativity |
| :---: | :--- | :--- | :---: |
| **1** | `()` | Grouping, function calls | Left |
| **2** | `.` `[]` | Member access, indexing | Left |
| **3** | `-` `not` | Unary negation, logical NOT | Right |
| **4** | `*` `/` `%` | Multiplicative | Left |
| **5** | `+` `-` | Additive, string concatenation | Left |
| **6** | `..` `..=` | Exclusive range, inclusive range | Left (chained ranges are accepted; a range is a value, not a comparator) |
| **7** | `<` `<=` `>` `>=` | Relational comparisons | Left |
| **8** | `==` `!=` | Equality comparisons | Left |
| **9** | `and` | Short-circuit logical AND | Left |
| **10** | `or` | Short-circuit logical OR | Left |
| **11** | `??` | Null-coalescing (`a ?? fallback`) | Right |
| **12** | `=` | Assignment | Right |

### 5.1 Deterministic Left-to-Right Evaluation Order
W guarantees **strict left-to-right ($L \rightarrow R$) evaluation order** across all composite expressions, independent of target C compiler argument ordering:
* **Function and Method Calls:** In `foo(a(), b(), c())`, the receiver (if any) is evaluated first, followed by `a()`, `b()`, and `c()` in strict left-to-right order before invoking `foo`.
* **Binary Expressions:** In `f() + g() * h()`, sub-expressions evaluate left-to-right within each operator node (`f()` before the product `g() * h()`, and `g()` before `h()`). Short-circuit operators (`and`, `or`, `??`) evaluate their left operand first and evaluate their right operand only when required.
* **Assignments:** In indexed or member assignments (`a()[b()] = c()` or `obj().field = val()`), the target container, index/member, and right-hand value are evaluated deterministically.
* **Composite Literals:** Elements of `list`, `tuple`, `dict`, and fields of `struct` literals are evaluated in lexical left-to-right appearance order.

### 5.2 Equality Semantics (`==` and `!=`)
Equality is partitioned cleanly along the value vs reference boundary:
* **Primitives & Enums (`int`, `float`, `bool`, `str`, `unit`, `none`, `enum`):** Value equality (`"abc" == "abc"` is `true`).
* **Composite Value Types (`list[T]`, `dict[K, V]`, `tuple[...]`, `struct`):** Recursive structural value equality (`[1, 2] == [1, 2]` is `true`; `Point { x: 1, y: 2 } == Point { x: 1, y: 2 }` is `true`).
* **Reference Types (`class`):** Reference identity equality (`obj1 == obj2` is `true` if and only if both bindings point to the exact same allocated instance in memory).

### 5.3 Formal Desugaring of `?` (`T?` and `T ! E`)
1. **Type Level (`T?`):** Defines an optional type (official W optional representation).
2. **Expression Level (`expr?`):** Postfix unwrapping and early-return propagation operator defined by explicit semantic desugaring:
   - **For Optional (`expr: T?`) inside a function returning `U?`:**
     ```w
     let x = expr?
     # Semantically equivalent to:
     # if expr is none -> return none; else -> unwrap value
     ```
   - **For Fallible Result (`expr: T ! E`) inside a function returning `U ! E`:**
     ```w
     let x = expr?
     # Semantically equivalent to:
     # if expr is err(e) -> return err(e); else -> unwrap ok value
     ```

---

## 6. Control Flow & Pattern Matching

### 6.1 Variables: Immutability by Default
* `let x = 42`: Immutable binding with local type inference.
* `let mut count = 0`: Mutable binding.
* Function parameters are strictly typed and immutable within the body. There is no
  `mut` modifier on a parameter; copy into a `let mut` local to mutate one. Value
  semantics make that copy cheap (copy-on-write) and unambiguous.

### 6.2 Loops
* **Element iteration:**
  ```w
  for item in items {
      print(item)
  }
  ```
* **Indexed iteration via tuple destructuring with `enumerate`:**
  ```w
  for i, item in enumerate(items) {
      print(i, item)
  }
  ```
* **Range iteration:**
  ```w
  for i in 0..10 {    # 0 to 9 (exclusive)
      print(i)
  }
  for i in 1..=10 {   # 1 to 10 (inclusive)
      print(i)
  }
  ```
* **While loops:**
  ```w
  while condition {
      # ...
  }
  ```

### 6.3 Exhaustive `match`
`match` must be exhaustive when switching on `enum` variants:
```w
match tok.kind {
    TokenKind.Number => {
        return parse_number()
    }
    TokenKind.String => {
        return parse_string()
    }
    TokenKind.Ident => {
        return parse_ident()
    }
    TokenKind.Keyword => {
        return parse_keyword()
    }
    TokenKind.Op => {
        return parse_operator()
    }
    TokenKind.Eof => {
        return done()
    }
}
```
* If an `enum` case is missing and no `else =>` fallback is provided, compilation fails with an exhaustiveness error.

---

## 7. Error Handling (`T ! E`)

W does not use non-local stack-unwinding exceptions. Fallible functions declare their error type explicitly:

```w
fn read_file(path: str) -> str ! IoError {
    # ...
}
```

If `main` returns a `Result` and that result is an `Err`, the runtime reports it on
`stderr` as `W4003` and terminates with a non-zero status. W has no stack unwinding, so
this is the only point where an error becomes visible to the process that started the
program; discarding it would make a failing program indistinguishable from a success
for `make`, CI or a shell script.

Handling strategies:
1. **Propagation via `?`:**
   ```w
   let content = read_file("src/main.w")?
   ```
2. **In-place Handling via `else err`:**
   ```w
   let content = read_file("src/main.w") else err {
       print("Failed to read file: ", err.message)
       return
   }
   ```

### Composición de errores

Una firma puede declarar un conjunto cerrado de tipos de error después de `!`:

```w
fn parse() -> Config ! ParseError | IoError
```

La unión solo existe en el canal de error de `T ! E`; no es un tipo unión general.
Debe contener al menos dos alternativas distintas. Se admiten `int`, `float`, `bool`,
`str`, y tipos `struct` o `enum` no genéricos. Se rechazan clases, tipos genéricos y
tipos compuestos cuya identidad concreta no puede distinguirse en el valor de runtime.
Las alternativas repetidas se canonicalizan.

`?` propaga el valor de error original sin conversión cuando todas las alternativas del
origen están incluidas en el conjunto de destino. Así, un error `ParseError` puede
propagarse a `ParseError | IoError`, pero una función que declara solo `ParseError` no
puede propagar un resultado que también contenga `IoError`. No hay conversiones implícitas
entre errores.

`else err` asigna a `err` el conjunto estático del canal de error. Para un `match` que
produzca un valor se deben cubrir todas las alternativas con patrones de tipo, por
ejemplo `ParseError(problem) => ...` e `IoError(problem) => ...`. El patrón acepta un
binding o `_`; el valor completo del error se conserva y se comprueba por su identidad
de tipo runtime. Los nombres cualificados de módulos comprobados también son válidos en
la firma y en el patrón, por ejemplo `storage.ParseError(problem)`.

---

## 8. Memory Model: Deterministic Reference Counting + Copy-on-Write

> **Core Value Semantics Guarantee:** *"Copying a W value produces a semantically independent value. Internal storage may be shared through copy-on-write as an implementation optimization, but mutations must never be observable through another value alias."*

1. **Pure & Recursive Value Semantics:** To the programmer, collections (`list`, `dict`, `str`, `tuple`) and `struct` records behave as independent values, including when nested (`list[list[T]]`, `struct` containing `list[T]`, etc.). Mutating `b` or any nested component inside `b` never affects `a`:
   ```w
   let a = [[1], [2]]
   let mut b = a
   b[0].append(99)
   # a is still [[1], [2]]
   # b is [[1, 99], [2]]
   ```
2. **Deterministic Single-Threaded Reference Counting + CoW:**
   - Backing buffers use lightweight single-threaded reference counting (`int32_t refcount`) without atomic synchronization overhead.
   - Buffers are shared on assignment or parameter passing by incrementing `refcount`.
   - When a mutating operation occurs (`append`, `pop`, `clear`, indexed assignment, or field assignment on a `struct`), any buffer along the access path with `refcount > 1` is detached (`w_cow_detach`) before applying the mutation.
3. **Reference Types (`class`):**
   - Unlike `struct`, instances of `class` (`W_OBJECT`) have reference identity semantics: assigning `let b = a` shares the same underlying instance without CoW detachment on field mutation.
4. **Acyclic Value-Storage Subgraph:**
   - **The subgraph formed exclusively by value storage (`struct`, `enum`, `list`, `dict`, `tuple`) cannot contain cycles.**
   - Copy-on-Write by itself is an internal storage-sharing optimization and does not inherently guarantee acyclicity in arbitrary languages. Rather, pure W value storage is guaranteed to form a directed acyclic graph (DAG) because:
     1. W provides no raw pointers, addresses, or shared mutable references to value containers;
     2. Every composite literal construction and every mutating value operation (`xs[i] = v`, `xs.append(v)`, `s.field = v`) captures an independent semantic snapshot of `v` (detaching any shared value container along the target lvalue path before writing); and
     3. Consequently, no value container can ever be mutated to hold a direct or indirect value-storage path back to itself.
   - Note that a value (such as a `struct` or `list`) may contain a reference to a `class` instance without losing its own value semantics. If a `class` instance holds a field containing a `struct` that references that `class` instance (`Node(class) -> Wrapper(struct) -> Node(class)`), the cycle crosses a reference-type (`class`) identity boundary; the subgraph formed solely by value storage remains strictly acyclic.

---

## 9. Module System

Modules are imported using file path strings. The imported module automatically binds to a namespace derived from the file's base name:

```w
import "lexer.w"
import "parser.w"

fn compile(source: str) {
    let tokens = lexer.tokenize(source)
    let ast = parser.parse(tokens)
}
```
* No auxiliary keywords (`as`, `from`) are required.

---

## 10. AI & Tooling Contract

1. **Canonical Formatter (`w fmt`):**
   - Every valid W program has exactly one canonical formatted representation.
   - The formatter is idempotent: `fmt(fmt(source)) == fmt(source)`.
2. **Stable Diagnostic Codes & Structured JSON Diagnostics (`w check --json`):**
   - Every compiler and runtime error carries a stable `Wxxxx` diagnostic code categorized by phase:
     - **`W0xxx` — Lexical & Syntactic Diagnostics:**
       - `W0001`: Unexpected token or invalid character
       - `W0002`: Malformed numeric literal
       - `W0003`: Unterminated string literal
       - `W0004`: Invalid or unterminated string escape sequence
       - `W0005`: Invalid Unicode scalar escape sequence
       - `W0006`: Invalid syntax or missing delimiter
     - **`W1xxx` — Name Resolution, Scope & Module Diagnostics:**
       - `W1001`: Unknown identifier, symbol, or type
       - `W1002`: Duplicate declaration
       - `W1003`: Module resolution or circular import error
       - `W1004`: Invalid control-flow or lexical context (`break`/`continue`/`return`/`this`/`super`)
     - **`W2xxx` — Type System, Exhaustiveness & Error Channel Diagnostics:**
       - `W2001`: Type mismatch
       - `W2002`: Invalid assignment target
       - `W2003`: Non-exhaustive `match` expression
       - `W2004`: Invalid return type or missing `return` statement
       - `W2005`: Invalid call arity or non-callable target
       - `W2006`: Invalid optional (`?`) or fallible (`T ! E` / `else err`) propagation
       - `W2007`: Missing or invalid `struct` initialization field
       - `W2010`: Invalid dictionary key type
     - **`W3xxx` — Mutability, Ownership & OOP Encapsulation Diagnostics:**
       - `W3001`: Mutation of immutable value binding (`let` vs `let mut`)
       - `W3002`: Invalid member access/mutation or `private` visibility violation
       - `W3003`: Invalid class inheritance or unimplemented `interface` contract
       - `W3004`: Constructor safety violation (uninitialized fields or invalid `super` invocation)
     - **`W4xxx` — Runtime Execution Diagnostics:**
       - `W4001`: Division or modulo by zero
       - `W4002`: Index or key out of bounds
       - `W4003`: Runtime execution error
   - `w check --json <file.w>` outputs deterministic machine-readable JSON:
   ```json
   {
     "code": "W2001",
     "severity": "error",
     "stage": "type",
     "message": "Type mismatch: cannot assign value of type 'none' to variable 'name' of type 'str'",
     "file": "example.w",
     "line": 12,
     "column": 9,
     "span": {
       "file": "example.w",
       "line": 12,
       "column": 9
     }
   }
   ```
3. **Stable AST Representation (`w ast file.w --json`):**
   - Emits a standardized JSON AST containing `"w_ast_version": "0.1"` for reliable agentic code analysis.

---

## 11. Standard Prelude & Built-in Methods

### 11.1 Global Prelude Functions
| Function | Signature | Description |
| :--- | :--- | :--- |
| `print(...)` | `(...) -> unit` | Prints space-separated arguments followed by a newline |
| `len(x)` | `(str \| list[T] \| dict[K, V] \| tuple[...]) -> int` | Returns code-point count for `str` or element count for collections |
| `enumerate(xs)` | `(list[T]) -> list[tuple[int, T]]` | Returns `(index, element)` pairs for indexed iteration |
| `dict_items(d)` | `(dict[K, V]) -> list[tuple[K, V]]` | Returns `(key, value)` pairs for dictionary iteration |
| `int(x)` | `(int \| float \| str \| bool) -> int` | Converts value to 64-bit integer |
| `float(x)` | `(int \| float \| str \| bool) -> float` | Converts value to 64-bit float |
| `str(x)` | `(any) -> str` | Converts any runtime value to its canonical string representation |
| `ord(s)` | `(str) -> int` | Returns the Unicode code point of the first character in `s` |
| `chr(c)` | `(int) -> str` | Returns a single-code-point UTF-8 string for code point `c` |
| `slice(x, a, b)` | `(str \| list[T], int, int) -> str \| list[T]` | Returns code-point substring or sub-list in `[a, b)`. Preserves the container kind; out-of-range bounds are clamped and an empty result is returned when `b <= a` |
| `bytes(s)` | `(str) -> list[int]` | Returns raw UTF-8 unsigned bytes (`0..=255`) of `s` |
| `args()` | `() -> list[str]` | Returns command-line arguments passed to the program |
| `read_file(p)` | `(str) -> str ! IoError` | Reads a UTF-8 file from disk or returns `IoError` |
| `write_file(p, c)` | `(str, str) -> unit ! IoError` | Writes UTF-8 content `c` to path `p` or returns `IoError` |

### 11.2 Built-in Collection Methods
* **`list[T]`:**
  - `xs.append(item: T) -> unit` (mutating; triggers CoW detach if shared)
  - `xs.pop() -> T` (mutating; removes and returns last element)
  - `xs.clear() -> unit` (mutating; removes all elements)
* **`dict[K, V]`:**
  - `d.get(key: K) -> V?` (returns `Some(V)` if present, or `none`)
  - `d.keys() -> list[K]` (returns list of keys in insertion order)
  - `d.values() -> list[V]` (returns list of values in insertion order)

---

## 12. Self-Hosting Bootstrap Pipeline

W includes a self-hosting compiler written entirely in W (`selfhost/w1.w`), bootstrapped from the Python `W0` reference implementation and emitting portable C99:

```text
Step 1: W0 (Python Host Reference Implementation)
        └── Full Lexer, Parser, TypeChecker, Formatter, Tree-Walk Interpreter, and C99 Backend.
        └── Compiles `selfhost/w1.w` -> `compiler0.c` -> `w1_stage1` native binary.

Step 2: Stage-1 Self-Compilation (`w1_stage1`)
        └── `w1_stage1` (native binary) compiles `selfhost/w1.w` -> `compiler1.c` -> `w1_stage2`.

Step 3: Stage-2 Fixed-Point Verification (`w1_stage2`)
        └── `w1_stage2` compiles `selfhost/w1.w` -> `compiler2.c`.
        └── Fixed-point identity verified: SHA256(compiler0.c) == SHA256(compiler1.c) == SHA256(compiler2.c).
        └── `w1_stage2` natively compiles and passes all runtime conformance tests with zero Python.
```

---

## 13. Language Evolution Roadmap

Reconstructed from what the toolchain actually implements. Every entry below is
present in the tree and covered by the test suite unless marked otherwise.

* **`v0.1.0` — Core + Self-Host + OOP** ✅
* **`v0.1.1` — Harden & Oracle** ✅
* **`v0.1.2` — Diagnostics & Stress** ✅
* **`v0.1.3` — Ownership & Self-Host Parity** ✅ (deterministic cleanup scopes, W1 semantic and diagnostic parity on the core subset)
* **`v0.2.0` — Generics, ADTs & Option/Result unification** ✅ (monomorphization for structs, functions, enums and classes)
* **`v0.2.x` — Copy-on-write telemetry, weak class references, compilation sessions** ✅
* **`v0.3.0` — Typed HIR as the default backend, `LayoutGraph` finite-layout verification, declaration-order independence** ✅
* **`v0.3.0` (Phase E) — First-class functions, closures, modules, FFI, stdlib, LSP** ✅
* **`v0.4` — roadmap in progress.** Candidate work, each gated on the decisions in
  `docs/EXPANSION.md`:
  - F03 error composition (`T ! E1 | E2`) is implemented and measured in the four-engine
    release corpus;
  - mutable closure captures through shared cells, so a closure can mutate captured state;
  - concurrency or an explicit statement that the runtime stays single-threaded;
  - W1 support for expansion-suite features beyond the measured core corpus.

## Phase A error composition clarification

Parenthesized types group constructors: `(T?) ! E` is Result[Option[T],E], `(T ! E)?` is Option[Result[T,E]], and `(T ! E1) ! E2` is Result[Result[T,E1],E2]. Ungrouped `T ! E1 ! E2` associates to the right. Formatting preserves these distinctions.

Postfix `?` handles exactly the outer constructor. A second `?` on an optional payload is invalid inside a function whose outer return type is Result; use an explicit branch/recovery value instead. Error propagation requires the source error set to be a subset of the declared destination set; it never converts or flattens error payloads. A complete `Result[T, E1]` value can be assigned to or returned as `Result[T, E2]` only when `T` is identical and every `E1` alternative is present in `E2`; this preserves the tagged value without wrapping it in another `Ok`. Nested Result layers are never collapsed. Returning an inner Result as a success payload requires preserving its outer success layer. Bare values denote success, including when success and error types coincide.

Optional/Option and fallible/Result spellings share canonical type identity. Optional display is payload-transparent; explicit Some values follow the same display policy as sugar. Some(None) differs from None. Implicit conversions do not add/remove nullable depth; use explicit Some for nested optionality. Guarded match arms do not contribute unconditional coverage. Nested variant payload cases must be exhaustive.

## Weak class references (B03)

`Weak[C]` is an invariant value handle for a concrete class `C`. `weak(object)`
creates a non-owning reference; `upgrade(handle)` returns `C?` and acquires strong
ownership on success. Expired handles return None. Weak values cannot access
fields or methods directly and cannot be dictionary keys. Weak handles compare by
stable identity, even after expiration; copies preserve identity, while handles
for different objects remain distinct. Display is `weak(alive)` or `weak(expired)`.

Default non-optional weak class fields are independent empty expired handles;
optional weak fields default to None. Empty handles compare equal to their copies
and never upgrade. There is no implicit Weak[Derived]-to-Weak[Base] conversion.

Strong references still form unreclaimed cycles. Use weak back-references or
explicitly clear strong edges. The native control block outlives object destruction
until the last weak handle is released, and invalidates the object before field
cleanup. This runtime is single-threaded. W0/HIR enforce weak argument/type rules;
W1 supports the concrete operations with dynamic argument checks and its existing
limited static-checking profile. This does not establish W1 generic parity.

---

## 14. Compiler Engine Parity & Determinism Contracts (Phase D / ADR-009)

### 14.1 Four Execution Targets & Architectural Roles
The W compiler architecture formally defines four execution targets:
1. **W0 Interpreter (`runtime/Interpreter.py`):** Canonical tree-walking reference implementation over surface AST.
2. **W0 Typed HIR (`hir/HirCCodeGen.py`):** Default native compilation target (`w build`, `w emit-c`). Operates strictly on type-interned, arena-verified High-Level Intermediate Representation (`HirModule`).
3. **W0 AST C99 (`codegen/CCodeGen.py`):** Retained secondary native oracle for differential verification (`--backend=ast`).
4. **W1 Self-Hosted C99 (`selfhost/w1.w`):** Native Stage-2 compiler binary compiled from self-hosted W sources.

### 14.2 Bootstrap Fixed-Point vs. Feature Parity
W distinguishes between two distinct compiler guarantees:
* **Bootstrap Fixed-Point:** A 3-stage bootstrap self-compilation of `selfhost/w1.w` produces bit-identical C code:
  $$\text{SHA256}(c_0) == \text{SHA256}(c_1) == \text{SHA256}(c_2)$$
  This guarantees determinism and convergence of the self-hosted compiler subset.
* **Feature Parity:** Documented in `docs/ENGINE_PARITY_MATRIX.md` and measured rather than declared. The release profile passes all 130 fixtures on all four engines, with no unsupported cases. This is corpus evidence, not a claim of universal W0/W1 equivalence; see the feature breakdown and limits in the parity matrix.

### 14.3 Code Generation Determinism
Given identical source text and compiler flags:
1. Generated C99 source code is byte-for-byte identical across independent compiler invocations, varied temporary paths, and arbitrary `PYTHONHASHSEED` values.
2. Emitted declarations (types, functions, global constants) follow deterministic topological and symbol-ordered sequences.

### 14.4 Telemetry & Standard Stream Separation
Under the `--stats` flag:
1. Diagnostic telemetry reports phase timings under `timing_ms` (`lex`, `parse`, `check`, `total` for `run`/`build`; `hir` and `codegen` are added when a backend runs), peak RSS (`peak_rss_kb`), and the specialization counters reported by `MonomorphizationTelemetry.to_dict()` (`specialization_requests`, `deduplicated_hits`, `specialized_structs`, `specialized_enums`, `specialized_functions`).
2. Execution commands (`run --stats`, `build --stats`) write JSON telemetry strictly to `stderr`, leaving program `stdout` unpolluted for exact differential oracle verification. Check commands (`check --stats`) emit JSON telemetry to `stdout`.

