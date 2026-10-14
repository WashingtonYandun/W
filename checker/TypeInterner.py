from typing import Any, Dict, List, Optional, Set, Tuple, Union
from checker.WType import (
    WType, PrimitiveType, IntType, FloatType, BoolType, StrType, UnitType, NoneType,
    OptionalType, ListType, DictType, TupleType, StructType, EnumType,
    InterfaceType, ClassFieldInfo, ClassMethodInfo, ClassType,
    ResultType, FunctionType, ModuleType, AnyType
)

# Canonical Reserved TypeId Constants (docs/TYPE_SYSTEM_DESIGN.md)
TYPE_ERROR: int = 0
TYPE_UNIT: int = 1
TYPE_BOOL: int = 2
TYPE_INT: int = 3
TYPE_FLOAT: int = 4
TYPE_STR: int = 5
TYPE_NONE: int = 6


class TypeCapabilities:
    """Precomputed capability and lifetime descriptor for a TypeId."""
    def __init__(
        self,
        needs_retain: bool = False,
        needs_release: bool = False,
        is_value: bool = True,
        is_reference: bool = False,
        is_copyable: bool = True,
        has_identity: bool = False,
        is_comparable: bool = True,
        is_valid_dict_key: bool = False,
    ):
        self.needs_retain = needs_retain
        self.needs_release = needs_release
        self.is_value = is_value
        self.is_reference = is_reference
        self.is_copyable = is_copyable
        self.has_identity = has_identity
        self.is_comparable = is_comparable
        self.is_valid_dict_key = is_valid_dict_key

    def to_dict(self) -> Dict[str, bool]:
        return {
            "needs_retain": self.needs_retain,
            "needs_release": self.needs_release,
            "is_value": self.is_value,
            "is_reference": self.is_reference,
            "is_copyable": self.is_copyable,
            "has_identity": self.has_identity,
            "is_comparable": self.is_comparable,
            "is_valid_dict_key": self.is_valid_dict_key,
        }

    def __repr__(self) -> str:
        return f"TypeCapabilities({self.to_dict()})"


class TypeEntry:
    """Immutable entry stored in the TypeInterner arena."""
    def __init__(self, tag: str, data: Any = None):
        self.tag = tag
        self.data = data

    def __repr__(self) -> str:
        return f"TypeEntry({self.tag}, {self.data})"


class StructDef:
    def __init__(self, def_id: int, name: str, fields: Dict[str, int]):
        self.def_id = def_id
        self.name = name
        self.fields = fields  # field_name -> TypeId


class EnumDef:
    def __init__(self, def_id: int, name: str, variants: List[str]):
        self.def_id = def_id
        self.name = name
        self.variants = variants


class InterfaceDef:
    def __init__(self, def_id: int, name: str, methods: Dict[str, int]):
        self.def_id = def_id
        self.name = name
        self.methods = methods  # method_name -> Function TypeId


class ClassDef:
    def __init__(
        self,
        def_id: int,
        name: str,
        superclass: Optional[int] = None,
        interfaces: Optional[List[int]] = None,
        fields: Optional[Dict[str, Tuple[int, bool]]] = None,  # name -> (TypeId, is_public)
        methods: Optional[Dict[str, Tuple[int, bool]]] = None,  # name -> (Function TypeId, is_public)
        init_sig: Optional[int] = None
    ):
        self.def_id = def_id
        self.name = name
        self.superclass = superclass  # Class TypeId
        self.interfaces = interfaces if interfaces is not None else []  # Interface TypeIds
        self.fields = fields if fields is not None else {}
        self.methods = methods if methods is not None else {}
        self.init_sig = init_sig


