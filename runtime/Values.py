from typing import Any, Dict, List, Optional

class WValue:
    """Base class for all runtime values in W Language v0.1."""
    def clone_value(self) -> 'WValue':
        return self

    def __eq__(self, other: Any) -> bool:
        raise NotImplementedError

    def __str__(self) -> str:
        raise NotImplementedError

    def __repr__(self) -> str:
        return self.__str__()


# ==========================================
# Primitive Runtime Values
# ==========================================

class WInt(WValue):
    def __init__(self, value: int):
        self.value = int(value)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, WInt) and self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return str(self.value)


class WFloat(WValue):
    def __init__(self, value: float):
        self.value = float(value)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, WFloat) and self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return str(self.value)


class WBool(WValue):
    def __init__(self, value: bool):
        self.value = bool(value)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, WBool) and self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return "true" if self.value else "false"


class WStr(WValue):
    def __init__(self, value: str):
        self.value = str(value)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, WStr) and self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return self.value


class WUnit(WValue):
    def __eq__(self, other: Any) -> bool:
        return isinstance(other, WUnit)

    def __str__(self) -> str:
        return "unit"


class WNone(WValue):
    def __eq__(self, other: Any) -> bool:
        return isinstance(other, WNone)

    def __str__(self) -> str:
        return "none"


class WTuple(WValue):
    def __init__(self, elements: List[WValue]):
        self.elements = elements

    def clone_value(self) -> 'WTuple':
        return WTuple([e.clone_value() for e in self.elements])

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, WTuple) and self.elements == other.elements

    def __str__(self) -> str:
        elems = ", ".join(repr(e) if isinstance(e, WStr) else str(e) for e in self.elements)
        return f"({elems})"


class WRange(WValue):
    def __init__(self, start: int, end: int, inclusive: bool = False):
        self.start = start
        self.end = end
        self.inclusive = inclusive

    def __iter__(self):
        stop = self.end + 1 if self.inclusive else self.end
        for i in range(self.start, stop):
            yield WInt(i)

    def __str__(self) -> str:
        op = "..=" if self.inclusive else ".."
        return f"{self.start}{op}{self.end}"


class WEnumValue(WValue):
    def __init__(self, enum_name: str, variant: str):
        self.enum_name = enum_name
        self.variant = variant

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, WEnumValue) and self.enum_name == other.enum_name and self.variant == other.variant

    def __str__(self) -> str:
        return f"{self.enum_name}.{self.variant}"


# ==========================================
# Result & Fallible Values (T ! E)
# ==========================================

class WResult(WValue):
    pass

class WOk(WResult):
    def __init__(self, value: WValue):
        self.value = value

    def clone_value(self) -> 'WOk':
        return WOk(self.value.clone_value())

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, WOk) and self.value == other.value

    def __str__(self) -> str:
        return f"Ok({self.value})"

class WErr(WResult):
    def __init__(self, error: WValue):
        self.error = error

    def clone_value(self) -> 'WErr':
        return WErr(self.error.clone_value())

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, WErr) and self.error == other.error

    def __str__(self) -> str:
        return f"Err({self.error})"


# ==========================================
# Copy-on-Write Backing Storage
# ==========================================

class SharedBuffer:
    """Refcounted container to implement pure Value Semantics with Copy-on-Write."""
    def __init__(self, data: Any):
        self.data = data
        self.refcount = 1

    def __repr__(self) -> str:
        return f"SharedBuffer(refcount={self.refcount}, data={self.data})"


class WList(WValue):
    def __init__(self, storage: Optional[SharedBuffer] = None, elements: Optional[List[WValue]] = None):
        if storage is not None:
            self.storage = storage
        else:
            self.storage = SharedBuffer(list(elements) if elements is not None else [])

    def clone_value(self) -> 'WList':
        self.storage.refcount += 1
        return WList(storage=self.storage)

    def ensure_unique(self) -> None:
        if self.storage.refcount > 1:
            self.storage.refcount -= 1
            # Perform CoW detachment
            self.storage = SharedBuffer([elem.clone_value() for elem in self.storage.data])

    def append(self, elem: WValue) -> None:
        self.ensure_unique()
        self.storage.data.append(elem.clone_value())

    def pop(self, idx: int = -1) -> WValue:
        self.ensure_unique()
        return self.storage.data.pop(idx)

    def clear(self) -> None:
        self.ensure_unique()
        self.storage.data.clear()

    def get(self, idx: int) -> WValue:
        return self.storage.data[idx]

    def set(self, idx: int, val: WValue) -> None:
        self.ensure_unique()
        self.storage.data[idx] = val.clone_value()

    def __len__(self) -> int:
        return len(self.storage.data)

    def __iter__(self):
        return iter(self.storage.data)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, WList) and self.storage.data == other.storage.data

    def __str__(self) -> str:
        elems = ", ".join(repr(e) if isinstance(e, WStr) else str(e) for e in self.storage.data)
        return f"[{elems}]"


