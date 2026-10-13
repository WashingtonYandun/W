from typing import Dict, List, Optional, Any

class WType:
    """Base class for semantic types in W Language v0.1."""
    def __eq__(self, other: Any) -> bool:
        raise NotImplementedError

    def __str__(self) -> str:
        raise NotImplementedError

    def __repr__(self) -> str:
        return self.__str__()


class PrimitiveType(WType):
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


class OptionalType(WType):
    def __init__(self, inner: WType):
        self.inner = inner

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, OptionalType) and self.inner == other.inner

    def __str__(self) -> str:
        return f"{self.inner}?"


class ListType(WType):
    def __init__(self, element: WType):
        self.element = element

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, ListType) and self.element == other.element

    def __str__(self) -> str:
        return f"list[{self.element}]"


class DictType(WType):
    def __init__(self, key: WType, value: WType):
        self.key = key
        self.value = value

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, DictType) and self.key == other.key and self.value == other.value

    def __str__(self) -> str:
        return f"dict[{self.key}, {self.value}]"


class TupleType(WType):
    def __init__(self, elements: List[WType]):
        self.elements = elements

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, TupleType) and self.elements == other.elements

    def __str__(self) -> str:
        elems = ", ".join(str(e) for e in self.elements)
        return f"tuple[{elems}]"


class StructType(WType):
    def __init__(self, name: str, fields: Dict[str, WType]):
        self.name = name
        self.fields = fields

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, StructType) and self.name == other.name

    def __str__(self) -> str:
        return self.name


class EnumType(WType):
    def __init__(self, name: str, variants: List[str]):
        self.name = name
        self.variants = variants

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, EnumType) and self.name == other.name

    def __str__(self) -> str:
        return self.name


class ResultType(WType):
    def __init__(self, ok: WType, err: WType):
        self.ok = ok
        self.err = err

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, ResultType) and self.ok == other.ok and self.err == other.err

    def __str__(self) -> str:
        return f"{self.ok} ! {self.err}"


class FunctionType(WType):
    def __init__(self, params: List[WType], ret: WType, is_mutating: bool = False):
        self.params = params
        self.ret = ret
        self.is_mutating = is_mutating

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, FunctionType) and self.params == other.params and self.ret == other.ret

    def __str__(self) -> str:
        params_str = ", ".join(str(p) for p in self.params)
        return f"fn({params_str}) -> {self.ret}"


class ModuleType(WType):
    def __init__(self, name: str, scope: Any):
        self.name = name
        self.scope = scope

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, ModuleType) and self.name == other.name

    def __str__(self) -> str:
        return f"module {self.name}"


class AnyType(WType):
    """Wildcard type for variadic builtins like print()."""
    def __eq__(self, other: Any) -> bool:
        return True

    def __str__(self) -> str:
        return "any"



def is_assignable(source: WType, target: WType) -> bool:
    """
    Check if a value of type `source` can be assigned to a variable/param of type `target`.
    Strict rules:
    - No implicit int -> float coercion.
    - An optional T? accepts T and none.
    - A result T ! E accepts T (auto-wrapping ok value).
    - A non-optional T rejects none.
    """
    if target == AnyType() or source == AnyType():
        return True

    if source == target:
        return True

    # An OptionalType(T) accepts T or none
    if isinstance(target, OptionalType):
        if source == NoneType:
            return True
        return is_assignable(source, target.inner)

    # A ResultType(ok, err) accepts ok value
    if isinstance(target, ResultType):
        return is_assignable(source, target.ok)

    return False
