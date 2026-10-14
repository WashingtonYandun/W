import weakref
from typing import Any, Dict, List, Optional

def nominal_display_name(name):
    if name.startswith('__wm_'):
        boundary = name.find('__', 5)
        if boundary >= 0:
            return name[boundary + 2:]
    return name

def display_value(value, quote_string=False):
    while isinstance(value, WEnumValue) and value.enum_name == "Option" and value.variant == "Some" and value.payload:
        value = value.payload[0]
    return repr(value) if quote_string and isinstance(value, WStr) else str(value)

class WValue:
    """Base class for all runtime values in W Language v0.1."""
    def clone_value(self) -> 'WValue':
        return self

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, WEnumValue) and other.enum_name == "Option" and other.variant == "Some":
            return other == self
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
        v = int(value) & 0xFFFFFFFFFFFFFFFF
        if v >= 0x8000000000000000:
            v -= 0x10000000000000000
        self.value = v

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, WEnumValue) and other.enum_name == "Option" and other.variant == "Some":
            return other == self
        return isinstance(other, WInt) and self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return str(self.value)


class WFloat(WValue):
    def __init__(self, value: float):
        self.value = float(value)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, WEnumValue) and other.enum_name == "Option" and other.variant == "Some":
            return other == self
        return isinstance(other, WFloat) and self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return str(self.value)


class WBool(WValue):
    def __init__(self, value: bool):
        self.value = bool(value)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, WEnumValue) and other.enum_name == "Option" and other.variant == "Some":
            return other == self
        return isinstance(other, WBool) and self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return "true" if self.value else "false"


class WStr(WValue):
    def __init__(self, value: str):
        self.value = str(value)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, WEnumValue) and other.enum_name == "Option" and other.variant == "Some":
            return other == self
        return isinstance(other, WStr) and self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f'"{self.value}"'


class WUnit(WValue):
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, WEnumValue) and other.enum_name == "Option" and other.variant == "Some":
            return other == self
        return isinstance(other, WUnit)

    def __str__(self) -> str:
        return "unit"


class WNone(WValue):
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, WEnumValue) and other.enum_name == "Option" and other.variant == "Some":
            return other == self
        if isinstance(other, WNone):
            return True
        if isinstance(other, WEnumValue) and (other.enum_name == "Option" or other.enum_name.startswith("Option__")) and other.variant == "None":
            return True
        return False

    def __str__(self) -> str:
        return "none"


class WTuple(WValue):
    def __init__(self, elements: List[WValue]):
        self.elements = elements

    def clone_value(self) -> 'WTuple':
        return WTuple([e.clone_value() for e in self.elements])

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, WEnumValue) and other.enum_name == "Option" and other.variant == "Some":
            return other == self
        return isinstance(other, WTuple) and self.elements == other.elements

    def __str__(self) -> str:
        elems = ", ".join(display_value(e, True) for e in self.elements)
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
    def __new__(cls, enum_name, variant, payload=None):
        builtin = enum_name.split("__", 1)[0]
        if builtin == "Result" and variant in ("Ok", "Err") and payload is not None:
            return (WOk if variant == "Ok" else WErr)(payload[0] if payload else WUnit())
        if builtin == "Option" and variant in ("None", "none"):
            return WNone()
        return super().__new__(cls)

    def __init__(self, enum_name: str, variant: str, payload: Optional[List[WValue]] = None):
        self.enum_name = "Option" if enum_name.startswith("Option__") else enum_name
        self.variant = variant
        self.payload: List[WValue] = payload if payload is not None else []

    def clone_value(self) -> 'WEnumValue':
        return WEnumValue(self.enum_name, self.variant, [p.clone_value() for p in self.payload])

    def __eq__(self, other: Any) -> bool:
        self_some = self.enum_name == "Option" and self.variant == "Some"
        other_some = isinstance(other, WEnumValue) and other.enum_name == "Option" and other.variant == "Some"
        if self_some and not other_some and not isinstance(other, WNone):
            return bool(self.payload) and self.payload[0] == other
        if other_some and not self_some:
            return other == self
        if isinstance(other, WEnumValue):
            return self.enum_name == other.enum_name and self.variant == other.variant and self.payload == other.payload
        if (self.enum_name == "Option" or self.enum_name.startswith("Option__")) and self.variant == "None" and isinstance(other, WNone):
            return True
        if (self.enum_name == "Result" or self.enum_name.startswith("Result__")) and self.variant == "Ok" and isinstance(other, WOk):
            return len(self.payload) == 1 and self.payload[0] == other.value
        if (self.enum_name == "Result" or self.enum_name.startswith("Result__")) and self.variant == "Err" and isinstance(other, WErr):
            return len(self.payload) == 1 and self.payload[0] == other.error
        return False

    def __str__(self) -> str:
        if self.enum_name == "Option" and self.variant == "Some" and self.payload:
            return str(self.payload[0])
        if self.payload:
            args_str = ", ".join(display_value(p, True) for p in self.payload)
            return f"{nominal_display_name(self.enum_name)}.{self.variant}({args_str})"
        return f"{nominal_display_name(self.enum_name)}.{self.variant}"


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
        if isinstance(other, WEnumValue) and other.enum_name == "Option" and other.variant == "Some":
            return other == self
        if isinstance(other, WOk):
            return self.value == other.value
        if isinstance(other, WEnumValue) and (other.enum_name == "Result" or other.enum_name.startswith("Result__")) and other.variant == "Ok" and len(other.payload) == 1:
            return self.value == other.payload[0]
        return False

    def __str__(self) -> str:
        return f"Ok({self.value})"

