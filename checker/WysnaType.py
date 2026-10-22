from typing import Dict, List, Optional, Any

class WysnaType:
    """Base class for semantic types in Wysna."""
    def __eq__(self, other: Any) -> bool:
        raise NotImplementedError

    def __hash__(self) -> int:
        return hash(str(self))

    def __str__(self) -> str:
        raise NotImplementedError

    def __repr__(self) -> str:
        return self.__str__()


class PrimitiveType(WysnaType):
    def __init__(self, name: str):
        self.name = name

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, PrimitiveType) and self.name == other.name

    def __str__(self) -> str:
        return self.name


IntType = PrimitiveType("int")
FloatType = PrimitiveType("float")
BoolType = PrimitiveType("bool")
StrType = PrimitiveType("str")
UnitType = PrimitiveType("unit")
NoneType = PrimitiveType("none")
OpaqueType = PrimitiveType("opaque")


class OptionalType(WysnaType):
    def __init__(self, inner: WysnaType):
        self.inner = inner

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, OptionalType):
            return self.inner == other.inner
        if isinstance(other, EnumType) and getattr(other, "template_name", None) == "Option" and getattr(other, "type_args", None) and len(other.type_args) == 1:
            return self.inner == other.type_args[0]
        return False

    def __str__(self) -> str:
        return f"{self.inner}?"


class WeakType(WysnaType):
    def __init__(self, target: WysnaType):
        self.target = target

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, WeakType) and self.target == other.target

    def __str__(self) -> str:
        return f"Weak[{self.target}]"


class ListType(WysnaType):
    def __init__(self, element: WysnaType):
        self.element = element

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, ListType) and self.element == other.element

    def __str__(self) -> str:
        return f"list[{self.element}]"


class DictType(WysnaType):
    def __init__(self, key: WysnaType, value: WysnaType):
        self.key = key
        self.value = value

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, DictType) and self.key == other.key and self.value == other.value

    def __str__(self) -> str:
        return f"dict[{self.key}, {self.value}]"


class TupleType(WysnaType):
    def __init__(self, elements: List[WysnaType]):
        self.elements = elements

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, TupleType) and self.elements == other.elements

    def __str__(self) -> str:
        elems = ", ".join(str(e) for e in self.elements)
        return f"tuple[{elems}]"


class StructType(WysnaType):
    def __init__(self, name: str, fields: Dict[str, WysnaType]):
        self.name = name
        self.fields = fields

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, StructType) and self.name == other.name

    def __str__(self) -> str:
        return self.name


class EnumType(WysnaType):
    def __init__(self, name: str, variants: List[str], variant_payloads: Optional[Dict[str, List[WysnaType]]] = None):
        self.name = name
        self.variants = variants
        self.variant_payloads: Dict[str, List[WysnaType]] = variant_payloads if variant_payloads is not None else {v: [] for v in variants}
        self.template_name: Optional[str] = None
        self.type_args: Optional[List[WysnaType]] = None

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, EnumType):
            return self.name == other.name
        if self.template_name == "Option" and self.type_args and len(self.type_args) == 1 and isinstance(other, OptionalType):
            return self.type_args[0] == other.inner
        if self.template_name == "Result" and self.type_args and len(self.type_args) == 2 and isinstance(other, ResultType):
            return self.type_args[0] == other.ok and self.type_args[1] == other.err
        return False

    def __str__(self) -> str:
        return self.name


class ResultType(WysnaType):
    def __init__(self, ok: WysnaType, err: WysnaType):
        self.ok = ok
        self.err = err

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, ResultType):
            return self.ok == other.ok and self.err == other.err
        if isinstance(other, EnumType) and getattr(other, "template_name", None) == "Result" and getattr(other, "type_args", None) and len(other.type_args) == 2:
            return self.ok == other.type_args[0] and self.err == other.type_args[1]
        return False

    def __str__(self) -> str:
        return f"{self.ok} ! {self.err}"


