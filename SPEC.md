# W Language Specification v0.1

> **Status:** Frozen Specification (v0.1 — Implemented & Self-Hosted)  
> **Targets:** `W0` (Python Reference Frontend, Interpreter & C99 Transpiler) & `W1` (`selfhost/w1.w` Self-Hosting Native C99 Compiler)  
> **Core Thesis:** *W is a small, statically typed programming language optimized for semantic density, deterministic tooling, and reliable code generation by humans and AI systems.*

---

## 1. The Four Foundational Pillars

1. **Compact:** Maximum semantic intention expressed per token. No unnecessary syntactic ceremony.
2. **Deterministic:** Canonical syntax with zero whitespace ambiguity, zero hidden mutations, and zero implicit nullability.
3. **Statically Typed:** Strict type safety with full local inference and mandatory explicit types on function boundaries.
4. **Self-Hostable:** Minimalist micro-kernel designed to compile its own compiler to standard C without heavy external dependencies.

---

## 2. Lexical Inventory (Exactly 22 Keywords)

The language defines an immutable set of **22 keywords**:

```text
DECLARATIONS (6):
fn        let       mut       struct    enum      import

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
Identifiers must start with an ASCII letter (`a-z`, `A-Z`) or underscore `_`, followed by letters, digits, or underscores. Identifiers cannot match any of the 22 reserved keywords.

### 3.2 Literals
* **Integers (`int`):** 64-bit signed integers. Supports optional `_` digit separators:
  `0`, `42`, `-10`, `1_000_000`.
* **Floats (`float`):** IEEE 754 64-bit floating point numbers. Must include digits both before and after the decimal point:
  `3.14`, `-0.5`, `100.0`. Forms such as `.5` or `1.` are invalid.
* **Booleans (`bool`):** `true` and `false`.
* **None (`none`):** The singular value of an empty optional.

### 3.3 Strings (`str`)
* **Encoding:** Stored as UTF-8 in memory.
* **Indexing Semantics:** `s[i]` indexes **Unicode Scalar Values / Code Points**, returning a single code-point string (`str`).
  ```w
  let s = "José"
  s[3]    # returns "é"
  len(s)  # returns 4
  ```
* **Byte Access:** Low-level byte access is explicitly provided via `bytes(s) -> list[int]`.
* **Escape Sequences:** `\n`, `\r`, `\t`, `\\`, `\"`, `\0`, `\u{HHHH}` (1 to 6 hex digits).

### 3.4 Comments and Delimiters
* **Comments:** Only line comments starting with `#`. Doc-comments start with `##`.
* **Delimiters:** Braces `{}` are mandatory for blocks (`if`, `for`, `while`, `fn`, `match`, `struct`). Semicolons are not used.

---

## 4. Type System & Nullability

### 4.1 Primitive & Built-in Types
* `int`: 64-bit signed integer.
* `float`: 64-bit floating point.
* `bool`: Boolean truth value.
* `str`: Immutable UTF-8 text with code-point indexing.
* `unit`: Type indicating the absence of a meaningful value for functions that return nothing.

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

### 4.3 Composite Collections
* `list[T]`: Dynamically sized contiguous homogeneous array (`[1, 2, 3]`).
* `dict[K, V]`: Associative hash table (`{"key": 42}`).
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

### 4.5 Product Types (`struct`) with Mandatory Named Initialization
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

---

## 5. Expressions, Operators & Precedence

Evaluation follows an explicit 12-level precedence hierarchy:

| Level | Operator | Description | Associativity |
| :---: | :--- | :--- | :---: |
| **1** | `()` | Grouping, function calls | Left |
| **2** | `.` `[]` | Member access, indexing | Left |
| **3** | `-` `not` | Unary negation, logical NOT | Right |
| **4** | `*` `/` `%` | Multiplicative | Left |
| **5** | `+` `-` | Additive, string concatenation | Left |
| **6** | `..` `..=` | Exclusive range, inclusive range | None |
| **7** | `<` `<=` `>` `>=` | Relational comparisons | Left |
| **8** | `==` `!=` | Equality comparisons | Left |
| **9** | `and` | Short-circuit logical AND | Left |
| **10** | `or` | Short-circuit logical OR | Left |
| **11** | `??` | Null-coalescing (`a ?? fallback`) | Right |
| **12** | `=` | Assignment | Right |

### 5.1 The Dual Nature of `?`
1. **Type Level (`T?`):** Defines an optional type.
2. **Expression Level (`expr?`):** Postfix unwrapping and early return operator.
   - For `T?`: If value is `none`, immediately returns `none` from the enclosing function (caller must return an optional `U?`).
   - For `T ! E`: If value is an error, immediately returns the error from the enclosing function (caller must return a fallible `U ! E`).

---

## 6. Control Flow & Pattern Matching

### 6.1 Variables: Immutability by Default
* `let x = 42`: Immutable binding with local type inference.
* `let mut count = 0`: Mutable binding.
* Function parameters are strictly typed and immutable within the body.

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

---

## 8. Memory Model: ARC + Copy-on-Write (Value Semantics)

1. **Pure Value Semantics:** To the programmer, collections (`list`, `dict`, `str`, `struct`) behave as independent values. Mutating `a` never silently affects `b`.
   ```w
   let a = [1, 2, 3]
   let mut b = a
   b.append(4)
   # a is still [1, 2, 3]
   # b is [1, 2, 3, 4]
   ```
2. **Under-the-Hood ARC + CoW:**
   - Buffers are shared while read-only, incrementing a reference count.
   - When a mutating operation occurs (`append`, `set`), if the buffer's reference count > 1, the runtime clones the buffer before applying changes.
3. **No Reference Cycles:** Because all structures have value semantics, circular references cannot be created through assignments or mutations.

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
2. **Structured JSON Diagnostics (`w check --json`):**
   - Compiler errors and warnings output machine-readable JSON:
   ```json
   {
     "code": "E023",
     "file": "src/parser.w",
     "line": 42,
     "column": 17,
     "message": "Non-exhaustive match on enum TokenKind. Missing: Eof",
     "expected": ["TokenKind.Eof"],
     "found": null
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
| `slice(x, a, b)` | `(str \| list[T], int, int) -> str \| list[T]` | Returns code-point substring or sub-list in `[a, b)` |
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

```text
Step 1: W0 (Python Host Reference Implementation)
        └── Full Lexer, Parser, TypeChecker, Formatter, Tree-Walk Interpreter, and C99 Backend.
        └── Compiles `selfhost/w1.w` -> `compiler0.c` -> `w1_stage1` native binary.

Step 2: Stage-1 Self-Compilation (`w1_stage1`)
        └── `w1_stage1` (native binary) compiles `selfhost/w1.w` -> `compiler1.c` -> `w1_stage2`.

Step 3: Stage-2 Fixed-Point Verification (`w1_stage2`)
        └── `w1_stage2` compiles `selfhost/w1.w` -> `compiler2.c`.
        └── Fixed-point identity verified: SHA256(compiler0.c) == SHA256(compiler1.c) == SHA256(compiler2.c).
        └── `w1_stage2` natively compiles and passes all 20/20 runtime conformance tests with zero Python.
```