class WErr(WResult):
    def __init__(self, error: WValue):
        self.error = error

    def clone_value(self) -> 'WErr':
        return WErr(self.error.clone_value())

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, WEnumValue) and other.enum_name == "Option" and other.variant == "Some":
            return other == self
        if isinstance(other, WErr):
            return self.error == other.error
        if isinstance(other, WEnumValue) and (other.enum_name == "Result" or other.enum_name.startswith("Result__")) and other.variant == "Err" and len(other.payload) == 1:
            return self.error == other.payload[0]
        return False

    def __str__(self) -> str:
        return f"Err({self.error})"


# ==========================================
# Copy-on-Write Backing Storage
# ==========================================

class CowTelemetry:
    """Process-wide logical CoW counters; Python storage has no C ABI byte model."""
    def __init__(self):
        self.detach_list: int = 0
        self.detach_dict: int = 0
        self.detach_struct: int = 0
        self.copied_slots: int = 0

    def reset(self) -> None:
        self.detach_list = 0
        self.detach_dict = 0
        self.detach_struct = 0
        self.copied_slots = 0

cow_telemetry = CowTelemetry()


class SharedBuffer:
    """Refcounted container to implement pure Value Semantics with Copy-on-Write."""
    def __init__(self, data: Any):
        self.data = data
        self.refcount = 1

    def __repr__(self) -> str:
        return f"SharedBuffer(refcount={self.refcount}, data={self.data})"


class CowOwner(WValue):
    """Each live value wrapper owns one reference to its shared buffer."""
    def __del__(self):
        storage = getattr(self, "storage", None)
        if storage is not None:
            storage.refcount -= 1


class WList(CowOwner):
    def __init__(self, storage: Optional[SharedBuffer] = None, elements: Optional[List[WValue]] = None):
        if storage is not None:
            self.storage = storage
        else:
            cloned_elems = [e.clone_value() for e in elements] if elements is not None else []
            self.storage = SharedBuffer(cloned_elems)

    def clone_value(self) -> 'WList':
        self.storage.refcount += 1
        return WList(storage=self.storage)

    def ensure_unique(self) -> None:
        if self.storage.refcount > 1:
            self.storage.refcount -= 1
            n = len(self.storage.data)
            cow_telemetry.detach_list += 1
            cow_telemetry.copied_slots += n
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
        if isinstance(other, WEnumValue) and other.enum_name == "Option" and other.variant == "Some":
            return other == self
        return isinstance(other, WList) and self.storage.data == other.storage.data

    def __str__(self) -> str:
        elems = ", ".join(display_value(e, True) for e in self.storage.data)
        return f"[{elems}]"