class ErrorUnionType(WysnaType):
    """A statically known, closed set of alternative error payload types."""
    def __init__(self, alternatives: List[WysnaType]):
        unique: List[WysnaType] = []
        for alternative in alternatives:
            if not any(alternative == existing for existing in unique):
                unique.append(alternative)
        self.alternatives = tuple(sorted(unique, key=str))

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, ErrorUnionType) and self.alternatives == other.alternatives

    def __str__(self) -> str:
        return " | ".join(str(alternative) for alternative in self.alternatives)


def is_error_channel_assignable(source: WysnaType, target: WysnaType) -> bool:
    """Check closed error-set inclusion without applying value constructors.

    In particular, a scalar error must not become compatible with a Result error
    channel merely because Result normally accepts its success payload.
    """
    source_alternatives = source.alternatives if isinstance(source, ErrorUnionType) else (source,)
    target_alternatives = target.alternatives if isinstance(target, ErrorUnionType) else (target,)
    return all(any(source_member == target_member for target_member in target_alternatives)
               for source_member in source_alternatives)


class FunctionType(WysnaType):
    def __init__(self, params: List[WysnaType], ret: WysnaType, is_mutating: bool = False):
        self.params = params
        self.ret = ret
        self.is_mutating = is_mutating

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, FunctionType) and self.params == other.params and self.ret == other.ret

    def __str__(self) -> str:
        params_str = ", ".join(str(p) for p in self.params)
        return f"fn({params_str}) -> {self.ret}"


class InterfaceType(WysnaType):
    def __init__(self, name: str, methods: Optional[Dict[str, FunctionType]] = None):
        self.name = name
        self.methods: Dict[str, FunctionType] = methods if methods is not None else {}

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, InterfaceType) and self.name == other.name

    def __str__(self) -> str:
        return self.name


class ClassFieldInfo:
    def __init__(self, type: WysnaType, is_public: bool, owner_class: str):
        self.type = type
        self.is_public = is_public
        self.owner_class = owner_class


class ClassMethodInfo:
    def __init__(self, fn_type: FunctionType, is_public: bool, owner_class: str):
        self.fn_type = fn_type
        self.is_public = is_public
        self.owner_class = owner_class


class ClassType(WysnaType):
    def __init__(
        self,
        name: str,
        superclass: Optional['ClassType'] = None,
        interfaces: Optional[List[InterfaceType]] = None,
        fields: Optional[Dict[str, ClassFieldInfo]] = None,
        methods: Optional[Dict[str, ClassMethodInfo]] = None,
        init_type: Optional[FunctionType] = None,
    ):
        self.name = name
        self.superclass = superclass
        self.interfaces: List[InterfaceType] = interfaces if interfaces is not None else []
        self.fields: Dict[str, ClassFieldInfo] = fields if fields is not None else {}
        self.methods: Dict[str, ClassMethodInfo] = methods if methods is not None else {}
        self.init_type = init_type

    def is_subclass_of(self, target_class_name: str) -> bool:
        curr: Optional[ClassType] = self
        while curr is not None:
            if curr.name == target_class_name:
                return True
            curr = curr.superclass
        return False

    def implements_interface(self, target_intf_name: str) -> bool:
        curr: Optional[ClassType] = self
        while curr is not None:
            for intf in curr.interfaces:
                if intf.name == target_intf_name:
                    return True
            curr = curr.superclass
        return False

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, ClassType) and self.name == other.name

    def __str__(self) -> str:
        return self.name


class ModuleType(WysnaType):
    def __init__(self, name: str, scope: Any):
        self.name = name
        self.scope = scope

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, ModuleType) and self.name == other.name

    def __str__(self) -> str:
        return f"module {self.name}"


