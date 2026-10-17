# W Language Architecture: Structured `TypeId` & `TypeInterner` Design

**Status:** Implemented & Canonical Specification (`C01-C05`, `D01-D06`)  
**Scope:** Static Type Representation, Interning, Subtyping, Invariance, and Generic Substitution

---

## 1. Motivation: Eliminating Stringly-Typed Type Representations

In `W v0.1.0`–`v0.1.1`:
- `W0` (`checker/WType.py`) represents types as heap-allocated Python objects (`ListType`, `DictType`, `ClassType`, etc.), while `Parser.py` represents generic custom type syntax as a string (`NamedType(name=f"{name}[{generic_arg}]")`).
- `W1` (`selfhost/w1.w`) tracks expression types using string tags (`"int"`, `"float"`, `"str"`, `"bool"`, `"list"`, `"class:Counter"`).

String-based or un-interned type trees break down as soon as **Generics (`v0.2`)** and **First-Class Function Types (`v0.3`)** are introduced:
1. **Structural Comparison Cost:** Comparing nested generic types such as `dict[str, list[Pair[int, User?]]]` by recursive tree traversal or formatted string comparison is error-prone and $O(\text{depth})$.
2. **Type Alias & Formatting Sensitivity:** Stringified type names are sensitive to whitespace, qualification, and evaluation order.
3. **Self-Hosting (`W1`) Representation:** Because `W1` is written in W itself, representing recursive type graphs cleanly in `W1` requires flat, index-addressed arena tables (`list[TypeEntry]`) indexed by integer `TypeId`s.

---

## 2. `TypeId` & `TypeInterner` Architecture

Every static type in the compiler is uniquely represented by a 32-bit integer handle (`TypeId`), managed by a central `TypeInterner`.

### 2.1 Reserved Primitive `TypeId` Constants
The interner pre-allocates fixed indices for built-in scalar and sentinel types at startup:

| `TypeId` | Canonical Type | Description |
| :--- | :--- | :--- |
| `0` | `<error>` | Poison/recovery type emitted after a type diagnostic to suppress cascading errors |
| `1` | `unit` | Absence of a meaningful value |
| `2` | `bool` | Boolean (`true` / `false`) |
| `3` | `int` | 64-bit signed two's complement integer |
| `4` | `float` | IEEE-754 `binary64` floating-point number |
| `5` | `str` | Immutable UTF-8 string (Unicode scalar indexed) |
| `6` | `none` | Singular bottom optional literal type |

### 2.2 Structured `TypeEntry` Taxonomy
Every interned `TypeId` maps to an immutable `TypeEntry` in the `TypeInterner` arena:

```text
enum TypeEntry {
    Error
    Primitive(PrimKind)                                 # unit, bool, int, float, str, none
    Optional(inner: TypeId)                             # T?
    Result(ok: TypeId, err: TypeId)                     # T ! E
    ErrorUnion(alternatives: sorted TypeIds)             # Error channel only: T ! E1 | E2
    List(elem: TypeId)                                  # list[T]
    Dict(key: TypeId, val: TypeId)                      # dict[K, V]
    Tuple(elems: list[TypeId])                          # tuple[T1, T2, ...]
    Function(params: list[TypeId], ret: TypeId)         # fn(T1, T2) -> R  (v0.3+)
    TypeParam(def_id: DefId, index: u32, name: str)     # Generic parameter T (v0.2+)
    NominalStruct(def_id: DefId, type_args: list[TypeId])
    NominalEnum(def_id: DefId, type_args: list[TypeId])
    NominalInterface(def_id: DefId, type_args: list[TypeId])
    NominalClass(def_id: DefId, type_args: list[TypeId])
}
```

### 2.3 Canonical Interning Guarantee ($O(1)$ Comparison vs. $O(\text{structure})$ Interning)
The `TypeInterner` maintains a hash-consing table mapping structural keys `(tag, child_type_ids...) -> TypeId`. We explicitly distinguish two operations:
1. **Type Equality Comparison (`T1 == T2`) is $O(1)$:** Once types are interned, comparing any two `TypeId` handles—regardless of nesting depth—is a single 32-bit integer comparison (`id1 == id2`).
2. **Type Construction / Interning (`intern(entry)`) is $O(\text{structure})$:** Interning a composite type syntax tree traverses its structure bottom-up, computing hashes over the immediate node tag and already-interned child `TypeId`s. Calling `interner.mk_list(TYPE_INT)` twice performs a hash table lookup and returns the **exact same `TypeId`**.
3. **Nominal Parameterization:** Nominal declarations (`struct`, `enum`, `interface`, `class`) are identified by their declaration `DefId` plus their interned `type_args: list[TypeId]`. Thus `Pair[int, str]` and `Pair[int, bool]` receive distinct `TypeId`s, while two occurrences of `Pair[int, str]` resolve to the identical `TypeId`.

