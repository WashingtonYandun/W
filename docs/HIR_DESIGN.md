# W Language Architecture: Typed High-Level IR (`HIR`) Design

**Status:** Approved Design Specification (`v0.1.2` Architecture Track — Target Implementation: `v0.2` / `v0.3`)  
**Scope:** Compiler Middle-End (`AST → Name Resolution → Type Checking → Typed HIR → Backends`)

---

## 1. Problem Statement & Architectural Motivation

In `W v0.1.0` and `v0.1.1`, both the reference toolchain (`W0` in Python) and the self-hosted compiler (`W1` in `selfhost/w1.w`) operate directly on the surface Abstract Syntax Tree (`AST`):

```text
Source (.w) ──► Lexer ──► Surface AST ──► TypeChecker ──► Interpreter / C99 CodeGen
```

While direct AST traversal was sufficient to bootstrap `W1` and validate core semantics, it creates four structural risks as the language evolves toward **Generics (`v0.2`)**, **Function Types (`v0.3`)**, and **Closures (`v0.4`)**:

1. **Repeated Semantic Disambiguation in Backends:**
   Surface syntax contains overloaded constructs that only become unambiguous after type checking:
   - `User("Ada")` (constructor call) vs `compute("Ada")` (function call);
   - `State.Active` (enum variant) vs `user.name` (struct field) vs `account.balance` (class field) vs `math.sin` (module member);
   - `obj.run()` via concrete class hierarchy vs `intf.run()` via dynamic interface dispatch;
   - `+` on `int` (wrapping 64-bit two's complement), `float` (IEEE-754 `binary64`), or `str` (UTF-8 concatenation).
2. **Evaluation-Order & Temporary Lowering Duplication:**
   In `v0.1.1`, enforcing strict left-to-right (`L→R`) evaluation order across `gcc` (x86_64) and `clang` (ARM64) required manually binding call expressions to statement-level temporaries (`WVal _tN = ...;`) in both `codegen/CCodeGen.py` and `selfhost/w1.w`.
3. **Copy-on-Write (CoW) Path Semantics:**
   Deeply nested value mutations (`matrix[0].append(99)` or `grid.rows[1][0] = 5`) must detach every shared value container (`list`, `dict`, `struct`) along the lvalue access path until reaching a `class` reference boundary. Encoding this rule in HIR eliminates the risk of divergence between the interpreter and C99 codegen.
4. **Monomorphization Target for Generics (`v0.2`):**
   Monomorphizing generic `struct`, `enum`, `class`, and `fn` templates directly over untyped surface AST nodes is brittle because identifier scopes and method resolutions are not yet bound to canonical `SymbolId` and `TypeId` handles.

---

## 2. Target Compiler Pipeline

```mermaid
flowchart TD
    A["Source (.w)"] --> B["Lexer (Token Stream)"]
    B --> C["Parser (Surface AST)"]
    C --> D["Pass 1: Declaration & Type Collector"]
    D --> E["Pass 2: Name Resolution & Type Checker"]
    E --> F["HIR Lowering (Typed HIR)"]
    F --> G["Monomorphization Pass (v0.2+)"]
    G --> H["L→R Temporary & CoW Path Lowering"]
    H --> I["W0 HIR Interpreter"]
    H --> J["C99 Backend (W0 & W1 Self-Hosted)"]
```

### Core Invariants of Typed HIR
1. **Total Type Decoration:** Every `HirExpr`, `HirPattern`, and `HirLocal` carries a non-null, interned `TypeId` and source `Span`.
2. **Zero Unresolved Names:** Variable, parameter, function, and type references use canonical integer identifiers (`SymbolId`, `TypeId`, `FieldIndex`, `MethodSlot`) rather than raw strings.
3. **Desugared Surface Syntax:**
   - Both `User("Ada")` and legacy `new User("Ada")` lower to `HirConstructObject(class_type_id, args)`.
   - Omitted `-> unit` return annotations and bare `return` statements are normalized to explicit `Unit` values.
   - `expr?` (postfix propagation) and `expr else err { ... }` lower to explicit control-flow branching over `Optional` / `Result` payloads.
4. **Explicit Evaluation Order & Value Detachment:**
   - Call arguments and binary operands with side effects are hoisted into ordered `HirStmt::BindTemp` statements before the consuming operation.
   - Mutating lvalue paths are represented explicitly as `HirCowPath` chains.

---

## 3. Core HIR Data Model

### 3.1 Identifiers & Metadata
```text
struct Span {
    file_id: u32
    line: u32
    col: u32
}

type SymbolId = u32   # Unique per lexical binding (local, param, global fn, module)
type TypeId   = u32   # Interned canonical type index (see TYPE_SYSTEM_DESIGN.md)
```

### 3.2 Top-Level Module & Declarations (`HirModule`)
```text
struct HirModule {
    file_path: str
    types: list[HirTypeDecl]       # Structs, Enums, Interfaces, Classes
    functions: list[HirFnDecl]     # Top-level functions and lowered methods
}

enum HirTypeDecl {
    Struct(TypeId, fields: list[HirFieldDef])
    Enum(TypeId, variants: list[str])
    Interface(TypeId, methods: list[HirMethodSig])
    Class(
        type_id: TypeId,
        superclass: TypeId?,
        interfaces: list[TypeId],
        fields: list[HirFieldDef],
        methods: list[HirMethodImpl]
    )
}

struct HirFnDecl {
    symbol_id: SymbolId
    name: str
    type_params: list[TypeId]      # Empty after v0.2 monomorphization
    params: list[HirParam]
    return_type: TypeId
    body: HirBlock
    span: Span
}
```

### 3.3 Statements (`HirStmt`)
| HIR Statement Node | Purpose |
| :--- | :--- |
| `HirLet(symbol_id, type_id, is_mut, init_expr, span)` | Local variable declaration with resolved `SymbolId` and `TypeId` |
| `HirBindTemp(temp_id, type_id, init_expr, span)` | Compiler-generated temporary enforcing strict `L→R` evaluation |
| `HirAssign(lvalue_path, value_expr, span)` | Assignment to a mutable local, index, struct field, or object field |
| `HirWhile(cond_expr, body_block, span)` | Loop with boolean-verified condition |
| `HirForList(elem_bindings, list_expr, body_block, span)` | Desugared list iteration over a cloned/retained `ListType` value |
| `HirReturn(value_expr, span)` | Explicit function/method return |
| `HirBreak(span)` / `HirContinue(span)` | Loop control transfer (statically verified `loop_depth > 0`) |
| `HirExprStmt(expr, span)` | Expression evaluated for side effects |

### 3.4 Expressions (`HirExpr`)
Every `HirExpr` contains `{ kind: HirExprKind, type_id: TypeId, span: Span }`:

| `HirExprKind` Variant | Lowered Semantics |
| :--- | :--- |
| `ConstInt(i64)` / `ConstFloat(f64)` / `ConstBool(bool)` / `ConstStr(str)` / `ConstNone` / `ConstUnit` | Typed scalar constants |
| `LocalRef(SymbolId)` / `ThisRef(TypeId)` | Direct reference to a local variable, parameter, or method receiver |
| `UnaryOp(UnaryKind, operand)` | `NegInt` (wrapping), `NegFloat`, `NotBool` |
| `BinaryOp(BinaryKind, left, right)` | Type-specialized operator (`AddInt`, `AddFloat`, `ConcatStr`, `DivIntTrunc`, `ModIntTrunc`, `EqVal`, `EqRef`, etc.) |
| `ConstructStruct(TypeId, fields: list[(FieldIdx, HirExpr)])` | Value-type `struct` initialization in canonical field declaration order |
| `ConstructEnum(TypeId, variant_idx: u32)` | Enum variant construction |
| `ConstructObject(TypeId, args: list[HirExpr])` | Unified heap-allocated `class` construction + `init` invocation (replaces both `Class(...)` and `new Class(...)`) |
| `ConstructList(elem_type: TypeId, elems: list[HirExpr])` | Homogeneous list literal construction |
| `ConstructDict(key_type: TypeId, val_type: TypeId, entries)` | Homogeneous dictionary literal construction (`key_type` verified non-float) |
| `ConstructTuple(elem_types: list[TypeId], elems: list[HirExpr])` | Tuple value construction |
| `DirectCall(fn_symbol: SymbolId, type_args: list[TypeId], args: list[HirExpr])` | Static function call |
| `BuiltinCall(BuiltinId, args: list[HirExpr])` | Typed runtime intrinsic (`Print`, `LenStr`, `LenList`, `LenDict`, `SliceStr`, `Ord`, `Chr`, `Bytes`, `ReadFile`, `WriteFile`) |
| `MethodCall(dispatch: DispatchKind, receiver: HirLValueOrExpr, method_name: str, args: list[HirExpr])` | Dispatched method call (`ListAppend`, `ListPop`, `ListClear`, `DictGet`, `ClassMethod`, `SuperMethod`, `InterfaceMethod`) |
| `FieldRead(kind: FieldAccessKind, object: HirExpr, field_name: str)` | Disambiguated `StructField` vs `ClassField` read |
| `IndexRead(kind: IndexKind, object: HirExpr, index: HirExpr)` | Disambiguated `ListIndex`, `StrScalarIndex`, or `DictLookup` (returns `V?`) |
| `TryPropagate(kind: TryKind, operand: HirExpr)` | Explicit early-return unwrap for `T?` (`TryOptional`) or `T ! E` (`TryResult`) |
| `Coalesce(opt_expr: HirExpr, fallback_expr: HirExpr)` | Short-circuiting optional unwrap (`??`) |
| `ElseHandle(operand: HirExpr, err_symbol: SymbolId?, handler: HirBlock)` | In-place `else err { ... }` recovery |
| `If(cond: HirExpr, then_block: HirBlock, elifs, else_block: HirBlock?)` | Typed conditional expression/statement |
| `Match(subject: HirExpr, arms: list[HirMatchArm])` | Exhaustiveness-checked pattern match |

---

## 4. Explicit Copy-on-Write (`HirCowPath`) Lowering

One of W's defining semantic guarantees is that **mutating a nested value container never mutates aliased value bindings**, whereas mutating a field through a `class` instance mutates the shared reference object.

In Typed HIR, any mutating target (`a[i][j] = x`, `b.rows[0].append(1)`, `s.inner.count = 2`) is lowered to a structured `HirLValuePath`:

```text
struct HirLValuePath {
    root: HirLValueRoot              # MutableLocal(SymbolId) | ClassObjectExpr(HirExpr)
    steps: list[HirPathStep]         # Ordered outer-to-inner projection steps
}

enum HirPathStep {
    StructField(field_name: str, struct_type: TypeId)   # Detach struct if refcount > 1
    ListIndex(index_expr: HirExpr, elem_type: TypeId)   # Detach list if refcount > 1
    DictKey(key_expr: HirExpr, val_type: TypeId)        # Detach dict if refcount > 1
    ClassField(field_name: str, class_type: TypeId)     # Reference boundary: NO CoW detach
}
```

### Lowering Rule at Class Reference Boundaries
When the TypeChecker / HIR Builder constructs an lvalue path from an expression $E$:
1. It walks $E$ from innermost projection to outermost base.
2. If it encounters a `ClassField` projection on a `ClassType` receiver, **that class instance becomes the `ClassObjectExpr` root** of the mutable path (no `let mut` required on the variable holding the class reference, and no CoW detachment on the class instance itself).
3. Any `StructField`, `ListIndex`, or `DictKey` steps *inside* that class field still perform CoW detachment on the value containers stored inside the object.
4. If no `ClassType` boundary is crossed, the root must be a `MutableLocal(SymbolId)` declared with `let mut` (otherwise `W3001` is emitted), and every `StructField` / `ListIndex` / `DictKey` step detaches its container when `refcount > 1`.

---

## 5. Evaluation Order Lowering (`L→R` Sequence Points)

Per `SPEC.md` Section 5.4, W guarantees strict left-to-right evaluation of all sub-expressions. Because C99 leaves function argument and binary operand evaluation order unspecified between sequence points, HIR lowering normalizes compound expressions into statement-level temporaries before C99 emission:

### Example
Surface W code:
```w
let y = add( bump(x), bump(x) * 2 )
```
Lowered HIR block statements:
```text
HirBindTemp(_t1: int = DirectCall(bump, [LocalRef(x)]))
HirBindTemp(_t2: int = DirectCall(bump, [LocalRef(x)]))
HirBindTemp(_t3: int = BinaryOp(MulInt, TempRef(_t2), ConstInt(2)))
HirBindTemp(_t4: int = DirectCall(add, [TempRef(_t1), TempRef(_t3)]))
HirLet(y: int = TempRef(_t4))
```
Both `gcc` and `clang` are forced by `;`-terminated C99 variable declarations to execute `_t1`, `_t2`, `_t3`, and `_t4` in exact deterministic sequence.

---

## 6. Migration Roadmap (`v0.2` – `v0.3`)

To preserve the 100% conformance suite and 3-stage self-hosting fixed-point (`W0 -> W1 Stage 1 -> W1 Stage 2`), HIR adoption is staged incrementally:

1. **Stage 1 (`v0.2` — Generics & Type Interner):**
   - Introduce `TypeInterner` and `TypeId` (`docs/TYPE_SYSTEM_DESIGN.md`).
   - Annotate AST/HIR nodes with resolved `TypeId`s during `TypeChecker`.
   - Perform Generic Monomorphization (`docs/ADR-002-generics-monomorphization.md`) over typed declarations before C99 emission.
2. **Stage 2 (`v0.3` — Full Typed HIR Pipeline):**
   - Introduce the `hir/` package in `W0` (`hir/HirNodes.py`, `hir/HirBuilder.py`).
   - Switch `Interpreter` and `CCodeGen` to consume `HirModule` instead of raw `Program` AST.
   - Mirror the flattened HIR node tables in `selfhost/w1.w` so `W1` benefits from the same unified front-end/middle-end architecture.