class AnyType(WysnaType):
    """Wildcard type for variadic builtins like print()."""
    def __eq__(self, other: Any) -> bool:
        return isinstance(other, AnyType)

    def __hash__(self) -> int:
        return hash("AnyType")

    def __str__(self) -> str:
        return "any"


class TypeParamType(WysnaType):
    """Represents a type parameter in generic declarations: T, U, A, B."""
    def __init__(self, name: str, constraint: Optional[WysnaType] = None):
        self.name = name
        self.constraint = constraint

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, TypeParamType) and self.name == other.name

    def __str__(self) -> str:
        return self.name


class GenericStructTemplate(WysnaType):
    """Represents an uninstantiated generic struct template: struct Box[T] { val: T }"""
    def __init__(self, name: str, type_params: List[Any], ast_decl: Any):
        self.name = name
        self.type_params = type_params
        self.ast_decl = ast_decl

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, GenericStructTemplate) and self.name == other.name

    def __str__(self) -> str:
        params_str = ", ".join(p.name if hasattr(p, "name") else str(p) for p in self.type_params)
        return f"{self.name}[{params_str}]"


class GenericFnTemplate(WysnaType):
    """Represents an uninstantiated generic function template: fn id[T](x: T) -> T"""
    def __init__(self, name: str, type_params: List[Any], ast_decl: Any):
        self.name = name
        self.type_params = type_params
        self.ast_decl = ast_decl

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, GenericFnTemplate) and self.name == other.name

    def __str__(self) -> str:
        params_str = ", ".join(p.name if hasattr(p, "name") else str(p) for p in self.type_params)
        return f"{self.name}[{params_str}]"


class GenericEnumTemplate(WysnaType):
    """Represents an uninstantiated generic enum template: enum Option[T] { Some(T), None }"""
    def __init__(self, name: str, type_params: List[Any], ast_decl: Any):
        self.name = name
        self.type_params = type_params
        self.ast_decl = ast_decl

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, GenericEnumTemplate) and self.name == other.name

    def __str__(self) -> str:
        params_str = ", ".join(p.name if hasattr(p, "name") else str(p) for p in self.type_params)
        return f"{self.name}[{params_str}]"