---

## 3. Nominal Type Metadata Tables (`DefId`)

To allow recursive classes and mutually recursive structs without cyclic `TypeEntry` keys, nominal type declarations are stored in a separate `TypeDefTable` indexed by `DefId`:

```text
struct StructDef {
    def_id: DefId
    name: str
    type_params: list[TypeId]
    fields: list[(str, TypeId)]         # Field types may reference type_params
}

struct ClassDef {
    def_id: DefId
    name: str
    type_params: list[TypeId]
    superclass: TypeId?                 # Instantiated superclass NominalClass TypeId
    interfaces: list[TypeId]            # Instantiated NominalInterface TypeIds
    fields: list[ClassFieldDef]
    methods: list[ClassMethodDef]
    init_sig: TypeId?
}
```

---

## 4. Generic Type Substitution (`substitute`)

When checking a generic field access, method call, or function instantiation (e.g., `box: Box[int]`), the type checker substitutes `TypeParam`s with concrete `TypeId` arguments via a purely functional interner pass:

```python
def substitute(interner: TypeInterner, target: TypeId, subst_map: Dict[TypeId, TypeId]) -> TypeId:
    if target in subst_map:
        return subst_map[target]
    entry = interner.get(target)
    # Recursively substitute child TypeIds and re-intern
```

Because `TypeEntry` graphs are finite DAGs (nominal recursion is broken through `DefId`), `substitute` terminates deterministically in time proportional to the depth of the type annotation.

---

## 5. Subtyping, Assignability & Variance Rules

The assignability relation `is_assignable(src: TypeId, dst: TypeId) -> bool` (`src <: dst`) is formally defined by five rules:

### 5.1 Identity & Error Recovery
1. If `src == dst`, then `src <: dst` ($O(1)$ integer check).
2. If `src == TYPE_ERROR` or `dst == TYPE_ERROR`, return `true` to prevent cascading diagnostics after an initial error.

### 5.2 Optional (`T?`) & Result (`T ! E`) Promotions
1. `none <: T?` for any `T`.
2. `S <: T?` if `S <: T`.
3. `S? <: T?` if `S <: T`.
4. `T <: (T ! E)` (implicit `Ok` wrapping) and `E <: (T ! E)` (implicit `Err` wrapping), provided `T != E`.

### 5.3 Uniones cerradas del canal de error

Una unión de error contiene al menos dos tipos distintos y solo puede aparecer como el
segundo componente de `Result<T, E>`. `ErrorUnionType` se interna con alternativas
ordenadas y sin duplicados. Una alternativa puede ampliarse a una unión que la contenga;
una unión origen puede propagarse únicamente si cada uno de sus miembros pertenece al
conjunto destino. No hay conversiones de payload.

Para mantener identidad runtime verificable y evitar conjuntos ambiguos, las alternativas
admitidas son escalares (`int`, `float`, `bool`, `str`), `struct` no genéricos y `enum`
no genéricos. Clases, genéricos y tipos compuestos quedan fuera de este contrato.

### 5.4 Nominal Class & Interface Subtyping
1. **Single Inheritance (`extends`):** `NominalClass(sub_def, sub_args) <: NominalClass(sup_def, sup_args)` if and only if walking the `superclass` chain from `sub` (with generic argument substitution) reaches `NominalClass(sup_def, sup_args)`.
2. **Interface Satisfaction (`implements`):** `NominalClass(cls_def, cls_args) <: NominalInterface(intf_def, intf_args)` if `cls` or any of its superclasses declares `implements` for `NominalInterface(intf_def, intf_args)`.

### 5.4 Strict Invariance of Generic Containers (`list`, `dict`, `struct`, `class`)
> **Design Decision:** All parameterized container and user-defined generic types (`list[T]`, `dict[K, V]`, `Struct[T]`, `Class[T]`) are **invariant** in their type parameters.

Concretely, even if `Dog <: Animal`:
- `list[Dog]` is **NOT** a subtype of `list[Animal]` (`list[Dog] </: list[Animal]`).
- `Box[Dog]` is **NOT** a subtype of `Box[Animal]`.

**Why Invariance is Required:**
1. **Soundness of Reference & Mutating Operations:** For reference classes (`Class[T]`), covariance would allow inserting a `Cat` into a `RefCell[Dog]` viewed as a `RefCell[Animal]`, breaking type soundness without runtime type tags.
2. **Predictable CoW & Monomorphization Layout:** In `v0.2`, generic types are compiled via monomorphization. Treating `list[Dog]` and `list[Animal]` as invariant ensures every container has an exact, unambiguous static element type.
3. **Explicit List Construction:** Note that a list literal `[Dog(), Cat()]` where both `Dog <: Animal` and `Cat <: Animal` still infers `list[Animal]` at construction time via least-upper-bound (`LUB`) superclass inference on the literal elements, or via explicit annotation `let xs: list[Animal] = [Dog(), Cat()]` (where each element expression is checked against `Animal`).