class WDict(CowOwner):
    def __init__(self, storage: Optional[SharedBuffer] = None, pairs: Optional[Dict[Any, WValue]] = None):
        if storage is not None:
            self.storage = storage
        else:
            cloned_pairs = {k: v.clone_value() for k, v in pairs.items()} if pairs is not None else {}
            self.storage = SharedBuffer(cloned_pairs)

    def clone_value(self) -> 'WDict':
        self.storage.refcount += 1
        return WDict(storage=self.storage)

    def ensure_unique(self) -> None:
        if self.storage.refcount > 1:
            self.storage.refcount -= 1
            n = len(self.storage.data)
            cow_telemetry.detach_dict += 1
            cow_telemetry.copied_slots += n * 2
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
        if isinstance(other, WEnumValue) and other.enum_name == "Option" and other.variant == "Some":
            return other == self
        return isinstance(other, WDict) and self.storage.data == other.storage.data

    def __str__(self) -> str:
        items = []
        for k, v in self.storage.data.items():
            k_str = f'"{k}"' if isinstance(k, str) else str(k)
            v_str = display_value(v, True)
            items.append(f"{k_str}: {v_str}")
        return "{" + ", ".join(items) + "}"


class WStructInstance(CowOwner):
    def __init__(self, struct_name: str, storage: Optional[SharedBuffer] = None, fields: Optional[Dict[str, WValue]] = None):
        self.struct_name = struct_name
        if storage is not None:
            self.storage = storage
        else:
            cloned_fields = {k: v.clone_value() for k, v in fields.items()} if fields is not None else {}
            self.storage = SharedBuffer(cloned_fields)

    def clone_value(self) -> 'WStructInstance':
        self.storage.refcount += 1
        return WStructInstance(self.struct_name, storage=self.storage)

    def ensure_unique(self) -> None:
        if self.storage.refcount > 1:
            self.storage.refcount -= 1
            n = len(self.storage.data)
            cow_telemetry.detach_struct += 1
            cow_telemetry.copied_slots += n
            self.storage = SharedBuffer({k: v.clone_value() for k, v in self.storage.data.items()})

    def get_field(self, name: str) -> WValue:
        return self.storage.data[name]

    def set_field(self, name: str, val: WValue) -> None:
        self.ensure_unique()
        self.storage.data[name] = val.clone_value()

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, WEnumValue) and other.enum_name == "Option" and other.variant == "Some":
            return other == self
        return isinstance(other, WStructInstance) and self.struct_name == other.struct_name and self.storage.data == other.storage.data

    def __str__(self) -> str:
        fields_str = ", ".join(f"{k}: {display_value(v, True)}" for k, v in self.storage.data.items())
        return f"{nominal_display_name(self.struct_name)} {{ {fields_str} }}"


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
        self.fields: Dict[str, WValue] = {k: v.clone_value() for k, v in fields.items()} if fields is not None else {}

    def clone_value(self) -> 'WObjectInstance':
        # Reference semantics: copying a reference points to the same object instance
        return self

    def get_field(self, name: str) -> WValue:
        return self.fields[name]

    def set_field(self, name: str, val: WValue) -> None:
        self.fields[name] = val.clone_value()

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, WEnumValue) and other.enum_name == "Option" and other.variant == "Some":
            return other == self
        return self is other

    def __str__(self) -> str:
        fields_str = ", ".join(f"{k}: {display_value(v, True)}" for k, v in self.fields.items())
        return f"{nominal_display_name(self.class_name)} {{ {fields_str} }}"


class WWeak(WValue):
    def __init__(self, target: Optional[WObjectInstance] = None):
        if target is None:
            self.identity = object()
            self.reference = lambda: None
            return
        if not hasattr(target, "weak_identity"):
            target.weak_identity = object()
        self.identity = target.weak_identity
        self.reference = weakref.ref(target)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, WEnumValue) and other.enum_name == "Option" and other.variant == "Some":
            return other == self
        return isinstance(other, WWeak) and self.identity is other.identity

    def __str__(self) -> str:
        return "weak(alive)" if self.reference() is not None else "weak(expired)"


class WSuperProxy(WValue):
    """Proxy binding 'super' inside a method to dispatch starting at the defining class's superclass."""
    def __init__(self, receiver: WObjectInstance, superclass_name: str):
        self.receiver = receiver
        self.superclass_name = superclass_name

    def __str__(self) -> str:
        return f"<super {self.superclass_name}>"


class WEnumNamespace(WValue):
    def __init__(self, name: str, variants: Any):
        self.name = name
        self.variants: Set[str] = set()
        if isinstance(variants, (list, set)):
            for v in variants:
                if hasattr(v, "name"):
                    self.variants.add(v.name)
                else:
                    self.variants.add(str(v))

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