def is_assignable(source: WysnaType, target: WysnaType) -> bool:
    """
    Check if a value of type `source` can be assigned to a variable/param of type `target`.
    Strict rules:
    - No implicit int -> float coercion.
    - An optional T? accepts T and none.
    - A result T ! E accepts T (auto-wrapping ok value).
    - A non-optional T rejects none.
    - Subclass is assignable to Superclass or implemented Interface.
    - Canonical Option[T] <-> T? and Result[T, E] <-> T ! E equivalence.

    `any` is one-directional on purpose. It exists only so that variadic builtin
    signatures (`print`, `len`, `enumerate`, ...) can declare a wildcard parameter,
    and so that internal inference can pass a placeholder. Nothing may be *assigned
    to* an `any` target, because that is the operation that lets a value escape the
    type system (a program could declare `fn f() -> int`, store a `str` in an `any`
    local and return it, unobserved).
    """
    if isinstance(source, AnyType):
        return True
    if isinstance(target, AnyType):
        return isinstance(source, AnyType)

    if source == target:
        return True

    if isinstance(source, ErrorUnionType) or isinstance(target, ErrorUnionType):
        source_alternatives = source.alternatives if isinstance(source, ErrorUnionType) else (source,)
        target_alternatives = target.alternatives if isinstance(target, ErrorUnionType) else (target,)
        return all(
            any(source_alternative == target_alternative for target_alternative in target_alternatives)
            for source_alternative in source_alternatives
        )

    def optional_inner(value):
        if isinstance(value, OptionalType):
            return value.inner
        if isinstance(value, EnumType) and getattr(value, "template_name", None) == "Option":
            return value.type_args[0]
        return None

    source_inner, target_inner = optional_inner(source), optional_inner(target)
    if source_inner is not None and target_inner is not None:
        if (optional_inner(source_inner) is not None) != (optional_inner(target_inner) is not None):
            return False
        return is_assignable(source_inner, target_inner)

    # Canonical Option[T] <-> OptionalType(T) assignability
    if isinstance(target, EnumType) and getattr(target, "template_name", None) == "Option" and getattr(target, "type_args", None):
        if source == NoneType:
            return True
        opt_inner = target.type_args[0]
        if is_assignable(source, opt_inner):
            return True
        if isinstance(source, OptionalType) and is_assignable(source.inner, opt_inner):
            return True
        if isinstance(source, EnumType) and getattr(source, "template_name", None) == "Option" and getattr(source, "type_args", None):
            return is_assignable(source.type_args[0], opt_inner)
    if isinstance(source, EnumType) and getattr(source, "template_name", None) == "Option" and getattr(source, "type_args", None) and isinstance(target, OptionalType):
        return is_assignable(source.type_args[0], target.inner)

    # Canonical Result[T, E] <-> ResultType(T, E) assignability
    if isinstance(target, EnumType) and getattr(target, "template_name", None) == "Result" and getattr(target, "type_args", None) and len(target.type_args) == 2:
        if isinstance(source, ResultType) and source.ok == target.type_args[0] and is_error_channel_assignable(source.err, target.type_args[1]):
            return True
        if isinstance(source, EnumType) and getattr(source, "template_name", None) == "Result" and getattr(source, "type_args", None) and len(source.type_args) == 2:
            if source.type_args[0] == target.type_args[0] and is_error_channel_assignable(source.type_args[1], target.type_args[1]):
                return True
        if is_assignable(source, target.type_args[0]):
            return True
    if isinstance(source, EnumType) and getattr(source, "template_name", None) == "Result" and getattr(source, "type_args", None) and len(source.type_args) == 2 and isinstance(target, ResultType):
        if source.type_args[0] == target.ok and is_error_channel_assignable(source.type_args[1], target.err):
            return True
        return is_assignable(source, target.ok)

    # OOP Subtyping: Class -> Superclass
    if isinstance(source, ClassType) and isinstance(target, ClassType):
        return source.is_subclass_of(target.name)

    # OOP Subtyping: Class -> Interface
    if isinstance(source, ClassType) and isinstance(target, InterfaceType):
        return source.implements_interface(target.name)

    # Invariant List subtyping: list[S] -> list[T] iff S == T (SPEC 4.1 & ADR-002)
    if isinstance(source, ListType) and isinstance(target, ListType):
        return source.element == target.element

    # Invariant Dict subtyping: dict[K1, V1] -> dict[K2, V2] iff K1 == K2 and V1 == V2
    if isinstance(source, DictType) and isinstance(target, DictType):
        return source.key == target.key and source.value == target.value

    # Invariant Struct subtyping: S1 -> S2 iff S1.name == S2.name and type_args match
    if isinstance(source, StructType) and isinstance(target, StructType):
        if source.name != target.name:
            return False
        return getattr(source, "type_args", ()) == getattr(target, "type_args", ())

    # Invariant Enum subtyping for non-Option/Result enums:
    if isinstance(source, EnumType) and isinstance(target, EnumType):
        if source.name != target.name:
            return False
        return getattr(source, "type_args", ()) == getattr(target, "type_args", ())


    # An OptionalType(T) accepts T or none
    if isinstance(target, OptionalType):
        if source == NoneType:
            return True
        return is_assignable(source, target.inner)

    # A narrower Result error set can be assigned to a wider Result channel.
    # This preserves the tagged value; it is not an Ok lift.
    if isinstance(source, ResultType) and isinstance(target, ResultType):
        if source.ok == target.ok and is_error_channel_assignable(source.err, target.err):
            return True

    # A ResultType(ok, err) accepts ok value
    if isinstance(target, ResultType):
        return is_assignable(source, target.ok)

    return False