### 5.5 Dictionary Key Validity (`is_valid_dict_key`)
For `Dict(key: TypeId, val: TypeId)`:
- `key` must be one of `int`, `str`, `bool`, or `NominalEnum(def_id, [])` (or a `tuple` composed recursively of valid key types once tuple hashing is enabled).
- `float` (and any composite containing `float`), `list`, `dict`, `struct`, and `class` are statically rejected with **`W2010` (`INVALID_DICT_KEY_TYPE`)**. Excluding `float` is an explicit language predictability design choice to avoid IEEE-754 `NaN` key-lookup anomalies (`NaN != NaN`) and `-0.0` vs. `+0.0` hashing ambiguities.

---

## 6. `TypeCapabilities` Matrix (Ownership, CoW & Generic Contracts)

To bridge static types with deterministic Reference Counting (`v0.1.3`) and future monomorphization (`v0.2`), every `TypeId` exposes a precomputed `TypeCapabilities` descriptor:

```text
struct TypeCapabilities {
    needs_retain: bool       # Requires RC increment when duplicating a binding/reference
    needs_release: bool      # Requires RC decrement & potential deallocation on scope exit
    is_value: bool           # Exhibits independent value semantics (scalars, str, list, dict, tuple, struct, enum)
    is_reference: bool       # Exhibits shared identity semantics (class, interface)
    is_copyable: bool        # Can be assigned/passed by value (all W types are copyable; collections/structs use CoW)
    has_identity: bool       # Supports shared mutable identity across aliases (true only for class/interface)
    is_comparable: bool      # Supports == and != operators
    is_valid_dict_key: bool  # Permitted as K in dict[K, V] (checked by W2010)
}
```

### Crucial Orthogonality: `is_value` vs. `needs_release`
Value semantics (`is_value`) and heap Reference Counting (`needs_retain` / `needs_release`) are **orthogonal axes**:

| Type Example | `is_value` | `is_reference` | `has_identity` | `needs_retain` / `needs_release` | `is_valid_dict_key` | Runtime Representation |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `int`, `bool`, `enum`, `unit` | `true` | `false` | `false` | `false` | `true` (`unit`: `false`) | Immediate unboxed scalar in `WVal` |
| `float` | `true` | `false` | `false` | `false` | **`false` (`W2010`)** | Immediate unboxed `double` in `WVal` |
| `str` | `true` | `false` | `false` | `true` | `true` | Immutable UTF-8 buffer |
| `list[T]`, `dict[K, V]` | `true` | `false` | `false` | `true` | `false` (`W2010`) | Refcounted CoW buffer (`WListBuf*`, `WDictBuf*`) |
| `tuple[T1, ...]` | `true` | `false` | `false` | `true` | `false` (in `v0.1`) | Refcounted buffer (`WTupleBuf*`) |
| `Point` (`struct`) | `true` | `false` | `false` | `true` | `false` (`W2010`) | Refcounted CoW buffer (`WStructBuf*`) |
| `User` (`class` / `interface`) | `false` | `true` | `true` | `true` | `false` (`W2010`) | Refcounted identity object (`WStructBuf*` with `W_OBJECT`) |
| `T?` / `T ! E` | Inherits | Inherits | Inherits | `true` (`WBoxBuf*`) | `false` (`W2010`) | Tagged `WVal` or refcounted `WBoxBuf*` (`W_OK` / `W_ERR`) |

---

## 6. Whole-Program Compilation & Type Invariance (Phase C & D Consolidation)

Across compilation sessions, container invariance, and declaration-order checks:
1. **Whole-Program TypeInterner Arena:** A single `CompilationSession` manages one shared `TypeInterner` across all imported source files and modules. Type comparison is strictly $O(1)$ by integer `TypeId`.
2. **Container Invariance:** Generic containers (`list[T]`, `dict[K, V]`, and user `struct` / `enum` instances) are strictly invariant. A `list[Dog]` cannot be assigned to or passed where a `list[Animal]` is expected, preventing silent heap type corruption.
3. **Inference Bounds:** Contextless empty collection inference (`let d = {}`) is statically rejected (`[W2001]`). Generic parameter inference enforces structural consistency across call arguments.
4. **Order Independence:** Top-level declarations are collected in a multi-pass shell resolution before type checking, ensuring program validity is completely invariant to declaration ordering.