class WDict(WValue):
    def __init__(self, storage: Optional[SharedBuffer] = None, pairs: Optional[Dict[Any, WValue]] = None):
        if storage is not None:
            self.storage = storage
        else:
            self.storage = SharedBuffer(dict(pairs) if pairs is not None else {})

    def clone_value(self) -> 'WDict':
        self.storage.refcount += 1
        return WDict(storage=self.storage)

    def ensure_unique(self) -> None:
        if self.storage.refcount > 1:
            self.storage.refcount -= 1
            self.storage = SharedBuffer({k: v.clone_value() for k, v in self.storage.data.items()})

    def set(self, key: Any, val: WValue) -> None:
        self.ensure_unique()
        self.storage.data[key] = val.clone_value()

    def get(self, key: Any) -> Optional[WValue]:
        return self.storage.data.get(key)

    def keys(self) -> List[WValue]:
        return [WStr(k) if isinstance(k, str) else WInt(k) for k in self.storage.data.keys()]

    def values(self) -> List[WValue]:
        return list(self.storage.data.values())

    def __len__(self) -> int:
        return len(self.storage.data)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, WDict) and self.storage.data == other.storage.data

    def __str__(self) -> str:
        items = []
        for k, v in self.storage.data.items():
            k_str = f'"{k}"' if isinstance(k, str) else str(k)
            v_str = f'"{v}"' if isinstance(v, WStr) else str(v)
            items.append(f"{k_str}: {v_str}")
        return "{" + ", ".join(items) + "}"


class WStructInstance(WValue):
    def __init__(self, struct_name: str, storage: Optional[SharedBuffer] = None, fields: Optional[Dict[str, WValue]] = None):
        self.struct_name = struct_name
        if storage is not None:
            self.storage = storage
        else:
            self.storage = SharedBuffer(dict(fields) if fields is not None else {})

    def clone_value(self) -> 'WStructInstance':
        self.storage.refcount += 1
        return WStructInstance(self.struct_name, storage=self.storage)

    def ensure_unique(self) -> None:
        if self.storage.refcount > 1:
            self.storage.refcount -= 1
            self.storage = SharedBuffer({k: v.clone_value() for k, v in self.storage.data.items()})

    def get_field(self, name: str) -> WValue:
        return self.storage.data[name]

    def set_field(self, name: str, val: WValue) -> None:
        self.ensure_unique()
        self.storage.data[name] = val.clone_value()

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, WStructInstance) and self.struct_name == other.struct_name and self.storage.data == other.storage.data

    def __str__(self) -> str:
        fields_str = ", ".join(f"{k}: {repr(v) if isinstance(v, WStr) else str(v)}" for k, v in self.storage.data.items())
        return f"{self.struct_name} {{ {fields_str} }}"


# ==========================================
# Functions & Closures
# ==========================================

class WFunction(WValue):
    def __init__(self, decl: Any, closure_env: Any):
        self.decl = decl
        self.closure_env = closure_env

    def __str__(self) -> str:
        return f"<fn {self.decl.name}>"


class WNativeFunction(WValue):
    def __init__(self, name: str, call_fn: Any):
        self.name = name
        self.call_fn = call_fn

    def __str__(self) -> str:
        return f"<native fn {self.name}>"


class WBoundMethod(WValue):
    def __init__(self, receiver: WValue, method_name: str, target_class_name: Optional[str] = None):
        self.receiver = receiver
        self.method_name = method_name
        self.target_class_name = target_class_name

    def __str__(self) -> str:
        return f"<bound method {self.method_name}>"


class WClassDef(WValue):
    def __init__(self, name: str, superclass_name: Optional[str], fields: List[Any], methods: Dict[str, Any], closure_env: Any):
        self.name = name
        self.superclass_name = superclass_name
        self.fields = fields
        self.methods = methods
        self.closure_env = closure_env

    def __str__(self) -> str:
        return f"<class {self.name}>"


class WObjectInstance(WValue):
    """Heap-allocated class instance with reference semantics (mutations happen in-place)."""
    def __init__(self, class_name: str, fields: Optional[Dict[str, WValue]] = None):
        self.class_name = class_name
        self.fields: Dict[str, WValue] = dict(fields) if fields is not None else {}

    def clone_value(self) -> 'WObjectInstance':
        # Reference semantics: copying a reference points to the same object instance
        return self

    def get_field(self, name: str) -> WValue:
        return self.fields[name]

    def set_field(self, name: str, val: WValue) -> None:
        self.fields[name] = val.clone_value()

    def __eq__(self, other: Any) -> bool:
        return self is other

    def __str__(self) -> str:
        fields_str = ", ".join(f"{k}: {repr(v) if isinstance(v, WStr) else str(v)}" for k, v in self.fields.items())
        return f"{self.class_name} {{ {fields_str} }}"


class WSuperProxy(WValue):
    """Proxy binding 'super' inside a method to dispatch starting at the defining class's superclass."""
    def __init__(self, receiver: WObjectInstance, superclass_name: str):
        self.receiver = receiver
        self.superclass_name = superclass_name

    def __str__(self) -> str:
        return f"<super {self.superclass_name}>"


class WEnumNamespace(WValue):
    def __init__(self, name: str, variants: List[str]):
        self.name = name
        self.variants = set(variants)

    def get_variant(self, variant: str) -> WEnumValue:
        if variant not in self.variants:
            raise KeyError(f"Enum '{self.name}' has no variant '{variant}'")
        return WEnumValue(self.name, variant)

    def __str__(self) -> str:
        return f"<enum {self.name}>"


class WModule(WValue):
    def __init__(self, name: str, env: Any):
        self.name = name
        self.env = env

    def get_member(self, member: str) -> WValue:
        return self.env.lookup(member)

    def __str__(self) -> str:
        return f"<module {self.name}>"