class TypeInterner:
    """
    Central Type Interner for W Language.
    Guarantees:
    - O(1) comparison between canonical TypeIds (id1 == id2).
    - Hash-consing of all structural and nominal type representations.
    - Pre-computed TypeCapabilities for ARC lifetime and CoW lowering.
    - Bidirectional mapping with legacy WType hierarchy.
    """
    def __init__(self) -> None:
        self._entries: List[TypeEntry] = []
        self._capabilities: List[TypeCapabilities] = []
        self._key_to_id: Dict[Tuple[Any, ...], int] = {}
        self._wtype_to_id: Dict[Any, int] = {}
        self._id_to_wtype: Dict[int, WType] = {}

        self.struct_defs: Dict[str, StructDef] = {}
        self.enum_defs: Dict[str, EnumDef] = {}
        self.interface_defs: Dict[str, InterfaceDef] = {}
        self.class_defs: Dict[str, ClassDef] = {}

        self._init_primitives()

    def _init_primitives(self) -> None:
        # 0: TYPE_ERROR
        self._register_fixed(
            TYPE_ERROR,
            ("error",),
            TypeEntry("error"),
            TypeCapabilities(is_value=True, is_comparable=True, is_valid_dict_key=False),
            AnyType()
        )
        # 1: TYPE_UNIT
        self._register_fixed(
            TYPE_UNIT,
            ("primitive", "unit"),
            TypeEntry("primitive", "unit"),
            TypeCapabilities(is_value=True, is_comparable=True, is_valid_dict_key=False),
            UnitType
        )
        # 2: TYPE_BOOL
        self._register_fixed(
            TYPE_BOOL,
            ("primitive", "bool"),
            TypeEntry("primitive", "bool"),
            TypeCapabilities(is_value=True, is_comparable=True, is_valid_dict_key=True),
            BoolType
        )
        # 3: TYPE_INT
        self._register_fixed(
            TYPE_INT,
            ("primitive", "int"),
            TypeEntry("primitive", "int"),
            TypeCapabilities(is_value=True, is_comparable=True, is_valid_dict_key=True),
            IntType
        )
        # 4: TYPE_FLOAT
        self._register_fixed(
            TYPE_FLOAT,
            ("primitive", "float"),
            TypeEntry("primitive", "float"),
            TypeCapabilities(is_value=True, is_comparable=True, is_valid_dict_key=False),
            FloatType
        )
        # 5: TYPE_STR
        self._register_fixed(
            TYPE_STR,
            ("primitive", "str"),
            TypeEntry("primitive", "str"),
            TypeCapabilities(needs_retain=True, needs_release=True, is_value=True, is_comparable=True, is_valid_dict_key=True),
            StrType
        )
        # 6: TYPE_NONE
        self._register_fixed(
            TYPE_NONE,
            ("primitive", "none"),
            TypeEntry("primitive", "none"),
            TypeCapabilities(is_value=True, is_comparable=True, is_valid_dict_key=False),
            NoneType
        )

    def _register_fixed(
        self,
        expected_id: int,
        key: Tuple[Any, ...],
        entry: TypeEntry,
        caps: TypeCapabilities,
        wtype: WType
    ) -> None:
        assigned_id = len(self._entries)
        assert assigned_id == expected_id, f"Primitive ID mismatch: expected {expected_id}, got {assigned_id}"
        self._entries.append(entry)
        self._capabilities.append(caps)
        self._key_to_id[key] = assigned_id
        self._id_to_wtype[assigned_id] = wtype

    def _intern(self, key: Tuple[Any, ...], entry: TypeEntry, caps: TypeCapabilities) -> int:
        if key in self._key_to_id:
            return self._key_to_id[key]
        type_id = len(self._entries)
        self._entries.append(entry)
        self._capabilities.append(caps)
        self._key_to_id[key] = type_id
        return type_id

    # -------------------------------------------------------------
    # Constructors for Composite Types
    # -------------------------------------------------------------

    def mk_optional(self, inner_id: int) -> int:
        if inner_id == TYPE_ERROR:
            return TYPE_ERROR
        # In W, T?? is normalized to T?
        entry = self.get_entry(inner_id)
        if entry.tag == "optional":
            return inner_id
        key = ("optional", inner_id)
        caps = TypeCapabilities(
            needs_retain=True,
            needs_release=True,
            is_value=self._capabilities[inner_id].is_value,
            is_reference=self._capabilities[inner_id].is_reference,
            has_identity=self._capabilities[inner_id].has_identity,
            is_comparable=True,
            is_valid_dict_key=False,
        )
        tid = self._intern(key, TypeEntry("optional", inner_id), caps)
        if tid not in self._id_to_wtype:
            self._id_to_wtype[tid] = OptionalType(self.to_wtype(inner_id))
        return tid

    def mk_result(self, ok_id: int, err_id: int) -> int:
        if ok_id == TYPE_ERROR or err_id == TYPE_ERROR:
            return TYPE_ERROR
        key = ("result", ok_id, err_id)
        caps = TypeCapabilities(
            needs_retain=True,
            needs_release=True,
            is_value=True,
            is_reference=False,
            is_comparable=False,
            is_valid_dict_key=False,
        )
        tid = self._intern(key, TypeEntry("result", (ok_id, err_id)), caps)
        if tid not in self._id_to_wtype:
            self._id_to_wtype[tid] = ResultType(self.to_wtype(ok_id), self.to_wtype(err_id))
        return tid

    def mk_list(self, elem_id: int) -> int:
        if elem_id == TYPE_ERROR:
            return TYPE_ERROR
        key = ("list", elem_id)
        caps = TypeCapabilities(
            needs_retain=True,
            needs_release=True,
            is_value=True,
            is_reference=False,
            is_comparable=True,
            is_valid_dict_key=False,
        )
        tid = self._intern(key, TypeEntry("list", elem_id), caps)
        if tid not in self._id_to_wtype:
            self._id_to_wtype[tid] = ListType(self.to_wtype(elem_id))
        return tid

    def mk_dict(self, key_id: int, val_id: int) -> int:
        if key_id == TYPE_ERROR or val_id == TYPE_ERROR:
            return TYPE_ERROR
        key = ("dict", key_id, val_id)
        caps = TypeCapabilities(
            needs_retain=True,
            needs_release=True,
            is_value=True,
            is_reference=False,
            is_comparable=True,
            is_valid_dict_key=False,
        )
        tid = self._intern(key, TypeEntry("dict", (key_id, val_id)), caps)
        if tid not in self._id_to_wtype:
            self._id_to_wtype[tid] = DictType(self.to_wtype(key_id), self.to_wtype(val_id))
        return tid

    def mk_tuple(self, elem_ids: Tuple[int, ...]) -> int:
        if any(eid == TYPE_ERROR for eid in elem_ids):
            return TYPE_ERROR
        key = ("tuple", elem_ids)
        needs_rc = any(self._capabilities[eid].needs_release for eid in elem_ids)
        caps = TypeCapabilities(
            needs_retain=needs_rc,
            needs_release=needs_rc,
            is_value=True,
            is_reference=False,
            is_comparable=True,
            is_valid_dict_key=False,
        )
        tid = self._intern(key, TypeEntry("tuple", elem_ids), caps)
        if tid not in self._id_to_wtype:
            self._id_to_wtype[tid] = TupleType([self.to_wtype(eid) for eid in elem_ids])
        return tid

    def mk_function(self, params: Tuple[int, ...], ret: int, is_mutating: bool = False) -> int:
        key = ("function", params, ret, is_mutating)
        caps = TypeCapabilities(
            needs_retain=False,
            needs_release=False,
            is_value=True,
            is_reference=False,
            is_comparable=False,
            is_valid_dict_key=False,
        )
        tid = self._intern(key, TypeEntry("function", (params, ret, is_mutating)), caps)
        if tid not in self._id_to_wtype:
            self._id_to_wtype[tid] = FunctionType([self.to_wtype(p) for p in params], self.to_wtype(ret), is_mutating)
        return tid

    # -------------------------------------------------------------
    # Constructors for Nominal User-Defined Types
    # -------------------------------------------------------------

    def mk_struct(self, name: str, fields: Optional[Dict[str, int]] = None) -> int:
        key = ("struct", name)
        if key in self._key_to_id:
            tid = self._key_to_id[key]
            if fields is not None and name in self.struct_defs:
                self.struct_defs[name].fields = fields
            return tid
        caps = TypeCapabilities(
            needs_retain=True,
            needs_release=True,
            is_value=True,
            is_reference=False,
            is_comparable=True,
            is_valid_dict_key=False,
        )
        tid = self._intern(key, TypeEntry("struct", name), caps)
        f_dict = fields if fields is not None else {}
        self.struct_defs[name] = StructDef(tid, name, f_dict)
        return tid

    def mk_enum(self, name: str, variants: Optional[List[str]] = None) -> int:
        key = ("enum", name)
        if key in self._key_to_id:
            tid = self._key_to_id[key]
            if variants is not None and name in self.enum_defs:
                self.enum_defs[name].variants = variants
            return tid
        caps = TypeCapabilities(
            needs_retain=False,
            needs_release=False,
            is_value=True,
            is_reference=False,
            is_comparable=True,
            is_valid_dict_key=True,
        )
        tid = self._intern(key, TypeEntry("enum", name), caps)
        v_list = variants if variants is not None else []
        self.enum_defs[name] = EnumDef(tid, name, v_list)
        return tid

    def mk_interface(self, name: str, methods: Optional[Dict[str, int]] = None) -> int:
        key = ("interface", name)
        if key in self._key_to_id:
            tid = self._key_to_id[key]
            if methods is not None and name in self.interface_defs:
                self.interface_defs[name].methods = methods
            return tid
        caps = TypeCapabilities(
            needs_retain=True,
            needs_release=True,
            is_value=False,
            is_reference=True,
            has_identity=True,
            is_comparable=True,
            is_valid_dict_key=False,
        )
        tid = self._intern(key, TypeEntry("interface", name), caps)
        m_dict = methods if methods is not None else {}
        self.interface_defs[name] = InterfaceDef(tid, name, m_dict)
        return tid

    def mk_class(
        self,
        name: str,
        superclass: Optional[int] = None,
        interfaces: Optional[List[int]] = None,
        fields: Optional[Dict[str, Tuple[int, bool]]] = None,
        methods: Optional[Dict[str, Tuple[int, bool]]] = None,
        init_sig: Optional[int] = None
    ) -> int:
        key = ("class", name)
        if key in self._key_to_id:
            tid = self._key_to_id[key]
            cdef = self.class_defs.get(name)
            if cdef is not None:
                if superclass is not None:
                    cdef.superclass = superclass
                if interfaces is not None:
                    cdef.interfaces = interfaces
                if fields is not None:
                    cdef.fields = fields
                if methods is not None:
                    cdef.methods = methods
                if init_sig is not None:
                    cdef.init_sig = init_sig
            return tid
        caps = TypeCapabilities(
            needs_retain=True,
            needs_release=True,
            is_value=False,
            is_reference=True,
            has_identity=True,
            is_comparable=True,
            is_valid_dict_key=False,
        )
        tid = self._intern(key, TypeEntry("class", name), caps)
        self.class_defs[name] = ClassDef(
            tid,
            name,
            superclass=superclass,
            interfaces=interfaces,
            fields=fields,
            methods=methods,
            init_sig=init_sig
        )
        return tid

    def mk_module(self, name: str) -> int:
        key = ("module", name)
        caps = TypeCapabilities(
            needs_retain=False,
            needs_release=False,
            is_value=False,
            is_reference=False,
            is_comparable=False,
            is_valid_dict_key=False,
        )
        return self._intern(key, TypeEntry("module", name), caps)

    def mk_any(self) -> int:
        key = ("any",)
        caps = TypeCapabilities(
            needs_retain=True,
            needs_release=True,
            is_value=True,
            is_reference=True,
            is_comparable=True,
            is_valid_dict_key=False,
        )
        return self._intern(key, TypeEntry("any"), caps)

    # -------------------------------------------------------------
    # Queries & Inspections
    # -------------------------------------------------------------

    def get_entry(self, type_id: int) -> TypeEntry:
        if 0 <= type_id < len(self._entries):
            return self._entries[type_id]
        return TypeEntry("error")

    def get_capabilities(self, type_id: int) -> TypeCapabilities:
        if 0 <= type_id < len(self._capabilities):
            return self._capabilities[type_id]
        return TypeCapabilities()

    def is_class_subclass_of(self, sub_id: int, sup_name: str) -> bool:
        sub_entry = self.get_entry(sub_id)
        if sub_entry.tag != "class":
            return False
        curr_name = sub_entry.data
        visited = set()
        while curr_name:
            if curr_name == sup_name:
                return True
            if curr_name in visited:
                break
            visited.add(curr_name)
            cdef = self.class_defs.get(curr_name)
            if not cdef or cdef.superclass is None:
                break
            sup_entry = self.get_entry(cdef.superclass)
            curr_name = sup_entry.data if sup_entry.tag == "class" else None
        return False

    def class_implements_interface(self, class_id: int, intf_name: str) -> bool:
        c_entry = self.get_entry(class_id)
        if c_entry.tag != "class":
            return False
        curr_name = c_entry.data
        visited = set()
        while curr_name:
            if curr_name in visited:
                break
            visited.add(curr_name)
            cdef = self.class_defs.get(curr_name)
            if not cdef:
                break
            for iid in cdef.interfaces:
                ientry = self.get_entry(iid)
                if ientry.tag == "interface" and ientry.data == intf_name:
                    return True
            if cdef.superclass is not None:
                sup_entry = self.get_entry(cdef.superclass)
                curr_name = sup_entry.data if sup_entry.tag == "class" else None
            else:
                break
        return False

    def is_assignable(self, src_id: int, dst_id: int) -> bool:
        """
        Fast canonical assignability check between TypeIds: src <: dst.
        Rules:
        - O(1) identity check.
        - TYPE_ERROR / Any is compatible with everything.
        - Optional T? accepts T, none, and S? if S <: T.
        - Result T ! E accepts T.
        - Covariant List subtyping for list literals/collections.
        - OOP subtyping: Class -> Superclass, Class -> Interface.
        """
        if src_id == dst_id:
            return True

        if src_id == TYPE_ERROR or dst_id == TYPE_ERROR:
            return True

        src_entry = self.get_entry(src_id)
        dst_entry = self.get_entry(dst_id)

        if src_entry.tag == "any" or dst_entry.tag == "any":
            return True

        # OOP Subtyping: Class -> Superclass
        if src_entry.tag == "class" and dst_entry.tag == "class":
            return self.is_class_subclass_of(src_id, dst_entry.data)

        # OOP Subtyping: Class -> Interface
        if src_entry.tag == "class" and dst_entry.tag == "interface":
            return self.class_implements_interface(src_id, dst_entry.data)

        # Covariant List subtyping: list[S] -> list[T] if S <: T
        if src_entry.tag == "list" and dst_entry.tag == "list":
            return self.is_assignable(src_entry.data, dst_entry.data)

        # Optional target: T? accepts T, none, and S? if S <: T
        if dst_entry.tag == "optional":
            if src_id == TYPE_NONE:
                return True
            inner_dst = dst_entry.data
            if src_entry.tag == "optional":
                return self.is_assignable(src_entry.data, inner_dst)
            return self.is_assignable(src_id, inner_dst)

        # Result target: (T ! E) accepts T
        if dst_entry.tag == "result":
            ok_id, err_id = dst_entry.data
            return self.is_assignable(src_id, ok_id)

        return False

    def to_string(self, type_id: int) -> str:
        """User-friendly canonical string representation of a TypeId."""
        entry = self.get_entry(type_id)
        if entry.tag == "error":
            return "<error>"
        elif entry.tag == "primitive":
            return str(entry.data)
        elif entry.tag == "optional":
            return f"{self.to_string(entry.data)}?"
        elif entry.tag == "result":
            ok_id, err_id = entry.data
            return f"{self.to_string(ok_id)} ! {self.to_string(err_id)}"
        elif entry.tag == "list":
            return f"list[{self.to_string(entry.data)}]"
        elif entry.tag == "dict":
            k_id, v_id = entry.data
            return f"dict[{self.to_string(k_id)}, {self.to_string(v_id)}]"
        elif entry.tag == "tuple":
            elem_strs = [self.to_string(eid) for eid in entry.data]
            return f"tuple[{', '.join(elem_strs)}]"
        elif entry.tag == "function":
            param_ids, ret_id, _ = entry.data
            p_strs = [self.to_string(pid) for pid in param_ids]
            return f"fn({', '.join(p_strs)}) -> {self.to_string(ret_id)}"
        elif entry.tag in ("struct", "enum", "interface", "class"):
            return str(entry.data)
        elif entry.tag == "module":
            return f"module {entry.data}"
        elif entry.tag == "any":
            return "any"
        return f"<unknown:{type_id}>"

    # -------------------------------------------------------------
    # Bidirectional Mapping: WType <-> TypeId
    # -------------------------------------------------------------

    def intern(self, wtype: WType) -> int:
        """Alias for from_wtype(wtype) to intern a WType to TypeId."""
        return self.from_wtype(wtype)

    def from_wtype(self, wtype: WType) -> int:
        """Converts an existing WType instance to its canonical TypeId."""
        if wtype is None:
            return TYPE_NONE
        if isinstance(wtype, PrimitiveType):
            if wtype.name == "int":
                return TYPE_INT
            elif wtype.name == "float":
                return TYPE_FLOAT
            elif wtype.name == "bool":
                return TYPE_BOOL
            elif wtype.name == "str":
                return TYPE_STR
            elif wtype.name == "unit":
                return TYPE_UNIT
            elif wtype.name == "none":
                return TYPE_NONE
            return TYPE_ERROR
        elif isinstance(wtype, OptionalType):
            return self.mk_optional(self.from_wtype(wtype.inner))
        elif isinstance(wtype, ResultType):
            return self.mk_result(self.from_wtype(wtype.ok), self.from_wtype(wtype.err))
        elif isinstance(wtype, ListType):
            return self.mk_list(self.from_wtype(wtype.element))
        elif isinstance(wtype, DictType):
            return self.mk_dict(self.from_wtype(wtype.key), self.from_wtype(wtype.value))
        elif isinstance(wtype, TupleType):
            return self.mk_tuple(tuple(self.from_wtype(e) for e in wtype.elements))
        elif isinstance(wtype, FunctionType):
            return self.mk_function(
                tuple(self.from_wtype(p) for p in wtype.params),
                self.from_wtype(wtype.ret),
                wtype.is_mutating
            )
        elif isinstance(wtype, StructType):
            key = ("struct", wtype.name)
            if key in self._key_to_id:
                return self._key_to_id[key]
            tid = self.mk_struct(wtype.name)
            fields = {fname: self.from_wtype(ftype) for fname, ftype in wtype.fields.items()} if hasattr(wtype, "fields") and wtype.fields else {}
            return self.mk_struct(wtype.name, fields)
        elif isinstance(wtype, EnumType):
            variants = wtype.variants if hasattr(wtype, "variants") else []
            return self.mk_enum(wtype.name, variants)
        elif isinstance(wtype, InterfaceType):
            key = ("interface", wtype.name)
            if key in self._key_to_id:
                return self._key_to_id[key]
            tid = self.mk_interface(wtype.name)
            methods = {mname: self.from_wtype(mfn) for mname, mfn in wtype.methods.items()} if hasattr(wtype, "methods") and wtype.methods else {}
            return self.mk_interface(wtype.name, methods)
        elif isinstance(wtype, ClassType):
            key = ("class", wtype.name)
            if key in self._key_to_id:
                return self._key_to_id[key]
            tid = self.mk_class(wtype.name)
            sup_id = self.from_wtype(wtype.superclass) if wtype.superclass else None
            intf_ids = [self.from_wtype(i) for i in wtype.interfaces] if wtype.interfaces else []
            fields = {fname: (self.from_wtype(finfo.type), finfo.is_public) for fname, finfo in wtype.fields.items()} if wtype.fields else {}
            methods = {mname: (self.from_wtype(minfo.fn_type), minfo.is_public) for mname, minfo in wtype.methods.items()} if wtype.methods else {}
            init_sig = self.from_wtype(wtype.init_type) if wtype.init_type else None
            return self.mk_class(wtype.name, superclass=sup_id, interfaces=intf_ids, fields=fields, methods=methods, init_sig=init_sig)
        elif isinstance(wtype, ModuleType):
            return self.mk_module(wtype.name)
        elif isinstance(wtype, AnyType):
            return self.mk_any()
        return TYPE_ERROR

    def to_wtype(self, type_id: int) -> WType:
        """Converts a TypeId back to a WType object."""
        if type_id in self._id_to_wtype:
            return self._id_to_wtype[type_id]

        entry = self.get_entry(type_id)
        res: WType = AnyType()

        if entry.tag == "error":
            res = AnyType()
        elif entry.tag == "primitive":
            pname = entry.data
            if pname == "int":
                res = IntType
            elif pname == "float":
                res = FloatType
            elif pname == "bool":
                res = BoolType
            elif pname == "str":
                res = StrType
            elif pname == "unit":
                res = UnitType
            elif pname == "none":
                res = NoneType
        elif entry.tag == "optional":
            res = OptionalType(self.to_wtype(entry.data))
        elif entry.tag == "result":
            ok_id, err_id = entry.data
            res = ResultType(self.to_wtype(ok_id), self.to_wtype(err_id))
        elif entry.tag == "list":
            res = ListType(self.to_wtype(entry.data))
        elif entry.tag == "dict":
            k_id, v_id = entry.data
            res = DictType(self.to_wtype(k_id), self.to_wtype(v_id))
        elif entry.tag == "tuple":
            res = TupleType([self.to_wtype(eid) for eid in entry.data])
        elif entry.tag == "function":
            params, ret, is_mut = entry.data
            res = FunctionType([self.to_wtype(p) for p in params], self.to_wtype(ret), is_mut)
        elif entry.tag == "struct":
            sdef = self.struct_defs.get(entry.data)
            f_wtypes = {fname: self.to_wtype(fid) for fname, fid in sdef.fields.items()} if sdef else {}
            res = StructType(entry.data, f_wtypes)
        elif entry.tag == "enum":
            edef = self.enum_defs.get(entry.data)
            v_list = edef.variants if edef else []
            res = EnumType(entry.data, v_list)
        elif entry.tag == "interface":
            idef = self.interface_defs.get(entry.data)
            m_wtypes = {mname: self.to_wtype(mid) for mname, mid in idef.methods.items()} if idef else {}
            res = InterfaceType(entry.data, m_wtypes)
        elif entry.tag == "class":
            cdef = self.class_defs.get(entry.data)
            if cdef:
                sup_wtype = self.to_wtype(cdef.superclass) if cdef.superclass is not None else None
                intf_wtypes = [self.to_wtype(iid) for iid in cdef.interfaces]
                f_infos = {fname: ClassFieldInfo(self.to_wtype(fid), is_pub, entry.data) for fname, (fid, is_pub) in cdef.fields.items()}
                m_infos = {mname: ClassMethodInfo(self.to_wtype(mid), is_pub, entry.data) for mname, (mid, is_pub) in cdef.methods.items()}
                init_wtype = self.to_wtype(cdef.init_sig) if cdef.init_sig is not None else None
                res = ClassType(entry.data, superclass=sup_wtype, interfaces=intf_wtypes, fields=f_infos, methods=m_infos, init_type=init_wtype)
            else:
                res = ClassType(entry.data)
        elif entry.tag == "module":
            res = ModuleType(entry.data, None)
        elif entry.tag == "any":
            res = AnyType()

        self._id_to_wtype[type_id] = res
        return res
