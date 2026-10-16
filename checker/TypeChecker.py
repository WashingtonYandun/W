from checker.OopGenerics import GenericOopTemplate, specialize as specialize_oop
import copy
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, NamedTuple, Sequence
from node.NodeType import (
    ExternFnDecl, LambdaExpr, FunctionType as AstFunctionType, Node, Program, Stmt, Expr, TypeNode, Pattern, Block,
    NamedType, OptionalType as AstOptionalType, ListType as AstListType,
    DictType as AstDictType, TupleType as AstTupleType, ResultType as AstResultType,
    ErrorUnionType as AstErrorUnionType,
    GenericType, TypeParam,
    IdentifierPattern, TuplePattern, EnumPattern, LiteralPattern, WildcardPattern,
    FnDecl, Param, StructDecl, StructField, EnumDecl,
    InterfaceDecl, InterfaceMethod, ClassDecl, ClassField, MethodDecl,
    ImportDecl, LetDecl,
    WhileStmt, ForStmt, ReturnStmt, BreakStmt, ContinueStmt, ExprStmt,
    IntLiteral, FloatLiteral, StringLiteral, BoolLiteral, NoneLiteral,
    IdentExpr, ThisExpr, SuperExpr, NewExpr,
    UnaryExpr, BinaryExpr, CoalesceExpr, RangeExpr, PostfixTryExpr, ElseErrExpr,
    CallExpr, MemberExpr, IndexExpr, AssignmentExpr,
    StructInitExpr, FieldInit, ListExpr, DictExpr, TupleExpr,
    IfExpr, ElifBranch, MatchExpr, MatchArm, VariantDecl
)
from checker.WType import (
    WType, IntType, FloatType, BoolType, StrType, UnitType, NoneType,
    OptionalType, WeakType, ListType, DictType, TupleType, StructType, EnumType,
    InterfaceType, ClassFieldInfo, ClassMethodInfo, ClassType,
    ResultType, ErrorUnionType, FunctionType, ModuleType, AnyType,
    TypeParamType, GenericStructTemplate, GenericFnTemplate, GenericEnumTemplate,
    is_assignable, is_error_channel_assignable
)
from checker.SymbolTable import Scope, Symbol, create_global_scope
from checker.TypeInterner import TypeInterner
from error.Error import TypeError
from checker.LayoutGraph import LayoutGraph, build_layout_graph_from_declarations


def _equality_compatible(left: WType, right: WType, seen: Optional[set] = None) -> bool:
    """True when `left == right` can be decided at runtime.

    Two specializations of the same generic template count as compatible when their
    type arguments line up, treating an unbound type parameter as compatible with
    anything. Without this, `Ok(42) == Err("bad")` is rejected because checking the
    operands separately infers `Result[int, E]` and `Result[T, str]`: two different
    specialized names for what is really a single `Result[int, str]` comparison.
    """
    if left == right:
        return True
    if isinstance(left, TypeParamType) or isinstance(right, TypeParamType):
        return True
    if isinstance(left, AnyType) or isinstance(right, AnyType):
        return True
    if isinstance(left, EnumType) and isinstance(right, EnumType):
        if getattr(left, "template_name", None) != getattr(right, "template_name", None):
            return False
        if len(left.type_args) != len(right.type_args):
            return False
        return all(_equality_compatible(a, b, seen) for a, b in zip(left.type_args, right.type_args))
    if seen is None:
        seen = set()
    if (id(left), id(right)) in seen:
        return False
    seen.add((id(left), id(right)))
    if isinstance(left, StructType) and isinstance(right, StructType):
        if getattr(left, "template_name", None) != getattr(right, "template_name", None):
            return False
        if len(left.type_args) != len(right.type_args):
            return False
        return all(_equality_compatible(a, b, seen) for a, b in zip(left.type_args, right.type_args))
    if isinstance(left, ListType) and isinstance(right, ListType):
        return _equality_compatible(left.element, right.element, seen)
    if isinstance(left, OptionalType) and isinstance(right, OptionalType):
        return _equality_compatible(left.inner, right.inner, seen)
    if isinstance(left, TupleType) and isinstance(right, TupleType):
        return len(left.elements) == len(right.elements) and all(
            _equality_compatible(a, b, seen) for a, b in zip(left.elements, right.elements))
    if isinstance(left, ResultType) and isinstance(right, ResultType):
        return (_equality_compatible(left.ok, right.ok, seen)
                and _equality_compatible(left.err, right.err, seen))
    if isinstance(left, ErrorUnionType) and isinstance(right, ErrorUnionType):
        return (len(left.alternatives) == len(right.alternatives)
                and all(_equality_compatible(a, b, seen)
                        for a, b in zip(left.alternatives, right.alternatives)))
    return False


class GenericInstanceKey(NamedTuple):
    """Session-local specialization identity; not a persistent hash or ABI name."""
    template_name: str
    type_ids: Tuple[int, ...]
    module_id: Optional[str] = None
    decl_id: Optional[Any] = None


class SpecializationState(Enum):
    PENDING = "pending"
    SPECIALIZING = "specializing"
    COMPLETE = "complete"
    FAILED = "failed"


class SpecializationEntry:
    def __init__(
        self,
        key: GenericInstanceKey,
        state: SpecializationState = SpecializationState.PENDING,
        specialized_type: Optional[WType] = None,
        specialized_symbol: Optional[Symbol] = None,
        ast_decl: Optional[Any] = None
    ):
        self.key = key
        self.state = state
        self.specialized_type = specialized_type
        self.specialized_symbol = specialized_symbol
        self.ast_decl = ast_decl
        self.dependencies: Set[GenericInstanceKey] = set()


# Largest structural size a single generic specialization may reach. The depth
# limit below bounds recursion; this bounds growth, which a depth limit alone
# does not catch because every level is a distinct, cached specialization.
MAX_SPECIALIZATION_COMPLEXITY = 256

def _mangle_type_static(t: WType) -> str:
    if isinstance(t, AnyType):
        return "any"
    if t == IntType:
        return "int"
    if t == FloatType:
        return "float"
    if t == BoolType:
        return "bool"
    if t == StrType:
        return "str"
    if t == UnitType:
        return "unit"
    if t == NoneType:
        return "none"
    if isinstance(t, (StructType, EnumType, ClassType, InterfaceType)):
        return f"{len(t.name)}_{t.name}"
    if isinstance(t, OptionalType):
        return f"opt__{_mangle_type_static(t.inner)}"
    if isinstance(t, ListType):
        return f"list__{_mangle_type_static(t.element)}"
    if isinstance(t, DictType):
        return f"dict__{_mangle_type_static(t.key)}__{_mangle_type_static(t.value)}"
    if isinstance(t, TupleType):
        elems = "__".join(_mangle_type_static(e) for e in t.elements)
        return f"tuple_{len(t.elements)}__{elems}"
    if isinstance(t, ResultType):
        return f"res__{_mangle_type_static(t.ok)}__{_mangle_type_static(t.err)}"
    if isinstance(t, ErrorUnionType):
        members = "__".join(_mangle_type_static(member) for member in t.alternatives)
        return f"errunion_{len(t.alternatives)}__{members}"
    if isinstance(t, TypeParamType):
        return t.name
    safe_str = str(t).replace("[", "__").replace("]", "").replace(", ", "__").replace(" ", "_")
    return f"{len(safe_str)}_{safe_str}"


def mangle_generic_name(
    template_name: str,
    concrete_args: Sequence[WType],
    module_name: Optional[str] = None
) -> str:
    args_part = "__".join(_mangle_type_static(a) for a in concrete_args)
    if template_name in ("Option", "Result"):
        return f"{template_name}__{args_part}"
    mod_prefix = f"{len(module_name)}_{module_name}__" if module_name else ""
    return f"_W_G_{mod_prefix}{len(template_name)}_{template_name}__{args_part}"


def type_strictly_contains(sub: WType, container: WType) -> bool:
    """Returns True if sub is a strict structural sub-component of container."""
    if sub == container:
        return False
    return _type_contains(sub, container)


def _type_contains(sub: WType, container: WType) -> bool:
    if sub == container:
        return True
    if isinstance(container, ListType):
        return _type_contains(sub, container.element)
    if isinstance(container, DictType):
        return _type_contains(sub, container.key) or _type_contains(sub, container.value)
    if isinstance(container, TupleType):
        return any(_type_contains(sub, e) for e in container.elements)
    if isinstance(container, OptionalType):
        return _type_contains(sub, container.inner)
    if isinstance(container, ResultType):
        return _type_contains(sub, container.ok) or _type_contains(sub, container.err)
    if isinstance(container, ErrorUnionType):
        return any(_type_contains(sub, member) for member in container.alternatives)
    if isinstance(container, (StructType, EnumType)) and getattr(container, "type_args", None):
        return any(_type_contains(sub, arg) for arg in container.type_args)
    return False


class MonomorphizationTelemetry:
    """Telemetry tracking generic specialization, cache hits, and code bloat."""
    def __init__(
        self,
        specialization_requests: int = 0,
        deduplicated_hits: int = 0,
        specialized_structs: int = 0,
        specialized_enums: int = 0,
        specialized_functions: int = 0
    ) -> None:
        self.specialization_requests = specialization_requests
        self.deduplicated_hits = deduplicated_hits
        self.specialized_structs = specialized_structs
        self.specialized_enums = specialized_enums
        self.specialized_functions = specialized_functions

    def to_dict(self) -> Dict[str, int]:
        return {
            "specialization_requests": self.specialization_requests,
            "deduplicated_hits": self.deduplicated_hits,
            "specialized_structs": self.specialized_structs,
            "specialized_enums": self.specialized_enums,
            "specialized_functions": self.specialized_functions,
        }


class TypeChecker:
    """
    Two-pass Semantic Analyzer and Type Checker for W Language v0.2.
    Pass 1: Collect & register all top-level declarations (Enums, Structs, Interfaces, Classes, Functions, Imports).
    Pass 2: Check function/method bodies, local bindings, assignments, and expressions.
    """
    def __init__(
        self,
        file: str = "<stdin>",
        session=None
    ) -> None:
        self.file = file
        self.global_scope = create_global_scope()
        self.current_scope = self.global_scope
        self.current_fn_ret_type: Optional[WType] = None
        self.expected_type: Optional[WType] = None
        self.current_class: Optional[ClassType] = None
        self.scope_spans = []
        self.closure_counter = 0
        self.loop_depth: int = 0
        from compiler.CompilationSession import CompilationSession
        self.session = session or CompilationSession()
        self.interner: TypeInterner = self.session.interner
        self.monomorphized_oop_decls = []
        self.generic_struct_templates: Dict[str, GenericStructTemplate] = {}
        self.generic_fn_templates: Dict[str, GenericFnTemplate] = {}
        self.generic_enum_templates: Dict[str, GenericEnumTemplate] = {}
        self.specializations: Dict[GenericInstanceKey, SpecializationEntry] = {}
        self.monomorphized_structs: Dict[GenericInstanceKey, StructType] = {}
        self.monomorphized_fns: Dict[GenericInstanceKey, Symbol] = {}
        self.monomorphized_enums: Dict[GenericInstanceKey, EnumType] = {}
        self.monomorphized_struct_decls: List[StructDecl] = []
        self.monomorphized_fn_decls: List[FnDecl] = []
        self.monomorphized_enum_decls: List[EnumDecl] = []
        self._monomorphize_depth: int = 0
        self._instantiation_stack: List[Tuple[str, Tuple[int, ...], int, Tuple[WType, ...], int, int]] = []
        # Type-parameter substitution in effect while a specialization is being
        # resolved. Unbound parameters keep their own name, so the resolver has to
        # consult this binding before treating a name as a declared type.
        self._active_type_subst: Optional[Dict[str, WType]] = None
        self.telemetry: MonomorphizationTelemetry = MonomorphizationTelemetry()

        # Canonical built-in Option[T] template
        opt_decl = EnumDecl(
            name="Option",
            variants=[
                VariantDecl(name="Some", payload_types=[NamedType(name="T")]),
                VariantDecl(name="None", payload_types=[])
            ],
            type_params=[TypeParam(name="T")]
        )
        self.generic_enum_templates["Option"] = GenericEnumTemplate("Option", [TypeParam(name="T")], opt_decl)

        # Canonical built-in Result[T, E] template
        res_decl = EnumDecl(
            name="Result",
            variants=[
                VariantDecl(name="Ok", payload_types=[NamedType(name="T")]),
                VariantDecl(name="Err", payload_types=[NamedType(name="E")])
            ],
            type_params=[TypeParam(name="T"), TypeParam(name="E")]
        )
        self.generic_enum_templates["Result"] = GenericEnumTemplate("Result", [TypeParam(name="T"), TypeParam(name="E")], res_decl)

    def check(self, program: Program) -> None:
        self.session.check_program(program, self)

    def _check_program(self, program: Program) -> None:
        # Reserve builtin identities and their specialization namespaces.
        for declaration in program.body:
            if isinstance(declaration, (StructDecl, EnumDecl, ClassDecl, InterfaceDecl)):
                if declaration.name in ("Option", "Result", "Weak") or declaration.name.startswith(("Option__", "Result__")):
                    raise TypeError("Builtin Option/Result/Weak identities are reserved", line=declaration.line,
                                    col=declaration.col, file=self.file, code="W1002")

        # Validate finite layouts via formal LayoutGraph (SCC on inline subgraph)
        pre_graph = build_layout_graph_from_declarations(
            struct_decls=[s for s in program.body if isinstance(s, StructDecl)],
            enum_decls=[s for s in program.body if isinstance(s, EnumDecl)],
            class_decls=[s for s in program.body if isinstance(s, ClassDecl)],
        )
        pre_graph.validate_finite_layouts(file_path=self.file)

        # Pass 1: Collect declarations
        self._pass1_collect_declarations(program)

        # Validate constraints even when the template is never instantiated.
        templates = list(self.generic_struct_templates.values())
        templates.extend(self.generic_fn_templates.values())
        templates.extend(self.generic_enum_templates.values())
        for template in templates:
            for parameter in template.type_params:
                constraint = getattr(parameter, "constraint", None)
                if constraint is not None:
                    self._resolve_constraint_interface(constraint, parameter.line, parameter.col)

        # Pass 2: Typecheck bodies & statements
        self._pass2_check_program(program)

        # Filter out uninstantiated generic templates and insert monomorphized declarations
        filtered_body: List[Stmt] = []
        for stmt in program.body:
            if isinstance(stmt, (StructDecl, FnDecl, EnumDecl, ClassDecl, InterfaceDecl)) and stmt.type_params:
                continue
            filtered_body.append(stmt)

        sorted_structs, sorted_enums, sorted_fns = self._sort_monomorphized_decls()
        final_body: List[Stmt] = []
        final_body.extend(self.monomorphized_oop_decls)
        final_body.extend(sorted_structs)
        final_body.extend(sorted_enums)
        final_body.extend(sorted_fns)
        final_body.extend(filtered_body)
        program.body = final_body

        # Post-monomorphization layout verification
        post_graph = build_layout_graph_from_declarations(
            struct_decls=[s for s in program.body if isinstance(s, StructDecl)],
            enum_decls=[s for s in program.body if isinstance(s, EnumDecl)],
            class_decls=[s for s in program.body if isinstance(s, ClassDecl)],
        )
        post_graph.validate_finite_layouts(file_path=self.file)

        program.interner = self.interner

    def _sort_monomorphized_decls(self) -> Tuple[List[StructDecl], List[EnumDecl], List[FnDecl]]:
        struct_map = {s.name: s for s in self.monomorphized_struct_decls}
        struct_deps: Dict[str, Set[str]] = {}
        for s in self.monomorphized_struct_decls:
            deps = set()
            for f in s.fields:
                f_type_name = getattr(f.type_ann, "name", None)
                if f_type_name and f_type_name in struct_map and f_type_name != s.name:
                    deps.add(f_type_name)
            struct_deps[s.name] = deps

        sorted_struct_names: List[str] = []
        visited_structs: Set[str] = set()
        temp_structs: Set[str] = set()

        def visit_struct(name: str):
            if name in temp_structs:
                return
            if name not in visited_structs:
                temp_structs.add(name)
                for dep in sorted(struct_deps.get(name, set())):
                    visit_struct(dep)
                temp_structs.remove(name)
                visited_structs.add(name)
                sorted_struct_names.append(name)

        for name in sorted(struct_map.keys()):
            if name not in visited_structs:
                visit_struct(name)

        sorted_structs = [struct_map[n] for n in sorted_struct_names]
        sorted_enums = sorted(self.monomorphized_enum_decls, key=lambda e: e.name)
        sorted_fns = sorted(self.monomorphized_fn_decls, key=lambda f: f.name)
        return sorted_structs, sorted_enums, sorted_fns

    # ==========================================
    # Pass 1: Collect Top-Level Declarations
    # ==========================================

    def _resolve_import(self, stmt: ImportDecl) -> WType:
        return self.session.import_module(stmt, self.file)

    def _pass1_collect_declarations(self, program: Program) -> None:
        # Reject user declarations starting with reserved compiler prefixes
        for stmt in program.body:
            if hasattr(stmt, "name") and isinstance(stmt.name, str) and not hasattr(stmt, "specialization_shell"):
                if stmt.name.startswith("_W_") or stmt.name.startswith("__w_"):
                    raise TypeError(
                        message=f"Identifier '{stmt.name}' is reserved for internal compiler use",
                        line=stmt.line,
                        col=stmt.col,
                        file=self.file,
                        code="W1002"
                    )

        # Step 1a: Pre-register ALL nominal type shells (Enums, Interfaces, Classes, Structs, Imports)
        for stmt in program.body:
            if isinstance(stmt, EnumDecl):
                if stmt.type_params:
                    template = GenericEnumTemplate(stmt.name, stmt.type_params, stmt)
                    self.generic_enum_templates[stmt.name] = template
                    self.global_scope.define_type(stmt.name, template, line=stmt.line, col=stmt.col, file=self.file)
                    continue

                seen_variants: Set[str] = set()
                variant_names: List[str] = []
                for v in stmt.variants:
                    v_name = v.name if hasattr(v, "name") else str(v)
                    if v_name in seen_variants:
                        raise TypeError(
                            message=f"Duplicate variant '{v_name}' in enum '{stmt.name}'",
                            line=stmt.line,
                            col=stmt.col,
                            file=self.file,
                            code="T008"
                        )
                    seen_variants.add(v_name)
                    variant_names.append(v_name)

                enum_type = EnumType(name=stmt.name, variants=variant_names, variant_payloads={})
                self.global_scope.define_type(stmt.name, enum_type, line=stmt.line, col=stmt.col, file=self.file)

            elif isinstance(stmt, InterfaceDecl):
                if stmt.type_params:
                    self.global_scope.define_type(stmt.name, GenericOopTemplate(stmt, self), file=self.file)
                    continue
                if hasattr(stmt, 'specialization_shell'):
                    continue
                intf_type = InterfaceType(name=stmt.name, methods={})
                self.global_scope.define_type(stmt.name, intf_type, line=stmt.line, col=stmt.col, file=self.file)

            elif isinstance(stmt, ClassDecl):
                if stmt.type_params:
                    self.global_scope.define_type(stmt.name, GenericOopTemplate(stmt, self), file=self.file)
                    continue
                if hasattr(stmt, 'specialization_shell'):
                    continue
                cls_type = ClassType(name=stmt.name)
                self.global_scope.define_type(stmt.name, cls_type, line=stmt.line, col=stmt.col, file=self.file)

            elif isinstance(stmt, StructDecl):
                if stmt.type_params:
                    template = GenericStructTemplate(name=stmt.name, type_params=stmt.type_params, ast_decl=stmt)
                    self.generic_struct_templates[stmt.name] = template
                    self.global_scope.define_type(stmt.name, template, line=stmt.line, col=stmt.col, file=self.file)
                else:
                    seen_fields: Set[str] = set()
                    for f in stmt.fields:
                        if f.name in seen_fields:
                            raise TypeError(
                                message=f"Duplicate field '{f.name}' in struct '{stmt.name}'",
                                line=f.line,
                                col=f.col,
                                file=self.file,
                                code="T014"
                            )
                        seen_fields.add(f.name)
                    struct_type = StructType(name=stmt.name, fields={})
                    self.global_scope.define_type(stmt.name, struct_type, line=stmt.line, col=stmt.col, file=self.file)

            elif isinstance(stmt, ImportDecl):
                mod_type = self._resolve_import(stmt)
                self.global_scope.define_symbol(
                    Symbol(stmt.namespace, mod_type, is_mut=False, kind="import", line=stmt.line, col=stmt.col),
                    file=self.file
                )

        # Step 1b: Resolve Members, Payloads, Signatures, and Top-Level Functions
        class_decls: List[ClassDecl] = []
        for stmt in program.body:
            if isinstance(stmt, EnumDecl):
                if stmt.type_params:
                    continue
                enum_type = self.global_scope.lookup_type(stmt.name)
                assert isinstance(enum_type, EnumType)
                variant_payloads: Dict[str, List[WType]] = {}
                for v in stmt.variants:
                    v_name = v.name if hasattr(v, "name") else str(v)
                    payload_wtypes: List[WType] = []
                    if hasattr(v, "payload_types") and v.payload_types:
                        for pt in v.payload_types:
                            payload_wtypes.append(self._resolve_type_node(pt))
                    variant_payloads[v_name] = payload_wtypes
                enum_type.variant_payloads = variant_payloads

            elif isinstance(stmt, StructDecl):
                if stmt.type_params:
                    continue
                struct_type = self.global_scope.lookup_type(stmt.name)
                assert isinstance(struct_type, StructType)
                fields_dict: Dict[str, WType] = {}
                for f in stmt.fields:
                    f_type = self._resolve_type_node(f.type_ann)
                    fields_dict[f.name] = f_type
                struct_type.fields = fields_dict
                self.interner.from_wtype(struct_type)

            elif isinstance(stmt, InterfaceDecl):
                if stmt.type_params:
                    continue
                intf_type = self.global_scope.lookup_type(stmt.name)
                assert isinstance(intf_type, InterfaceType)
                for m in stmt.methods:
                    if m.name in intf_type.methods:
                        raise TypeError(
                            message=f"Duplicate method '{m.name}' in interface '{stmt.name}'",
                            line=m.line,
                            col=m.col,
                            file=self.file,
                            code="T008"
                        )
                    p_types = [self._resolve_type_node(p.type_ann) for p in m.params]
                    r_type = self._resolve_type_node(m.return_type)
                    intf_type.methods[m.name] = FunctionType(params=p_types, ret=r_type)

            elif isinstance(stmt, ClassDecl):
                if stmt.type_params:
                    continue
                if isinstance(stmt.superclass, TypeNode):
                    stmt.superclass = self._resolve_type_node(stmt.superclass).name
                stmt.interfaces = [self._resolve_type_node(interface).name if isinstance(interface, TypeNode) else interface
                                   for interface in stmt.interfaces]
                class_decls.append(stmt)
                cls_type = self.global_scope.lookup_type(stmt.name)
                assert isinstance(cls_type, ClassType)

                if stmt.superclass is not None:
                    sup_t = self.global_scope.lookup_type(stmt.superclass)
                    if sup_t is None or not isinstance(sup_t, ClassType):
                        raise TypeError(
                            message=f"Unknown superclass '{stmt.superclass}' for class '{stmt.name}'",
                            line=stmt.line,
                            col=stmt.col,
                            file=self.file,
                            code="T002"
                        )
                    if sup_t.name == stmt.name or sup_t.is_subclass_of(stmt.name):
                        raise TypeError(
                            message=f"Cyclic class inheritance detected involving '{stmt.name}'",
                            line=stmt.line,
                            col=stmt.col,
                            file=self.file,
                            code="W3003"
                        )
                    cls_type.superclass = sup_t

                for intf_name in stmt.interfaces:
                    intf_t = self.global_scope.lookup_type(intf_name)
                    if intf_t is None or not isinstance(intf_t, InterfaceType):
                        raise TypeError(
                            message=f"Unknown interface '{intf_name}' implemented by class '{stmt.name}'",
                            line=stmt.line,
                            col=stmt.col,
                            file=self.file,
                            code="T002"
                        )
                    cls_type.interfaces.append(intf_t)

                # Own fields & methods
                seen_own_fields: Set[str] = set()
                for f in stmt.fields:
                    if f.name in seen_own_fields:
                        raise TypeError(
                            message=f"Duplicate field '{f.name}' in class '{stmt.name}'",
                            line=f.line,
                            col=f.col,
                            file=self.file,
                            code="T014"
                        )
                    seen_own_fields.add(f.name)
                    f_type = self._resolve_type_node(f.type_ann)
                    cls_type.fields[f.name] = ClassFieldInfo(type=f_type, is_public=f.is_public, owner_class=stmt.name)

                seen_own_methods: Set[str] = set()
                for m in stmt.methods:
                    if m.name in seen_own_methods:
                        raise TypeError(
                            message=f"Duplicate method '{m.name}' in class '{stmt.name}'",
                            line=m.line,
                            col=m.col,
                            file=self.file,
                            code="T008"
                        )
                    seen_own_methods.add(m.name)
                    p_types = [self._resolve_type_node(p.type_ann) for p in m.params]
                    r_type = self._resolve_type_node(m.return_type)
                    fn_t = FunctionType(params=p_types, ret=r_type)
                    if m.name == "init":
                        cls_type.init_type = fn_t
                    else:
                        cls_type.methods[m.name] = ClassMethodInfo(fn_type=fn_t, is_public=m.is_public, owner_class=stmt.name)

            elif isinstance(stmt, FnDecl):
                if stmt.type_params:
                    template = GenericFnTemplate(name=stmt.name, type_params=stmt.type_params, ast_decl=stmt)
                    self.generic_fn_templates[stmt.name] = template
                    self.global_scope.define_symbol(
                        Symbol(stmt.name, template, is_mut=False, kind="fn", line=stmt.line, col=stmt.col),
                        file=self.file
                    )
                else:
                    param_types: List[WType] = [self._resolve_type_node(p.type_ann) for p in stmt.params]
                    ret_type = self._resolve_type_node(stmt.return_type)
                    fn_type = FunctionType(params=param_types, ret=ret_type)
                    self.global_scope.define_symbol(
                        Symbol(stmt.name, fn_type, is_mut=False, kind="fn", line=stmt.line, col=stmt.col),
                        file=self.file
                    )


        # Step 1d: Propagate inherited members and verify interface contracts
        for stmt in class_decls:
            cls_type = self.global_scope.lookup_type(stmt.name)
            assert isinstance(cls_type, ClassType)

            # Collect ancestor chain from root superclass down to direct superclass
            ancestors: List[ClassType] = []
            curr_sup = cls_type.superclass
            while curr_sup is not None:
                ancestors.append(curr_sup)
                curr_sup = curr_sup.superclass
            ancestors.reverse()

            merged_fields: Dict[str, ClassFieldInfo] = {}
            merged_methods: Dict[str, ClassMethodInfo] = {}
            for anc in ancestors:
                for fname, finfo in anc.fields.items():
                    merged_fields[fname] = finfo
                for mname, minfo in anc.methods.items():
                    merged_methods[mname] = minfo

            # Apply subclass own fields and methods (checking override compatibility)
            for fname, finfo in cls_type.fields.items():
                if fname in merged_fields and finfo.owner_class == cls_type.name:
                    raise TypeError(f"Inherited field '{fname}' cannot be redeclared", file=self.file,
                                    line=stmt.line, col=stmt.col, code="W3003")
                merged_fields[fname] = finfo
            for mname, minfo in cls_type.methods.items():
                if mname in merged_methods:
                    base_m = merged_methods[mname]
                    if not base_m.is_public:
                        raise TypeError(
                            message=f"Cannot override private method '{mname}' of superclass '{base_m.owner_class}'",
                            line=stmt.line,
                            col=stmt.col,
                            file=self.file,
                            code="W3002"
                        )
                    if base_m.is_public and not minfo.is_public:
                        raise TypeError(f"Public method '{mname}' cannot become private", file=self.file,
                                        line=stmt.line, col=stmt.col, code="W3002")
                    if minfo.fn_type.params != base_m.fn_type.params or not is_assignable(minfo.fn_type.ret, base_m.fn_type.ret):
                        raise TypeError(
                            message=f"Method '{mname}' in class '{stmt.name}' has incompatible override signature with superclass '{base_m.owner_class}'",
                            line=stmt.line,
                            col=stmt.col,
                            file=self.file,
                            code="W3003"
                        )
                merged_methods[mname] = minfo

            cls_type.fields = merged_fields
            cls_type.methods = merged_methods

            # Verify all implemented interfaces
            for intf in cls_type.interfaces:
                for req_name, req_sig in intf.methods.items():
                    if req_name not in cls_type.methods:
                        raise TypeError(
                            message=f"Class '{stmt.name}' does not implement required method '{req_name}' from interface '{intf.name}'",
                            line=stmt.line,
                            col=stmt.col,
                            file=self.file,
                            code="W3003"
                        )
                    impl_info = cls_type.methods[req_name]
                    if not impl_info.is_public:
                        raise TypeError(
                            message=f"Interface method '{req_name}' in class '{stmt.name}' must be public",
                            line=stmt.line,
                            col=stmt.col,
                            file=self.file,
                            code="W3003"
                        )
                    if impl_info.fn_type.params != req_sig.params or not is_assignable(impl_info.fn_type.ret, req_sig.ret):
                        raise TypeError(
                            message=f"Method '{req_name}' in class '{stmt.name}' does not match signature required by interface '{intf.name}'",
                            line=stmt.line,
                            col=stmt.col,
                            file=self.file,
                            code="W3003"
                        )


    # ==========================================
    # Pass 2: Typecheck Program Bodies
    # ==========================================

    def _pass2_check_program(self, program: Program) -> None:
        for stmt in program.body:
            self._check_stmt(stmt)

    def _check_stmt(self, stmt: Stmt) -> None:
        if isinstance(stmt, (EnumDecl, StructDecl, InterfaceDecl, ImportDecl)):
            return  # Handled in Pass 1

        elif isinstance(stmt, ClassDecl):
            if stmt.type_params:
                return
            self._check_class_decl(stmt)

        elif isinstance(stmt, FnDecl):
            if stmt.type_params:
                return  # Generic templates are typechecked when monomorphized
            self._check_fn_decl(stmt)

        elif isinstance(stmt, LetDecl):
            self._check_let_decl(stmt)

        elif isinstance(stmt, WhileStmt):
            cond_t = self._check_expr(stmt.condition)
            if cond_t != BoolType:
                raise TypeError(
                    message=f"While loop condition must be bool, found '{cond_t}'",
                    line=stmt.condition.line,
                    col=stmt.condition.col,
                    file=self.file,
                    code="T003"
                )
            self.loop_depth += 1
            try:
                self._check_block(stmt.body, is_statement_context=True)
            finally:
                self.loop_depth -= 1

        elif isinstance(stmt, ForStmt):
            self._check_for_stmt(stmt)

        elif isinstance(stmt, ReturnStmt):
            val_t = self._check_payload(stmt.value, self.current_fn_ret_type) if stmt.value else UnitType
            if self.current_fn_ret_type is None:
                raise TypeError(
                    message="Return statement outside of function",
                    line=stmt.line,
                    col=stmt.col,
                    file=self.file,
                    code="W1004"
                )
            if not is_assignable(val_t, self.current_fn_ret_type):
                raise TypeError(
                    message=f"Return type mismatch: expected '{self.current_fn_ret_type}', found '{val_t}'",
                    line=stmt.line,
                    col=stmt.col,
                    file=self.file,
                    code="T006"
                )

            self._mark_result_lift(stmt.value, self.current_fn_ret_type)

        elif isinstance(stmt, BreakStmt):
            if self.loop_depth == 0:
                raise TypeError(
                    message="'break' statement outside of loop",
                    line=stmt.line,
                    col=stmt.col,
                    file=self.file,
                    code="W1004"
                )

        elif isinstance(stmt, ContinueStmt):
            if self.loop_depth == 0:
                raise TypeError(
                    message="'continue' statement outside of loop",
                    line=stmt.line,
                    col=stmt.col,
                    file=self.file,
                    code="W1004"
                )

        elif isinstance(stmt, ExprStmt):
            self._check_expr(stmt.expr, is_statement_context=True)

    def _check_constructor_rules(self, stmt: ClassDecl, cls_type: ClassType, m: MethodDecl) -> None:
        # 1. Constructor return type check: init cannot return non-unit
        if cls_type.init_type is not None and cls_type.init_type.ret != UnitType:
            raise TypeError(
                message=f"Constructor 'init' of class '{stmt.name}' cannot return a value of type '{cls_type.init_type.ret}', expected 'unit'",
                line=m.line,
                col=m.col,
                file=self.file,
                code="W3004"
            )

        from checker.ConstructorFlow import check_constructor
        check_constructor(stmt, cls_type, m, self.file)

    def _check_class_decl(self, stmt: ClassDecl) -> None:
        cls_type = self.global_scope.lookup_type(stmt.name)
        assert isinstance(cls_type, ClassType)
        old_class = self.current_class
        self.current_class = cls_type
        try:
            for m in stmt.methods:
                if m.name == "init":
                    self._check_constructor_rules(stmt, cls_type, m)
                fn_type = cls_type.init_type if m.name == "init" else cls_type.methods[m.name].fn_type
                assert fn_type is not None
                fn_scope = Scope(parent=self.current_scope, is_function_scope=True)
                old_scope = self.current_scope
                old_ret_type = self.current_fn_ret_type
                old_loop_depth = self.loop_depth
                self.current_scope = fn_scope
                self.current_fn_ret_type = fn_type.ret
                self.loop_depth = 0
                try:
                    # Also bind 'self' as an alias to 'this' inside methods
                    fn_scope.define_symbol(
                        Symbol("self", cls_type, is_mut=False, kind="param", line=m.line, col=m.col),
                        file=self.file
                    )
                    for p, p_type in zip(m.params, fn_type.params):
                        fn_scope.define_symbol(
                            Symbol(p.name, p_type, is_mut=False, kind="param", line=p.line, col=p.col),
                            file=self.file
                        )
                    is_unit_ret = (fn_type.ret == UnitType) or (isinstance(fn_type.ret, ResultType) and fn_type.ret.ok == UnitType)
                    body_ret = self._check_block(m.body, is_statement_context=is_unit_ret)
                    self._mark_result_lift(m.body.tail_expr, fn_type.ret)
                    if not is_unit_ret and not self._block_has_return(m.body):
                        if body_ret is not None and is_assignable(body_ret, fn_type.ret):
                            pass
                        else:
                            raise TypeError(
                                message=f"Method '{stmt.name}.{m.name}' missing return statement for type '{fn_type.ret}'",
                                line=m.line,
                                col=m.col,
                                file=self.file,
                                code="T006"
                            )
                finally:
                    self.current_scope = old_scope
                    self.current_fn_ret_type = old_ret_type
                    self.loop_depth = old_loop_depth
        finally:
            self.current_class = old_class

    def _check_fn_decl(self, stmt: FnDecl) -> None:
        if isinstance(stmt, ExternFnDecl):
            allowed = {"int", "int32", "int64", "float", "double", "bool", "opaque"}
            if (not all(isinstance(p.type_ann, NamedType) and p.type_ann.name in allowed for p in stmt.params)
                    or not isinstance(stmt.return_type, NamedType) or stmt.return_type.name not in allowed | {"unit"}):
                raise TypeError("C FFI accepts only scalar and opaque ABI types", file=self.file,
                                line=stmt.line, col=stmt.col, code="W2001")
            return
        sym = self.global_scope.lookup_symbol(stmt.name)
        assert sym is not None and isinstance(sym.type, FunctionType)
        fn_type: FunctionType = sym.type

        fn_scope = Scope(parent=self.current_scope, is_function_scope=True)
        old_scope = self.current_scope
        old_ret_type = self.current_fn_ret_type
        old_loop_depth = self.loop_depth

        self.current_scope = fn_scope
        self.current_fn_ret_type = fn_type.ret
        self.loop_depth = 0

        try:
            # Bind parameters in function scope as immutable
            for p, p_type in zip(stmt.params, fn_type.params):
                fn_scope.define_symbol(
                    Symbol(p.name, p_type, is_mut=False, kind="param", line=p.line, col=p.col),
                    file=self.file
                )

            is_unit_ret = (fn_type.ret == UnitType) or (isinstance(fn_type.ret, ResultType) and fn_type.ret.ok == UnitType)
            body_ret = self._check_block(stmt.body, is_statement_context=is_unit_ret)
            self._mark_result_lift(stmt.body.tail_expr, fn_type.ret)

            # If function expects a return value other than unit, verify return presence
            if not is_unit_ret and not self._block_has_return(stmt.body):
                if body_ret is not None and is_assignable(body_ret, fn_type.ret):
                    pass  # Tail expression satisfies return
                else:
                    raise TypeError(
                        message=f"Function '{stmt.name}' missing return statement for type '{fn_type.ret}'",
                        line=stmt.line,
                        col=stmt.col,
                        file=self.file,
                        code="T006"
                    )
        finally:
            self.current_scope = old_scope
            self.current_fn_ret_type = old_ret_type
            self.loop_depth = old_loop_depth

    def _expr_has_return(self, expr: Expr) -> bool:
        if isinstance(expr, IfExpr):
            if expr.else_branch is None:
                return False
            if not self._block_has_return(expr.then_branch):
                return False
            for eb in expr.elif_branches:
                if not self._block_has_return(eb.body):
                    return False
            return self._block_has_return(expr.else_branch)
        if isinstance(expr, MatchExpr):
            if not expr.arms:
                return False
            for arm in expr.arms:
                if not isinstance(arm.body, Block) or not self._block_has_return(arm.body):
                    return False
            return True
        return False

    def _block_has_return(self, block: Block) -> bool:
        for s in block.statements:
            if isinstance(s, ReturnStmt):
                return True
            if isinstance(s, ExprStmt) and self._expr_has_return(s.expr):
                return True
        if block.tail_expr is not None and self._expr_has_return(block.tail_expr):
            return True
        return False

    def _block_diverges(self, block: Block) -> bool:
        for s in block.statements:
            if isinstance(s, (ReturnStmt, BreakStmt, ContinueStmt)):
                return True
        return self._block_has_return(block)

    # The synthetic parameter name introduced by closure conversion. Captured
    # variables are immutable snapshots today, so a mutation attempt is rejected -- but
    # the diagnostic has to name the captured variable, not a compiler internal.
    CLOSURE_ENVIRONMENT_PARAMETER = '__w_environment'

    def _binding_error_name(self, symbol) -> str:
        if symbol is not None and getattr(symbol, 'name', None) == self.CLOSURE_ENVIRONMENT_PARAMETER:
            return "a captured variable"
        return symbol.name if symbol is not None else "a captured variable"

    def _immutable_binding_message(self, symbol, action: str) -> str:
        """Explains why a mutation target is not writable.

        A captured variable is a snapshot in the closure environment, so the reason
        differs from a plain `let` binding and the message must say which one applies.
        """
        if symbol is not None and getattr(symbol, 'name', None) == self.CLOSURE_ENVIRONMENT_PARAMETER:
            return (f"Cannot {action} on a captured variable: closures capture values "
                    f"as immutable snapshots")
        return f"Cannot {action} on immutable binding '{self._binding_error_name(symbol)}'"

    def _find_value_root_symbol(self, expr: Expr) -> Optional[Symbol]:
        if isinstance(expr, IdentExpr):
            return self.current_scope.lookup_symbol(expr.name)
        if isinstance(expr, IndexExpr):
            return self._find_value_root_symbol(expr.object)
        if isinstance(expr, MemberExpr):
            obj_t = self._check_expr(expr.object)
            if isinstance(obj_t, ClassType):
                return None
            return self._find_value_root_symbol(expr.object)
        return None

    def _check_class_instantiation(self, class_t: ClassType, args: List[Expr], line: int, col: int) -> ClassType:
        init_fn: Optional[FunctionType] = None
        curr_c: Optional[ClassType] = class_t
        while curr_c is not None:
            if curr_c.init_type is not None:
                init_fn = curr_c.init_type
                break
            curr_c = curr_c.superclass
        if init_fn is not None:
            expected_params = init_fn.params
            if len(args) != len(expected_params):
                raise TypeError(
                    message=f"Constructor of '{class_t.name}' expects {len(expected_params)} arguments, found {len(args)}",
                    line=line,
                    col=col,
                    file=self.file,
                    code="T015"
                )
            for i, (a_expr, p_type) in enumerate(zip(args, expected_params)):
                a_type = self._check_expr(a_expr)
                if not is_assignable(a_type, p_type):
                    raise TypeError(
                        message=f"Constructor argument {i + 1} type mismatch: expected '{p_type}', found '{a_type}'",
                        line=a_expr.line,
                        col=a_expr.col,
                        file=self.file,
                        code="T003"
                    )
        else:
            if len(args) != 0:
                raise TypeError(
                    message=f"Default constructor of '{class_t.name}' takes 0 arguments, found {len(args)}",
                    line=line,
                    col=col,
                    file=self.file,
                    code="T015"
                )
        return class_t


    def _check_block(self, block: Block, is_statement_context: bool = False, initial_bindings: Optional[Dict[str, WType]] = None) -> Optional[WType]:
        block_scope = Scope(parent=self.current_scope)
        if initial_bindings:
            for b_name, b_type in initial_bindings.items():
                block_scope.define_symbol(
                    Symbol(b_name, b_type, is_mut=False, kind="var", line=block.line, col=block.col),
                    file=self.file
                )
        old_scope = self.current_scope
        self.current_scope = block_scope
        self.scope_spans.append(((block.line, block.col),
                                 (getattr(block, 'end_line', block.line), getattr(block, 'end_col', block.col)), block_scope))

        try:
            for s in block.statements:
                self._check_stmt(s)
            if block.tail_expr:
                return self._check_expr(block.tail_expr, is_statement_context=is_statement_context)
            return None
        finally:
            self.current_scope = old_scope

    def _check_let_decl(self, stmt: LetDecl) -> None:
        if stmt.name.startswith("_W_") or stmt.name.startswith("__w_"):
            raise TypeError(
                message=f"Identifier '{stmt.name}' is reserved for internal compiler use",
                line=stmt.line,
                col=stmt.col,
                file=self.file,
                code="W1002"
            )
        # Check for unannotated empty list or none
        if isinstance(stmt.initializer, ListExpr) and len(stmt.initializer.elements) == 0 and stmt.type_ann is None:
            raise TypeError(
                message="Cannot infer type of empty list literal '[]'; explicit type annotation required",
                line=stmt.line,
                col=stmt.col,
                file=self.file,
                code="T011"
            )

        if isinstance(stmt.initializer, NoneLiteral) and stmt.type_ann is None:
            raise TypeError(
                message="Cannot infer type of 'none'; explicit optional type annotation required",
                line=stmt.line,
                col=stmt.col,
                file=self.file,
                code="T011"
            )

        if isinstance(stmt.initializer, DictExpr) and len(stmt.initializer.entries) == 0 and stmt.type_ann is None:
            raise TypeError(
                message="Cannot infer type of empty dictionary literal '{}'; explicit type annotation required",
                line=stmt.line,
                col=stmt.col,
                file=self.file,
                code="T011"
            )


        expected_type: Optional[WType] = None
        if stmt.type_ann is not None:
            expected_type = self._resolve_type_node(stmt.type_ann)

        old_expected = self.expected_type
        self.expected_type = expected_type
        try:
            init_type = self._check_expr(stmt.initializer)
        finally:
            self.expected_type = old_expected

        if expected_type is not None:
            if not is_assignable(init_type, expected_type):
                raise TypeError(
                    message=f"Type mismatch: cannot assign value of type '{init_type}' to variable '{stmt.name}' of type '{expected_type}'",
                    line=stmt.line,
                    col=stmt.col,
                    file=self.file,
                    code="T003"
                )
            var_type = expected_type
        else:
            var_type = init_type

        self._mark_result_lift(stmt.initializer, var_type, force=True)
        self.current_scope.define_symbol(
            Symbol(stmt.name, var_type, is_mut=stmt.is_mut, kind="var", line=stmt.line, col=stmt.col),
            file=self.file
        )

    def _check_for_stmt(self, stmt: ForStmt) -> None:
        iter_t = self._check_expr(stmt.iterable)

        # Iterable must be a list
        elem_t: WType
        if isinstance(iter_t, ListType):
            elem_t = iter_t.element
        else:
            raise TypeError(
                message=f"Cannot iterate over non-list value of type '{iter_t}'",
                line=stmt.iterable.line,
                col=stmt.iterable.col,
                file=self.file,
                code="T003"
            )

        self._bind_pattern_type(stmt.pattern, elem_t, {}, stmt.line, stmt.col)
        loop_scope = Scope(parent=self.current_scope)
        old_scope = self.current_scope
        self.current_scope = loop_scope
        self.loop_depth += 1

        try:
            if isinstance(stmt.pattern, IdentifierPattern):
                loop_scope.define_symbol(
                    Symbol(stmt.pattern.name, elem_t, is_mut=False, kind="var", line=stmt.pattern.line, col=stmt.pattern.col),
                    file=self.file
                )
            elif isinstance(stmt.pattern, TuplePattern):
                if not isinstance(elem_t, TupleType) or len(elem_t.elements) != len(stmt.pattern.elements):
                    raise TypeError(
                        message=f"Cannot destructure iterable element of type '{elem_t}' into {len(stmt.pattern.elements)} variables",
                        line=stmt.pattern.line,
                        col=stmt.pattern.col,
                        file=self.file,
                        code="T003"
                    )
                for p_var, p_type in zip(stmt.pattern.elements, elem_t.elements):
                    assert isinstance(p_var, IdentifierPattern)
                    loop_scope.define_symbol(
                        Symbol(p_var.name, p_type, is_mut=False, kind="var", line=p_var.line, col=p_var.col),
                        file=self.file
                    )

            for s in stmt.body.statements:
                self._check_stmt(s)
            if stmt.body.tail_expr is not None:
                self._check_expr(stmt.body.tail_expr, is_statement_context=True)
        finally:
            self.loop_depth -= 1
            self.current_scope = old_scope

    # ==========================================
    # Expression Type Checking
    # ==========================================

    def _mark_result_lift(self, expr: Optional[Expr], target: WType, force: bool = False) -> None:
        if expr is None:
            return
        target_id = self.interner.intern(target)
        source_entry = self.interner.get_entry(expr.inferred_type_id)
        target_entry = self.interner.get_entry(target_id)
        if source_entry.tag == target_entry.tag == "result":
            source_ok, source_error = source_entry.data
            target_ok, target_error = target_entry.data
            same_ok = source_ok == target_ok or self.interner.get_entry(source_ok).tag == "any" or self.interner.get_entry(target_ok).tag == "any"
            same_error = self.interner.is_error_channel_assignable(source_error, target_error)
            if same_ok and same_error:
                return
        if self.interner.get_entry(target_id).tag == "result" and expr.inferred_type_id != target_id:
            if force or source_entry.tag == "result" or isinstance(target, EnumType):
                expr.force_result_wrap_id = target_id

    def _check_payload(self, expr: Expr, expected: Optional[WType]) -> WType:
        previous = self.expected_type
        self.expected_type = expected
        try:
            actual = self._check_expr(expr)
        finally:
            self.expected_type = previous
        if expected is not None and is_assignable(actual, expected):
            self._mark_result_lift(expr, expected, force=True)
            return expected
        return actual

    def _builtin_arguments(self, type_: Optional[WType], name: str) -> List[WType]:
        if name == "Option" and isinstance(type_, OptionalType):
            return [type_.inner]
        if name == "Result" and isinstance(type_, ResultType):
            return [type_.ok, type_.err]
        if isinstance(type_, EnumType) and getattr(type_, "template_name", None) == name:
            return type_.type_args or []
        return []

    def _module_receiver(self, expression):
        if isinstance(expression, IdentExpr):
            symbol = self.current_scope.lookup_symbol(expression.name)
        elif isinstance(expression, MemberExpr):
            parent = self._module_receiver(expression.object)
            symbol = parent.scope.lookup_symbol(expression.property) if parent else None
        else:
            return None
        return symbol.type if symbol and isinstance(symbol.type, ModuleType) else None

    def _check_expr(self, expr: Expr, is_statement_context: bool = False, allow_module: bool = False) -> WType:
        wtype = self._check_expr_impl(expr, is_statement_context)
        if isinstance(wtype, ModuleType) and not allow_module:
            raise TypeError("Module namespaces cannot be used as runtime values", file=self.file,
                            line=expr.line, col=expr.col, code="W2003")
        if isinstance(expr, MemberExpr) and isinstance(wtype, FunctionType) and not getattr(expr, 'is_callee', False) and not hasattr(expr, 'function_reference') and not isinstance(getattr(expr.object, 'inferred_type', None), StructType) and not (isinstance(getattr(expr.object, 'inferred_type', None), ClassType) and expr.property in expr.object.inferred_type.fields):
            raise TypeError("Bound method values require an explicit lambda adapter", file=self.file, line=expr.line, col=expr.col, code="W2013")
        expr.inferred_type = wtype
        expr.inferred_type_id = self.interner.from_wtype(wtype)
        return wtype

    def _check_expr_impl(self, expr: Expr, is_statement_context: bool = False) -> WType:
        if isinstance(expr, LambdaExpr):
            from checker.ClosureConversion import convert_lambda
            return convert_lambda(self, expr)
        if isinstance(expr, IntLiteral):
            if expr.value > 9223372036854775807 or expr.value < -9223372036854775808:
                raise TypeError(
                    message=f"Integer literal {expr.value} exceeds 64-bit signed range [-9223372036854775808, 9223372036854775807]",
                    line=expr.line, col=expr.col, file=self.file, code="W0002"
                )
            return IntType
        if isinstance(expr, FloatLiteral):
            return FloatType
        if isinstance(expr, StringLiteral):
            return StrType
        if isinstance(expr, BoolLiteral):
            return BoolType
        if isinstance(expr, NoneLiteral):
            return NoneType

        if isinstance(expr, IdentExpr):
            if expr.name in ("None", "none"):
                return NoneType
            sym = self.current_scope.lookup_symbol(expr.name)
            if sym is not None:
                if sym.kind == 'builtin' and not getattr(expr, 'is_callee', False):
                    raise TypeError("Builtin function values require an explicit lambda adapter", file=self.file, line=expr.line, col=expr.col, code="W2013")
                expr.resolved_symbol = sym
                if sym.kind == "fn" and isinstance(sym.type, FunctionType):
                    expr.function_reference = sym.name
                return sym.type
            # Check if referencing an Enum type
            enum_type = self.current_scope.lookup_type(expr.name)
            if enum_type is not None and isinstance(enum_type, EnumType):
                return enum_type
            # Check if referencing an unqualified enum variant
            candidates = [t for t in self.global_scope.types.values()
                          if isinstance(t, EnumType) and expr.name in t.variants]
            if len(candidates) > 1:
                raise TypeError(f"Ambiguous enum variant '{expr.name}'; qualify its enum", file=self.file,
                                line=expr.line, col=expr.col, code="W1001")
            if candidates:
                enum_type = candidates[0]
                if enum_type.variant_payloads.get(expr.name):
                    raise TypeError(f"Variant '{expr.name}' requires a payload", file=self.file,
                                    line=expr.line, col=expr.col, code="W2005")
                expr.resolved_enum_name = enum_type.name
                return enum_type
            for tmpl in self.generic_enum_templates.values():
                var_names = [v.name if hasattr(v, "name") else str(v) for v in tmpl.ast_decl.variants]
                if expr.name in var_names:
                    if tmpl.name == "Option" and expr.name in ("None", "none"):
                        return NoneType
                    concrete_args = [TypeParamType(p.name if hasattr(p, "name") else str(p)) for p in tmpl.type_params]
                    return self._monomorphize_enum(tmpl, concrete_args, expr.line, expr.col)
            raise TypeError(
                message=f"Unknown identifier '{expr.name}'",
                line=expr.line,
                col=expr.col,
                file=self.file,
                code="T001"
            )

        if isinstance(expr, UnaryExpr):
            operand_t = self._check_expr(expr.operand)
            if expr.op == "-":
                if operand_t in (IntType, FloatType):
                    return operand_t
                raise TypeError(
                    message=f"Unary '-' operator expects number, found '{operand_t}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T005"
                )
            if expr.op == "not":
                if operand_t == BoolType:
                    return BoolType
                raise TypeError(
                    message=f"Unary 'not' operator expects bool, found '{operand_t}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T005"
                )

        if isinstance(expr, BinaryExpr):
            lhs_t = self._check_expr(expr.left)
            rhs_t = self._check_expr(expr.right)
            op = expr.op

            if op == "+":
                if lhs_t == IntType and rhs_t == IntType:
                    return IntType
                if lhs_t == FloatType and rhs_t == FloatType:
                    return FloatType
                if lhs_t == StrType and rhs_t == StrType:
                    return StrType
                raise TypeError(
                    message=f"Binary '+' cannot be applied to '{lhs_t}' and '{rhs_t}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T005"
                )

            if op in ("-", "*", "/"):
                if lhs_t == IntType and rhs_t == IntType:
                    return IntType
                if lhs_t == FloatType and rhs_t == FloatType:
                    return FloatType
                raise TypeError(
                    message=f"Binary '{op}' cannot be applied to '{lhs_t}' and '{rhs_t}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T005"
                )

            if op == "%":
                if lhs_t == IntType and rhs_t == IntType:
                    return IntType
                raise TypeError(
                    message=f"Operator '%' is only defined for integers, found '{lhs_t}' and '{rhs_t}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T005"
                )

            if op in ("==", "!="):
                def contains_function(type_, seen):
                    if id(type_) in seen:
                        return False
                    seen.add(id(type_))
                    if isinstance(type_, FunctionType):
                        return True
                    children = []
                    if isinstance(type_, ListType): children = [type_.element]
                    elif isinstance(type_, DictType): children = [type_.key, type_.value]
                    elif isinstance(type_, TupleType): children = type_.elements
                    elif isinstance(type_, OptionalType): children = [type_.inner]
                    elif isinstance(type_, ResultType): children = [type_.ok, type_.err]
                    elif isinstance(type_, StructType): children = list(type_.fields.values())
                    elif isinstance(type_, EnumType): children = [p for payload in type_.variant_payloads.values() for p in payload]
                    return any(contains_function(child, seen) for child in children)
                if contains_function(lhs_t, set()) or contains_function(rhs_t, set()):
                    raise TypeError("Function values do not support equality", file=self.file, line=expr.line, col=expr.col, code="W2001")
                if not is_assignable(lhs_t, rhs_t) and not is_assignable(rhs_t, lhs_t) \
                        and not _equality_compatible(lhs_t, rhs_t):
                    raise TypeError(
                        message=f"Cannot compare equality of different types '{lhs_t}' and '{rhs_t}'",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T005"
                    )
                return BoolType

            if op in ("<", "<=", ">", ">="):
                if lhs_t == IntType and rhs_t == IntType:
                    return BoolType
                if lhs_t == FloatType and rhs_t == FloatType:
                    return BoolType
                raise TypeError(
                    message=f"Relational comparisons are only defined for numbers, found '{lhs_t}' and '{rhs_t}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T005"
                )

            if op in ("and", "or"):
                if lhs_t == BoolType and rhs_t == BoolType:
                    return BoolType
                raise TypeError(
                    message=f"Logical '{op}' expects bool operands, found '{lhs_t}' and '{rhs_t}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T005"
                )

        if isinstance(expr, RangeExpr):
            start_t = self._check_expr(expr.start)
            end_t = self._check_expr(expr.end)
            if start_t != IntType or end_t != IntType:
                raise TypeError(
                    message=f"Range bounds must be integers, found '{start_t}' and '{end_t}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T005"
                )
            return ListType(IntType)

        if isinstance(expr, CoalesceExpr):
            lhs_t = self._check_expr(expr.left)
            opt_inner = None
            if isinstance(lhs_t, OptionalType):
                opt_inner = lhs_t.inner
            elif isinstance(lhs_t, EnumType) and getattr(lhs_t, "template_name", None) == "Option" and getattr(lhs_t, "type_args", None):
                opt_inner = lhs_t.type_args[0]
            elif lhs_t == NoneType:
                rhs_t = self._check_expr(expr.right)
                return rhs_t
            if opt_inner is None:
                raise TypeError(
                    message=f"Left operand of '??' must be an optional type (T?), found '{lhs_t}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T009"
                )
            rhs_t = self._check_payload(expr.right, opt_inner)
            if not is_assignable(rhs_t, opt_inner):
                raise TypeError(
                    message=f"Right operand of '??' type mismatch: expected '{opt_inner}', found '{rhs_t}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T003"
                )

            return opt_inner

        if isinstance(expr, PostfixTryExpr):
            operand_t = self._check_expr(expr.operand)
            if isinstance(operand_t, OptionalType) or (isinstance(operand_t, EnumType) and getattr(operand_t, "template_name", None) == "Option" and getattr(operand_t, "type_args", None)):
                opt_inner = operand_t.inner if isinstance(operand_t, OptionalType) else operand_t.type_args[0]
                is_ret_opt = isinstance(self.current_fn_ret_type, OptionalType) or (isinstance(self.current_fn_ret_type, EnumType) and getattr(self.current_fn_ret_type, "template_name", None) == "Option")
                if not is_ret_opt:
                    raise TypeError(
                        message=f"Cannot use '?' on optional in function returning non-optional type '{self.current_fn_ret_type}'",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T010"
                    )
                expr.propagation_kind = "optional"
                return opt_inner

            if isinstance(operand_t, ResultType) or (isinstance(operand_t, EnumType) and getattr(operand_t, "template_name", None) == "Result" and getattr(operand_t, "type_args", None) and len(operand_t.type_args) == 2):
                res_ok = operand_t.ok if isinstance(operand_t, ResultType) else operand_t.type_args[0]
                res_err = operand_t.err if isinstance(operand_t, ResultType) else operand_t.type_args[1]
                is_ret_res = isinstance(self.current_fn_ret_type, ResultType) or (isinstance(self.current_fn_ret_type, EnumType) and getattr(self.current_fn_ret_type, "template_name", None) == "Result")
                if not is_ret_res:
                    raise TypeError(
                        message=f"Cannot use '?' on result in function returning non-result type '{self.current_fn_ret_type}'",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T010"
                    )
                cur_err = self.current_fn_ret_type.err if isinstance(self.current_fn_ret_type, ResultType) else self.current_fn_ret_type.type_args[1]
                if not is_error_channel_assignable(res_err, cur_err):
                    raise TypeError(
                        message=f"Error type mismatch in '?' propagation: '{res_err}' is not covered by declared '{cur_err}'",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T010"
                    )
                expr.propagation_kind = "result"
                return res_ok

            raise TypeError(
                message=f"Operator '?' requires optional (T?) or result (T ! E), found '{operand_t}'",
                line=expr.line,
                col=expr.col,
                file=self.file,
                code="T009"
            )

        if isinstance(expr, ElseErrExpr):
            operand_t = self._check_expr(expr.operand)
            unwrapped_t: WType
            bound_err_t: Optional[WType] = None

            if isinstance(operand_t, ResultType) or (isinstance(operand_t, EnumType) and getattr(operand_t, "template_name", None) == "Result" and getattr(operand_t, "type_args", None) and len(operand_t.type_args) == 2):
                unwrapped_t = operand_t.ok if isinstance(operand_t, ResultType) else operand_t.type_args[0]
                bound_err_t = operand_t.err if isinstance(operand_t, ResultType) else operand_t.type_args[1]
            elif isinstance(operand_t, OptionalType) or (isinstance(operand_t, EnumType) and getattr(operand_t, "template_name", None) == "Option" and getattr(operand_t, "type_args", None)):
                if expr.err_name is not None:
                    raise TypeError(
                        message=f"Cannot bind error variable '{expr.err_name}' on optional type '{operand_t}'; use 'else {{ ... }}' or '??'",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T009"
                    )
                unwrapped_t = operand_t.inner if isinstance(operand_t, OptionalType) else operand_t.type_args[0]
            else:
                raise TypeError(
                    message=f"'else' handler requires result (T ! E) or optional (T?), found '{operand_t}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T009"
                )

            handler_scope = Scope(parent=self.current_scope)
            if expr.err_name is not None and bound_err_t is not None:
                handler_scope.define_symbol(
                    Symbol(expr.err_name, bound_err_t, is_mut=False, kind="var", line=expr.line, col=expr.col),
                    file=self.file
                )

            old_scope = self.current_scope
            self.current_scope = handler_scope
            try:
                for s in expr.handler.statements:
                    self._check_stmt(s)
                tail_t = self._check_expr(expr.handler.tail_expr) if expr.handler.tail_expr else None
            finally:
                self.current_scope = old_scope

            if not self._block_diverges(expr.handler):
                actual_handler_t = tail_t if tail_t is not None else UnitType
                if not is_assignable(actual_handler_t, unwrapped_t):
                    raise TypeError(
                        message=f"'else' handler must diverge (return/break/continue) or evaluate to '{unwrapped_t}', found '{actual_handler_t}'",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T003"
                    )

            return unwrapped_t

        if isinstance(expr, ThisExpr):
            if self.current_class is None:
                raise TypeError(
                    message="'this' can only be used inside a class method",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="W1004"
                )
            return self.current_class

        if isinstance(expr, SuperExpr):
            if self.current_class is None:
                raise TypeError(
                    message="'super' can only be used inside a class method",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="W1004"
                )
            if self.current_class.superclass is None:
                raise TypeError(
                    message=f"Class '{self.current_class.name}' has no superclass",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="W1004"
                )
            return self.current_class.superclass

        if isinstance(expr, NewExpr):
            if "." in expr.class_name and not getattr(expr, "type_args", None):
                expr.class_name = self._resolve_type_node(NamedType(expr.class_name, expr.line, expr.col)).name
            if getattr(expr, 'type_args', None):
                expression_type = self._resolve_type_node(GenericType(expr.class_name, expr.type_args, expr.line, expr.col))
                expr.class_name = expression_type.name
                expr.type_args = None
            class_t = self.current_scope.lookup_type(expr.class_name)
            if class_t is None or not isinstance(class_t, ClassType):
                raise TypeError(
                    message=f"Unknown class type '{expr.class_name}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T002"
                )
            return self._check_class_instantiation(class_t, expr.args, expr.line, expr.col)

        if isinstance(expr, AssignmentExpr):
            # W accepts assignment as an expression, which makes `a = b = c = 1` legal.
            # The HIR has no assignment expression node, so the lowering synthesises a
            # temporary per level; that is verified for one nested level, and deeper
            # chains are rejected here rather than miscompiled.
            depth = 1
            inner = expr.value
            while isinstance(inner, AssignmentExpr):
                depth += 1
                inner = inner.value
            if depth > 2:
                raise TypeError(
                    message=f"Chained assignment nests {depth} levels; at most 2 are supported "
                            f"(split it into separate statements)",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="W2013",
                )

            # Target validation
            val_t = self._check_expr(expr.value)

            if isinstance(expr.target, IdentExpr):
                sym = self.current_scope.lookup_symbol(expr.target.name)
                if sym is None:
                    raise TypeError(
                        message=f"Unknown identifier '{expr.target.name}'",
                        line=expr.target.line,
                        col=expr.target.col,
                        file=self.file,
                        code="T001"
                    )
                if not sym.is_mut:
                    raise TypeError(
                        message=f"Cannot assign to immutable binding '{sym.name}'",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T004"
                    )
                if not is_assignable(val_t, sym.type):
                    raise TypeError(
                        message=f"Type mismatch: cannot assign value of type '{val_t}' to variable '{sym.name}' of type '{sym.type}'",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T003"
                    )
                self._mark_result_lift(expr.value, sym.type, force=True)
                expr.target.inferred_type = sym.type
                expr.target.inferred_type_id = self.interner.from_wtype(sym.type)
                return sym.type

            if isinstance(expr.target, IndexExpr):
                # Target value root must be a mutable binding (unless rooted in a reference-type class)
                sym = self._find_value_root_symbol(expr.target.object)
                if sym and not sym.is_mut:
                    raise TypeError(
                        message=f"Cannot mutate elements of immutable binding '{sym.name}'",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T004"
                    )
                obj_t = self._check_expr(expr.target.object)
                idx_t = self._check_expr(expr.target.index)
                if isinstance(obj_t, ListType):
                    if idx_t != IntType:
                        raise TypeError(
                            message=f"List index must be int, found '{idx_t}'",
                            line=expr.target.index.line,
                            col=expr.target.index.col,
                            file=self.file,
                            code="T003"
                        )
                    if not is_assignable(val_t, obj_t.element):
                        raise TypeError(
                            message=f"Cannot assign '{val_t}' to list of '{obj_t.element}'",
                            line=expr.line,
                            col=expr.col,
                            file=self.file,
                            code="T003"
                        )
                    self._mark_result_lift(expr.value, obj_t.element, force=True)
                    expr.target.inferred_type = obj_t.element
                    expr.target.inferred_type_id = self.interner.from_wtype(obj_t.element)
                    return obj_t.element

                if isinstance(obj_t, DictType):
                    if not is_assignable(idx_t, obj_t.key):
                        raise TypeError(
                            message=f"Dict key type mismatch: expected '{obj_t.key}', found '{idx_t}'",
                            line=expr.target.index.line,
                            col=expr.target.index.col,
                            file=self.file,
                            code="T003"
                        )
                    if not is_assignable(val_t, obj_t.value):
                        raise TypeError(
                            message=f"Dict value type mismatch: expected '{obj_t.value}', found '{val_t}'",
                            line=expr.line,
                            col=expr.col,
                            file=self.file,
                            code="T003"
                        )
                    self._mark_result_lift(expr.value, obj_t.value, force=True)
                    expr.target.inferred_type = obj_t.value
                    expr.target.inferred_type_id = self.interner.from_wtype(obj_t.value)
                    return obj_t.value

                raise TypeError(
                    message=f"Cannot assign to index of type '{obj_t}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T005"
                )


            if isinstance(expr.target, MemberExpr):
                obj_t = self._check_expr(expr.target.object)
                if isinstance(obj_t, ClassType):
                    f_info = obj_t.fields.get(expr.target.property)
                    if f_info is None:
                        raise TypeError(
                            message=f"Class '{obj_t.name}' has no field '{expr.target.property}'",
                            line=expr.target.line,
                            col=expr.target.col,
                            file=self.file,
                            code="T012"
                        )
                    if not f_info.is_public and (self.current_class is None or self.current_class.name != f_info.owner_class):
                        raise TypeError(
                            message=f"Cannot access private field '{expr.target.property}' of class '{f_info.owner_class}'",
                            line=expr.target.line,
                            col=expr.target.col,
                            file=self.file,
                            code="W3002"
                        )
                    if not is_assignable(val_t, f_info.type):
                        raise TypeError(
                            message=f"Type mismatch on field '{expr.target.property}': expected '{f_info.type}', found '{val_t}'",
                            line=expr.line,
                            col=expr.col,
                            file=self.file,
                            code="T003"
                        )
                    self._mark_result_lift(expr.value, f_info.type, force=True)
                    expr.target.inferred_type = f_info.type
                    expr.target.inferred_type_id = self.interner.from_wtype(f_info.type)
                    return f_info.type

                sym = self._find_value_root_symbol(expr.target.object)
                if sym and not sym.is_mut:
                    raise TypeError(
                        message=self._immutable_binding_message(sym, "mutate a field"),
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T004"
                    )
                if not isinstance(obj_t, StructType):
                    raise TypeError(
                        message=f"Cannot assign to field of non-struct '{obj_t}'",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T012"
                    )
                if expr.target.property not in obj_t.fields:
                    raise TypeError(
                        message=f"Struct '{obj_t.name}' has no field '{expr.target.property}'",
                        line=expr.target.line,
                        col=expr.target.col,
                        file=self.file,
                        code="T012"
                    )
                field_t = obj_t.fields[expr.target.property]
                if not is_assignable(val_t, field_t):
                    raise TypeError(
                        message=f"Type mismatch on field '{expr.target.property}': expected '{field_t}', found '{val_t}'",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T003"
                    )
                self._mark_result_lift(expr.value, field_t, force=True)
                expr.target.inferred_type = field_t
                expr.target.inferred_type_id = self.interner.from_wtype(field_t)
                return field_t

            raise TypeError(
                message="Invalid assignment target",
                line=expr.line,
                col=expr.col,
                file=self.file,
                code="W2002"
            )

        if isinstance(expr, MemberExpr):
            # Enum variant access: Enum.Variant
            if isinstance(expr.object, IdentExpr):
                if expr.object.name == "Option" and expr.property in ("None", "none"):
                    return NoneType
                enum_t = self.current_scope.lookup_type(expr.object.name)
                if isinstance(enum_t, EnumType):
                    if expr.property not in enum_t.variants:
                        raise TypeError(
                            message=f"Enum '{enum_t.name}' has no variant '{expr.property}'",
                            line=expr.line,
                            col=expr.col,
                            file=self.file,
                            code="T001"
                        )
                    if enum_t.variant_payloads.get(expr.property):
                        raise TypeError(f"Variant '{expr.property}' requires a payload", file=self.file,
                                        line=expr.line, col=expr.col, code="W2005")
                    return enum_t
                if expr.object.name in self.generic_enum_templates:
                    tmpl = self.generic_enum_templates[expr.object.name]
                    var_names = [v.name if hasattr(v, "name") else str(v) for v in tmpl.ast_decl.variants]
                    if expr.property not in var_names:
                        raise TypeError(
                            message=f"Generic enum '{tmpl.name}' has no variant '{expr.property}'",
                            line=expr.line,
                            col=expr.col,
                            file=self.file,
                            code="T001"
                        )
                    if tmpl.name == "Option" and expr.property in ("None", "none"):
                        return NoneType
                    ctx_t = self.expected_type
                    if isinstance(ctx_t, EnumType) and getattr(ctx_t, "template_name", None) == tmpl.name and ctx_t.type_args:
                        concrete_args = list(ctx_t.type_args)
                    else:
                        concrete_args = [TypeParamType(p.name if hasattr(p, "name") else str(p)) for p in tmpl.type_params]
                    enum_t = self._monomorphize_enum(tmpl, concrete_args, expr.line, expr.col)
                    expr.object.name = enum_t.name
                    return enum_t

            obj_t = self._check_expr(expr.object, allow_module=True)
            if isinstance(obj_t, ClassType):
                if expr.property == "init" and isinstance(expr.object, SuperExpr):
                    curr_s: Optional[ClassType] = obj_t
                    while curr_s is not None:
                        if curr_s.init_type is not None:
                            return curr_s.init_type
                        curr_s = curr_s.superclass
                    return FunctionType(params=[], ret=UnitType)

                f_info = obj_t.fields.get(expr.property)
                if f_info is not None:
                    if not f_info.is_public and (self.current_class is None or self.current_class.name != f_info.owner_class):
                        raise TypeError(
                            message=f"Cannot access private field '{expr.property}' of class '{f_info.owner_class}'",
                            line=expr.line,
                            col=expr.col,
                            file=self.file,
                            code="W3002"
                        )
                    return f_info.type

                m_info = obj_t.methods.get(expr.property)
                if m_info is not None:
                    if not m_info.is_public and (self.current_class is None or self.current_class.name != m_info.owner_class):
                        raise TypeError(
                            message=f"Cannot access private method '{expr.property}' of class '{m_info.owner_class}'",
                            line=expr.line,
                            col=expr.col,
                            file=self.file,
                            code="W3002"
                        )
                    return m_info.fn_type

                raise TypeError(
                    message=f"Class '{obj_t.name}' has no member '{expr.property}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T012"
                )

            if isinstance(obj_t, InterfaceType):
                if expr.property in obj_t.methods:
                    return obj_t.methods[expr.property]
                raise TypeError(
                    message=f"Interface '{obj_t.name}' has no method '{expr.property}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T012"
                )

            if isinstance(obj_t, StructType):
                if expr.property not in obj_t.fields:
                    raise TypeError(
                        message=f"Struct '{obj_t.name}' has no field '{expr.property}'",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T012"
                    )
                return obj_t.fields[expr.property]

            if isinstance(obj_t, ListType):
                if expr.property == "append":
                    return FunctionType([obj_t.element], UnitType, is_mutating=True)
                if expr.property == "pop":
                    return FunctionType([], obj_t.element, is_mutating=True)
                if expr.property == "clear":
                    return FunctionType([], UnitType, is_mutating=True)

            if isinstance(obj_t, DictType):
                if expr.property == "get":
                    return FunctionType([obj_t.key], OptionalType(obj_t.value))
                if expr.property == "keys":
                    return FunctionType([], ListType(obj_t.key))
                if expr.property == "values":
                    return FunctionType([], ListType(obj_t.value))

            if isinstance(obj_t, ModuleType):
                sym = obj_t.scope.lookup_symbol(expr.property)
                if sym is not None:
                    expr.resolved_module_member = sym.name
                    expr.resolved_symbol = sym
                    if sym.kind == 'fn' and isinstance(sym.type, FunctionType):
                        expr.function_reference = sym.name
                    return sym.type
                t_def = obj_t.scope.lookup_type(expr.property)
                if t_def is not None:
                    return t_def
                raise TypeError(
                    message=f"Module '{obj_t.name}' has no exported member '{expr.property}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T001"
                )

            if isinstance(obj_t, AnyType):
                return AnyType()

            raise TypeError(
                message=f"Cannot access property '{expr.property}' on type '{obj_t}'",
                line=expr.line,
                col=expr.col,
                file=self.file,
                code="T012"
            )


        if isinstance(expr, IndexExpr):
            obj_t = self._check_expr(expr.object)
            idx_t = self._check_expr(expr.index)
            if isinstance(obj_t, ListType):
                if idx_t != IntType:
                    raise TypeError(
                        message=f"List index must be int, found '{idx_t}'",
                        line=expr.index.line,
                        col=expr.index.col,
                        file=self.file,
                        code="T003"
                    )
                return obj_t.element

            if obj_t == StrType:
                if idx_t != IntType:
                    raise TypeError(
                        message=f"String index must be int, found '{idx_t}'",
                        line=expr.index.line,
                        col=expr.index.col,
                        file=self.file,
                        code="T003"
                    )
                return StrType
            if isinstance(obj_t, DictType):
                if not is_assignable(idx_t, obj_t.key):
                    raise TypeError(
                        message=f"Dict key type mismatch: expected '{obj_t.key}', found '{idx_t}'",
                        line=expr.index.line,
                        col=expr.index.col,
                        file=self.file,
                        code="T003"
                    )
                # `d[k]` yields V and panics with W4002 when the key is absent (SPEC
                # 10.2). The optional form is `d.get(k)`, which returns V?. Returning
                # V? here forced every dictionary read through unwrapping ceremony and
                # made `d[k].append(x)` impossible to write.
                return obj_t.value
            raise TypeError(
                message=f"Cannot index type '{obj_t}'",
                line=expr.line,
                col=expr.col,
                file=self.file,
                code="T005"
            )

        if isinstance(expr, CallExpr):
            expr.callee.is_callee = True
            if isinstance(expr.callee, IdentExpr) and expr.type_args:
                template = self.current_scope.lookup_type(expr.callee.name)
                if isinstance(template, GenericOopTemplate):
                    type_ = specialize_oop(template, [self._resolve_type_node(a) for a in expr.type_args], expr.line, expr.col)
                    expr.callee.name = type_.name
                    expr.type_args = None
            if isinstance(expr.callee, IdentExpr) and self.current_scope.lookup_symbol(expr.callee.name) is None:
                variants = [t for t in self.global_scope.types.values()
                            if isinstance(t, EnumType) and not getattr(t, "template_name", None)
                            and expr.callee.name in t.variants]
                if len(variants) > 1:
                    raise TypeError("Ambiguous enum constructor; qualify its enum", file=self.file,
                                    line=expr.line, col=expr.col, code="W1001")
                if variants:
                    expr.callee = MemberExpr(IdentExpr(variants[0].name, expr.line, expr.col),
                                             expr.callee.name, expr.line, expr.col)
            # Support generic function calls and generic struct constructors
            callee_t: Optional[WType] = None
            if isinstance(expr.callee, MemberExpr):
                module_type = self._module_receiver(expr.callee.object)
                if isinstance(module_type, ModuleType):
                    type_template = module_type.scope.lookup_type(expr.callee.property)
                    if isinstance(type_template, GenericOopTemplate):
                        if not expr.type_args:
                            raise TypeError("Generic class constructor needs explicit type arguments", file=self.file, line=expr.line, col=expr.col, code="W2001")
                        specialized = specialize_oop(type_template, [self._resolve_type_node(a) for a in expr.type_args], expr.line, expr.col)
                        if self.global_scope.lookup_type(specialized.name) is None:
                            self.global_scope.define_type(specialized.name, specialized, file=self.file)
                        expr.callee = IdentExpr(specialized.name, expr.line, expr.col)
                        expr.type_args = None
                        return self._check_expr(expr)
                    symbol = module_type.scope.lookup_symbol(expr.callee.property)
                    if symbol and isinstance(symbol.type, GenericFnTemplate):
                        template = symbol.type
                        if expr.type_args:
                            concrete_args = [self._resolve_type_node(argument) for argument in expr.type_args]
                        else:
                            if len(expr.args) != len(template.ast_decl.params):
                                raise TypeError("Generic module function argument count mismatch", file=self.file,
                                                line=expr.line, col=expr.col, code="W2005")
                            bindings = {}
                            parameters = {parameter.name for parameter in template.type_params}
                            for parameter, argument in zip(template.ast_decl.params, expr.args):
                                self._unify_type(parameter.type_ann, self._check_expr(argument), parameters, bindings)
                            if any(parameter.name not in bindings for parameter in template.type_params):
                                raise TypeError("Cannot infer imported generic function arguments", file=self.file,
                                                line=expr.line, col=expr.col, code="W2003")
                            concrete_args = self._concrete_type_args(template, bindings)
                        unit = module_type.checked_module
                        specialized = unit.checker._monomorphize_fn(template, concrete_args, expr.line, expr.col)
                        self.session.refresh_specializations(unit)
                        expr.callee = IdentExpr(specialized.name, line=expr.callee.line, col=expr.callee.col)
                        expr.type_args = []
                        callee_t = specialized.type
            if isinstance(expr.callee, IdentExpr):
                callee_name = expr.callee.name
                symbol = self.current_scope.lookup_symbol(callee_name)
                if callee_name in ("weak", "upgrade") and symbol and symbol.kind == "builtin":
                    if len(expr.args) != 1 or expr.type_args:
                        raise TypeError(f"{callee_name} expects one argument and no type arguments",
                                        line=expr.line, col=expr.col, file=self.file, code="W2005")
                    argument = self._check_expr(expr.args[0])
                    if callee_name == "weak" and isinstance(argument, ClassType):
                        return WeakType(argument)
                    if callee_name == "upgrade" and isinstance(argument, WeakType):
                        return OptionalType(argument.target)
                    raise TypeError(f"Invalid argument type '{argument}' for {callee_name}",
                                    line=expr.line, col=expr.col, file=self.file, code="W2003")
                if callee_name in self.generic_fn_templates:
                    template = self.generic_fn_templates[callee_name]
                    if expr.type_args:
                        concrete_args = [self._resolve_type_node(a) for a in expr.type_args]
                    else:
                        if len(expr.args) != len(template.ast_decl.params):
                            raise TypeError(
                                message=f"Expected {len(template.ast_decl.params)} arguments for generic function '{callee_name}', found {len(expr.args)}",
                                line=expr.line,
                                col=expr.col,
                                file=self.file,
                                code="T015"
                            )
                        type_params_set = {p.name if hasattr(p, "name") else str(p) for p in template.type_params}
                        bindings: Dict[str, WType] = {}
                        for p_decl, a_expr in zip(template.ast_decl.params, expr.args):
                            a_type = self._check_expr(a_expr)
                            if not self._unify_type(p_decl.type_ann, a_type, type_params_set, bindings):
                                raise TypeError(
                                    message=f"Conflicting type inference for generic function '{callee_name}': cannot unify '{a_type}'",
                                    line=a_expr.line,
                                    col=a_expr.col,
                                    file=self.file,
                                    code="W2001"
                                )
                        for p in template.type_params:
                            p_name = p.name if hasattr(p, "name") else str(p)
                            if p_name not in bindings:
                                raise TypeError(
                                    message=f"Could not infer type parameter '{p_name}' for generic function '{callee_name}'",
                                    line=expr.line,
                                    col=expr.col,
                                    file=self.file,
                                    code="T003"
                                )
                        concrete_args = self._concrete_type_args(template, bindings)

                    fn_sym = self._monomorphize_fn(template, concrete_args, expr.line, expr.col)
                    expr.callee.name = fn_sym.name
                    expr.type_args = []
                    callee_t = fn_sym.type

                elif callee_name in self.generic_struct_templates:
                    template = self.generic_struct_templates[callee_name]
                    if expr.type_args:
                        concrete_args = [self._resolve_type_node(a) for a in expr.type_args]
                    else:
                        if len(expr.args) != len(template.ast_decl.fields):
                            raise TypeError(
                                message=f"Expected {len(template.ast_decl.fields)} arguments for struct constructor '{callee_name}', found {len(expr.args)}",
                                line=expr.line,
                                col=expr.col,
                                file=self.file,
                                code="T015"
                            )
                        type_params_set = {p.name if hasattr(p, "name") else str(p) for p in template.type_params}
                        bindings = {}
                        for f_decl, a_expr in zip(template.ast_decl.fields, expr.args):
                            a_type = self._check_expr(a_expr)
                            if not self._unify_type(f_decl.type_ann, a_type, type_params_set, bindings):
                                raise TypeError(
                                    message=f"Conflicting type inference for struct constructor '{callee_name}': cannot unify '{a_type}'",
                                    line=a_expr.line,
                                    col=a_expr.col,
                                    file=self.file,
                                    code="W2001"
                                )

                        for p in template.type_params:
                            p_name = p.name if hasattr(p, "name") else str(p)
                            if p_name not in bindings:
                                raise TypeError(
                                    message=f"Could not infer type parameter '{p_name}' for struct constructor '{callee_name}'",
                                    line=expr.line,
                                    col=expr.col,
                                    file=self.file,
                                    code="T003"
                                )
                        concrete_args = self._concrete_type_args(template, bindings)

                    struct_t = self._monomorphize_struct(template, concrete_args, expr.line, expr.col)
                    expr.callee.name = struct_t.name
                    expr.type_args = []
                    ctor_sym = self.global_scope.lookup_symbol(struct_t.name)
                    callee_t = ctor_sym.type if ctor_sym else FunctionType([struct_t.fields[f.name] for f in template.ast_decl.fields], struct_t)

                elif callee_name == "Some":
                    if len(expr.args) != 1:
                        raise TypeError(
                            message=f"Constructor 'Some' expects 1 argument, found {len(expr.args)}",
                            line=expr.line,
                            col=expr.col,
                            file=self.file,
                            code="T015"
                        )
                    context = self._builtin_arguments(self.expected_type or self.current_fn_ret_type, "Option")
                    arg_t = self._check_payload(expr.args[0], context[0] if context else None)
                    template = self.generic_enum_templates["Option"]
                    opt_t = self._monomorphize_enum(template, [arg_t], expr.line, expr.col)
                    return opt_t

                elif callee_name == "Ok":
                    if len(expr.args) != 1:
                        raise TypeError(
                            message=f"Constructor 'Ok' expects 1 argument, found {len(expr.args)}",
                            line=expr.line,
                            col=expr.col,
                            file=self.file,
                            code="T015"
                        )
                    ctx_t = self.expected_type or self.current_fn_ret_type
                    context = self._builtin_arguments(ctx_t, "Result")
                    arg_t = self._check_payload(expr.args[0], context[0] if context else None)
                    err_t = AnyType()
                    if isinstance(ctx_t, ResultType):
                        err_t = ctx_t.err
                    elif isinstance(ctx_t, EnumType) and getattr(ctx_t, "template_name", None) == "Result" and ctx_t.type_args and len(ctx_t.type_args) == 2:
                        err_t = ctx_t.type_args[1]
                    template = self.generic_enum_templates["Result"]
                    res_t = self._monomorphize_enum(template, [arg_t, err_t], expr.line, expr.col)
                    return res_t

                elif callee_name == "Err":
                    if len(expr.args) != 1:
                        raise TypeError(
                            message=f"Constructor 'Err' expects 1 argument, found {len(expr.args)}",
                            line=expr.line,
                            col=expr.col,
                            file=self.file,
                            code="T015"
                        )
                    ctx_t = self.expected_type or self.current_fn_ret_type
                    context = self._builtin_arguments(ctx_t, "Result")
                    err_t = self._check_payload(expr.args[0], context[1] if context else None)
                    ok_t = AnyType()
                    if isinstance(ctx_t, ResultType):
                        ok_t = ctx_t.ok
                    elif isinstance(ctx_t, EnumType) and getattr(ctx_t, "template_name", None) == "Result" and ctx_t.type_args and len(ctx_t.type_args) == 2:
                        ok_t = ctx_t.type_args[0]
                    template = self.generic_enum_templates["Result"]
                    res_t = self._monomorphize_enum(template, [ok_t, err_t], expr.line, expr.col)
                    return res_t

                else:
                    found_tmpl = None
                    found_var = None
                    for tmpl_name, tmpl in self.generic_enum_templates.items():
                        for v in tmpl.ast_decl.variants:
                            v_name = v.name if hasattr(v, "name") else str(v)
                            if v_name == callee_name:
                                found_tmpl = tmpl
                                found_var = v
                                break
                        if found_tmpl:
                            break
                    if found_tmpl and found_var:
                        payload_types = getattr(found_var, "payload_types", [])
                        if len(expr.args) != len(payload_types):
                            raise TypeError(
                                message=f"Variant '{callee_name}' expects {len(payload_types)} arguments, found {len(expr.args)}",
                                line=expr.line,
                                col=expr.col,
                                file=self.file,
                                code="T015"
                            )
                        type_params_set = {p.name if hasattr(p, "name") else str(p) for p in found_tmpl.type_params}
                        bindings = {}
                        for pt, a_expr in zip(payload_types, expr.args):
                            a_type = self._check_expr(a_expr)
                            self._unify_type(pt, a_type, type_params_set, bindings)
                        for p in found_tmpl.type_params:
                            p_name = p.name if hasattr(p, "name") else str(p)
                            if p_name not in bindings:
                                raise TypeError(
                                    message=f"Could not infer type parameter '{p_name}' for enum constructor '{callee_name}'",
                                    line=expr.line,
                                    col=expr.col,
                                    file=self.file,
                                    code="T003"
                                )
                        concrete_args = self._concrete_type_args(found_tmpl, bindings)
                        enum_t = self._monomorphize_enum(found_tmpl, concrete_args, expr.line, expr.col)
                        expr.callee = MemberExpr(IdentExpr(enum_t.name, line=expr.line, col=expr.col), callee_name, line=expr.line, col=expr.col)
                        expr.type_args = []
                        return enum_t

                    if expr.type_args:
                        symbol = self.current_scope.lookup_symbol(callee_name)
                        alternative = getattr(expr, 'index_alternative', None)
                        if symbol and isinstance(symbol.type, (ListType, DictType)) and alternative is not None:
                            expr.callee = IndexExpr(expr.callee, alternative, expr.line, expr.col)
                            expr.type_args = None
                            expr.index_alternative = None
                            return self._check_expr(expr)
                        raise TypeError(
                            message=f"Symbol '{callee_name}' is not a generic function or struct",
                            line=expr.line,
                            col=expr.col,
                            file=self.file,
                            code="T002"
                        )

                    if self.current_scope.lookup_symbol(expr.callee.name) is None:
                        maybe_cls = self.current_scope.lookup_type(expr.callee.name)
                        if isinstance(maybe_cls, ClassType):
                            return self._check_class_instantiation(maybe_cls, expr.args, expr.line, expr.col)

            if isinstance(expr.callee, MemberExpr) and isinstance(expr.callee.object, IdentExpr) and expr.callee.object.name in self.generic_enum_templates:
                template = self.generic_enum_templates[expr.callee.object.name]
                variant_name = expr.callee.property
                var_decl = next((v for v in template.ast_decl.variants if (v.name if hasattr(v, "name") else str(v)) == variant_name), None)
                if var_decl is None:
                    raise TypeError(
                        message=f"Generic enum '{template.name}' has no variant '{variant_name}'",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T001"
                    )
                payload_types = getattr(var_decl, "payload_types", [])
                if len(expr.args) != len(payload_types):
                    raise TypeError(
                        message=f"Variant '{variant_name}' expects {len(payload_types)} arguments, found {len(expr.args)}",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T015"
                    )
                if expr.type_args:
                    concrete_args = [self._resolve_type_node(a) for a in expr.type_args]
                else:
                    type_params_set = {p.name if hasattr(p, "name") else str(p) for p in template.type_params}
                    bindings = {}
                    ctx_t = self.expected_type or self.current_fn_ret_type
                    context_args = self._builtin_arguments(ctx_t, template.name)
                    context_types = dict(zip([p.name for p in template.type_params], context_args))
                    for pt, a_expr in zip(payload_types, expr.args):
                        expected = None
                        if isinstance(pt, NamedType):
                            expected = context_types.get(pt.name)
                        elif isinstance(pt, GenericType):
                            subst_pt = self._substitute_type_node(pt, context_types)
                            try:
                                expected = self._resolve_type_node(subst_pt)
                            except Exception:
                                expected = None
                        a_type = self._check_payload(a_expr, expected)
                        self._unify_type(pt, a_type, type_params_set, bindings)
                    if template.name == "Result":
                        if "E" not in bindings:
                            if isinstance(ctx_t, ResultType):
                                bindings["E"] = ctx_t.err
                            elif isinstance(ctx_t, EnumType) and getattr(ctx_t, "template_name", None) == "Result" and ctx_t.type_args and len(ctx_t.type_args) == 2:
                                bindings["E"] = ctx_t.type_args[1]
                            else:
                                bindings["E"] = AnyType()
                        if "T" not in bindings:
                            if isinstance(ctx_t, ResultType):
                                bindings["T"] = ctx_t.ok
                            elif isinstance(ctx_t, EnumType) and getattr(ctx_t, "template_name", None) == "Result" and ctx_t.type_args and len(ctx_t.type_args) == 2:
                                bindings["T"] = ctx_t.type_args[0]
                            else:
                                bindings["T"] = AnyType()
                    elif template.name == "Option":
                        if "T" not in bindings:
                            if isinstance(ctx_t, OptionalType):
                                bindings["T"] = ctx_t.inner
                            elif isinstance(ctx_t, EnumType) and getattr(ctx_t, "template_name", None) == "Option" and ctx_t.type_args and len(ctx_t.type_args) == 1:
                                bindings["T"] = ctx_t.type_args[0]
                            else:
                                bindings["T"] = AnyType()

                    for p in template.type_params:
                        p_name = p.name if hasattr(p, "name") else str(p)
                        if p_name not in bindings:
                            raise TypeError(
                                message=f"Could not infer type parameter '{p_name}' for enum constructor '{template.name}.{variant_name}'",
                                line=expr.line,
                                col=expr.col,
                                file=self.file,
                                code="T003"
                            )
                    concrete_args = self._concrete_type_args(template, bindings)

                enum_t = self._monomorphize_enum(template, concrete_args, expr.line, expr.col)
                expr.callee.object.name = enum_t.name
                expr.type_args = []
                return enum_t

            if isinstance(expr.callee, MemberExpr) and isinstance(expr.callee.object, IdentExpr):
                enum_t = self.current_scope.lookup_type(expr.callee.object.name)
                if isinstance(enum_t, EnumType):
                    variant_name = expr.callee.property
                    if variant_name not in enum_t.variants:
                        raise TypeError(
                            message=f"Enum '{enum_t.name}' has no variant '{variant_name}'",
                            line=expr.line,
                            col=expr.col,
                            file=self.file,
                            code="T001"
                        )
                    expected_payloads = enum_t.variant_payloads.get(variant_name, [])
                    if len(expr.args) != len(expected_payloads):
                        raise TypeError(
                            message=f"Variant '{variant_name}' expects {len(expected_payloads)} arguments, found {len(expr.args)}",
                            line=expr.line,
                            col=expr.col,
                            file=self.file,
                            code="T015"
                        )
                    for i, (a_expr, p_type) in enumerate(zip(expr.args, expected_payloads)):
                        a_type = self._check_expr(a_expr)
                        if not is_assignable(a_type, p_type):
                            raise TypeError(
                                message=f"Argument {i + 1} type mismatch: expected '{p_type}', found '{a_type}'",
                                line=a_expr.line,
                                col=a_expr.col,
                                file=self.file,
                                code="T003"
                            )
                    return enum_t

            # Mutating method check on receiver (transitive across value-type paths)
            if callee_t is None:
                if isinstance(expr.callee, MemberExpr):
                    callee_t = self._check_expr(expr.callee)
                    if isinstance(callee_t, FunctionType) and callee_t.is_mutating:
                        sym = self._find_value_root_symbol(expr.callee.object)
                        if sym and not sym.is_mut:
                            raise TypeError(
                                message=self._immutable_binding_message(sym, f"call mutating method '{expr.callee.property}'"),
                                line=expr.line,
                                col=expr.col,
                                file=self.file,
                                code="T004"
                            )
                else:
                    callee_t = self._check_expr(expr.callee)
            if isinstance(callee_t, AnyType):
                for a in expr.args:
                    self._check_expr(a)
                return AnyType()

            if not isinstance(callee_t, FunctionType):
                alternative = getattr(expr, 'index_alternative', None)
                if alternative is not None and isinstance(callee_t, (ListType, DictType)):
                    expr.callee = IndexExpr(expr.callee, alternative, expr.line, expr.col)
                    expr.type_args = None
                    expr.index_alternative = None
                    return self._check_expr(expr)
                raise TypeError(
                    message=f"Cannot call non-function of type '{callee_t}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T015"
                )


            if not isinstance(expr.callee, (IdentExpr, MemberExpr)):
                expr.indirect_call = True
            elif isinstance(expr.callee, IdentExpr):
                symbol = self.current_scope.lookup_symbol(expr.callee.name)
                expr.indirect_call = symbol is not None and symbol.kind not in ("fn", "builtin")

            if isinstance(expr.callee, MemberExpr):
                receiver_type = getattr(expr.callee.object, 'inferred_type', None)
                if isinstance(receiver_type, StructType) or (isinstance(receiver_type, ClassType) and expr.callee.property in receiver_type.fields):
                    expr.indirect_call = True

            # Special built-in checks
            if isinstance(expr.callee, IdentExpr):
                name = expr.callee.name
                if name == "len":
                    if len(expr.args) != 1:
                        raise TypeError(message="len() takes exactly 1 argument", line=expr.line, col=expr.col, file=self.file, code="T015")
                    a_t = self._check_expr(expr.args[0])
                    if not (isinstance(a_t, (ListType, DictType)) or a_t == StrType):
                        raise TypeError(message=f"len() expects list, dict, or str, found '{a_t}'", line=expr.line, col=expr.col, file=self.file, code="T003")
                    return IntType

                if name == "str":
                    if len(expr.args) != 1:
                        raise TypeError(message="str() takes exactly 1 argument", line=expr.line, col=expr.col, file=self.file, code="T015")
                    a_t = self._check_expr(expr.args[0])
                    if a_t not in (IntType, FloatType, BoolType, StrType):
                        raise TypeError(message=f"str() expects int, float, bool, or str, found '{a_t}'", line=expr.line, col=expr.col, file=self.file, code="T003")
                    return StrType

                if name == "int":
                    if len(expr.args) != 1:
                        raise TypeError(message="int() takes exactly 1 argument", line=expr.line, col=expr.col, file=self.file, code="T015")
                    a_t = self._check_expr(expr.args[0])
                    if a_t not in (IntType, FloatType, StrType):
                        raise TypeError(message=f"int() expects int, float, or str, found '{a_t}'", line=expr.line, col=expr.col, file=self.file, code="T003")
                    return IntType

                if name == "float":
                    if len(expr.args) != 1:
                        raise TypeError(message="float() takes exactly 1 argument", line=expr.line, col=expr.col, file=self.file, code="T015")
                    a_t = self._check_expr(expr.args[0])
                    if a_t not in (IntType, FloatType, StrType):
                        raise TypeError(message=f"float() expects int, float, or str, found '{a_t}'", line=expr.line, col=expr.col, file=self.file, code="T003")
                    return FloatType

                if name == "slice":
                    # SPEC 11.1: slice(x, a, b) works for str and for list[T], and
                    # preserves the container kind. Each case is checked explicitly
                    # because the result type depends on the argument type.
                    if len(expr.args) != 3:
                        raise TypeError(message="slice() takes exactly 3 arguments (value, start, end)",
                                        line=expr.line, col=expr.col, file=self.file, code="T015")
                    a_t = self._check_expr(expr.args[0])
                    for index in (1, 2):
                        b_t = self._check_expr(expr.args[index])
                        if b_t != IntType:
                            raise TypeError(
                                message=f"slice() bound {index} expects int, found '{b_t}'",
                                line=expr.args[index].line, col=expr.args[index].col,
                                file=self.file, code="T003")
                    if a_t == StrType:
                        return StrType
                    if isinstance(a_t, ListType):
                        return a_t
                    raise TypeError(
                        message=f"slice() expects str or list, found '{a_t}'",
                        line=expr.line, col=expr.col, file=self.file, code="T003")

                if name == "enumerate":
                    if len(expr.args) != 1:
                        raise TypeError(message="enumerate() takes exactly 1 argument", line=expr.line, col=expr.col, file=self.file, code="T015")
                    a_t = self._check_expr(expr.args[0])
                    if not isinstance(a_t, ListType):
                        raise TypeError(message=f"enumerate() expects list, found '{a_t}'", line=expr.line, col=expr.col, file=self.file, code="T003")
                    return ListType(TupleType([IntType, a_t.element]))

                if name == "dict_items":
                    if len(expr.args) != 1:
                        raise TypeError(message="dict_items() takes exactly 1 argument", line=expr.line, col=expr.col, file=self.file, code="T015")
                    a_t = self._check_expr(expr.args[0])
                    if not isinstance(a_t, DictType):
                        raise TypeError(message=f"dict_items() expects dict, found '{a_t}'", line=expr.line, col=expr.col, file=self.file, code="T003")
                    return ListType(TupleType([a_t.key, a_t.value]))

            if expr.type_args:
                raise TypeError("Type arguments require a generic function", file=self.file,
                                line=expr.line, col=expr.col, code="W2003")
            # Standard function argument checking
            if callee_t.params == [AnyType()]:
                # Variadic (like print)
                for a in expr.args:
                    self._check_expr(a)

                return callee_t.ret

            if len(expr.args) != len(callee_t.params):
                raise TypeError(
                    message=f"Expected {len(callee_t.params)} arguments, found {len(expr.args)}",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T015"
                )

            for i, (a_expr, p_type) in enumerate(zip(expr.args, callee_t.params)):
                a_type = self._check_payload(a_expr, p_type)
                if not is_assignable(a_type, p_type):
                    raise TypeError(
                        message=f"Argument {i + 1} type mismatch: expected '{p_type}', found '{a_type}'",
                        line=a_expr.line,
                        col=a_expr.col,
                        file=self.file,
                        code="T003"
                    )
                self._mark_result_lift(a_expr, p_type, force=True)
            return callee_t.ret

        if isinstance(expr, StructInitExpr):
            template = self.generic_struct_templates.get(expr.struct_name)
            if template is not None:
                if expr.type_args:
                    concrete_args = [self._resolve_type_node(a) for a in expr.type_args]
                else:
                    type_params_set = {p.name if hasattr(p, "name") else str(p) for p in template.type_params}
                    bindings: Dict[str, WType] = {}
                    template_fields = {f.name: f.type_ann for f in template.ast_decl.fields}
                    for f in expr.fields:
                        if f.name in template_fields:
                            a_t = self._check_expr(f.value)
                            if not self._unify_type(template_fields[f.name], a_t, type_params_set, bindings):
                                raise TypeError(
                                    message=f"Conflicting type inference for field '{f.name}' in struct '{template.name}': cannot unify '{a_t}'",
                                    line=f.line,
                                    col=f.col,
                                    file=self.file,
                                    code="W2001"
                                )

                    for p in template.type_params:
                        p_name = p.name if hasattr(p, "name") else str(p)
                        if p_name not in bindings:
                            raise TypeError(
                                message=f"Cannot infer type argument for type parameter '{p_name}' in struct '{template.name}'",
                                line=expr.line,
                                col=expr.col,
                                file=self.file,
                                code="T003"
                            )
                    concrete_args = self._concrete_type_args(template, bindings)

                struct_t = self._monomorphize_struct(template, concrete_args, expr.line, expr.col)
                expr.struct_name = struct_t.name
                expr.type_args = []
            else:
                if expr.type_args:
                    raise TypeError(
                        message=f"Struct '{expr.struct_name}' is not generic",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T002"
                    )
                struct_t = self.current_scope.lookup_type(expr.struct_name)
                if struct_t is None or not isinstance(struct_t, StructType):
                    raise TypeError(
                        message=f"Unknown struct type '{expr.struct_name}'",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T002"
                    )

            seen_fields: Set[str] = set()
            for f in expr.fields:
                if f.name in seen_fields:
                    raise TypeError(
                        message=f"Duplicate field '{f.name}' in struct initialization of '{expr.struct_name}'",
                        line=f.line,
                        col=f.col,
                        file=self.file,
                        code="T014"
                    )
                seen_fields.add(f.name)

            for req_field in struct_t.fields:
                if req_field not in seen_fields:
                    raise TypeError(
                        message=f"Missing required field '{req_field}' in struct initialization of '{expr.struct_name}'",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T013"
                    )

            for f in expr.fields:
                if f.name not in struct_t.fields:
                    raise TypeError(
                        message=f"Struct '{expr.struct_name}' has no field '{f.name}'",
                        line=f.line,
                        col=f.col,
                        file=self.file,
                        code="T012"
                    )
                expected_f_type = struct_t.fields[f.name]
                actual_f_type = self._check_expr(f.value)
                if not is_assignable(actual_f_type, expected_f_type):
                    raise TypeError(
                        message=f"Field '{f.name}' type mismatch: expected '{expected_f_type}', found '{actual_f_type}'",
                        line=f.line,
                        col=f.col,
                        file=self.file,
                        code="T003"
                    )
                self._mark_result_lift(f.value, expected_f_type, force=True)
            return struct_t

        if isinstance(expr, ListExpr):
            context = self.expected_type if isinstance(self.expected_type, ListType) else None
            if len(expr.elements) == 0:
                return context or ListType(AnyType())
            elem_types = [self._check_payload(e, context.element if context else None) for e in expr.elements]
            common_t = elem_types[0]
            for t in elem_types[1:]:
                if is_assignable(t, common_t):
                    continue
                if is_assignable(common_t, t):
                    common_t = t
                    continue
                found_super: Optional[WType] = None
                if isinstance(common_t, ClassType) and isinstance(t, ClassType):
                    curr = common_t.superclass
                    while curr is not None:
                        if is_assignable(t, curr):
                            found_super = curr
                            break
                        curr = curr.superclass
                if found_super is not None:
                    common_t = found_super
                    continue
                raise TypeError(
                    message=f"List elements must be homogeneous: found '{t}' and '{common_t}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T003"
                )
            return ListType(common_t)

        if isinstance(expr, TupleExpr):
            elem_types = [self._check_expr(e) for e in expr.elements]
            return TupleType(elem_types)

        if isinstance(expr, DictExpr):
            context = self.expected_type if isinstance(self.expected_type, DictType) else None
            if len(expr.entries) == 0:
                return context or DictType(AnyType(), AnyType())
            first_key_t = self._check_payload(expr.entries[0].key, context.key if context else None)
            if not self._is_valid_dict_key_type(first_key_t):
                raise TypeError(
                    message=f"Invalid dictionary key type '{first_key_t}'; allowed key types are int, str, bool, or enum",
                    line=expr.entries[0].key.line,
                    col=expr.entries[0].key.col,
                    file=self.file,
                    code="W2010"
                )
            first_val_t = self._check_payload(expr.entries[0].value, context.value if context else None)
            for entry in expr.entries[1:]:
                kt = self._check_payload(entry.key, context.key if context else None)
                vt = self._check_payload(entry.value, context.value if context else None)
                if not self._is_valid_dict_key_type(kt):
                    raise TypeError(
                        message=f"Invalid dictionary key type '{kt}'; allowed key types are int, str, bool, or enum",
                        line=entry.key.line,
                        col=entry.key.col,
                        file=self.file,
                        code="W2010"
                    )
                if not is_assignable(kt, first_key_t):
                    raise TypeError(
                        message=f"Dict keys must be homogeneous: found '{kt}' and '{first_key_t}'",
                        line=entry.key.line,
                        col=entry.key.col,
                        file=self.file,
                        code="T003"
                    )
                if not is_assignable(vt, first_val_t):
                    raise TypeError(
                        message=f"Dict values must be homogeneous: found '{vt}' and '{first_val_t}'",
                        line=entry.value.line,
                        col=entry.value.col,
                        file=self.file,
                        code="T003"
                    )
            return DictType(first_key_t, first_val_t)


        if isinstance(expr, IfExpr):
            cond_t = self._check_expr(expr.condition)
            if cond_t != BoolType:
                raise TypeError(
                    message=f"Condition of 'if' must be bool, found '{cond_t}'",
                    line=expr.condition.line,
                    col=expr.condition.col,
                    file=self.file,
                    code="T003"
                )
            then_t = self._check_block(expr.then_branch, is_statement_context=is_statement_context) or UnitType

            for elif_b in expr.elif_branches:
                e_cond_t = self._check_expr(elif_b.condition)
                if e_cond_t != BoolType:
                    raise TypeError(message=f"Condition of 'elif' must be bool, found '{e_cond_t}'", line=elif_b.condition.line, col=elif_b.condition.col, file=self.file, code="T003")
                e_then_t = self._check_block(elif_b.body, is_statement_context=is_statement_context) or UnitType
                if not is_statement_context and not is_assignable(e_then_t, then_t):
                    raise TypeError(
                        message=f"Incompatible types in 'elif' branch: '{e_then_t}' vs '{then_t}'",
                        line=elif_b.line,
                        col=elif_b.col,
                        file=self.file,
                        code="T003"
                    )

            if expr.else_branch is not None:
                else_t = self._check_block(expr.else_branch, is_statement_context=is_statement_context) or UnitType
                if not is_statement_context and not is_assignable(else_t, then_t):
                    raise TypeError(
                        message=f"Incompatible types in 'if' expression branches: '{else_t}' vs '{then_t}'",
                        line=expr.else_branch.line,
                        col=expr.else_branch.col,
                        file=self.file,
                        code="T003"
                    )
                return UnitType if is_statement_context else then_t
            else:
                if not is_statement_context and then_t != UnitType:
                    raise TypeError(
                        message="If-expression returning a value requires an 'else' branch",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T003"
                    )
                return UnitType

        if isinstance(expr, MatchExpr):
            outer_expected = self.expected_type
            subject_t = self._check_expr(expr.subject)
            covered_variants: Set[str] = set()
            has_wildcard = False
            arm_types: List[WType] = []

            # Determine expected variants and variant payload types for subject_t
            expected_variants: Optional[Set[str]] = None
            payload_types_map: Dict[str, List[WType]] = {}

            if isinstance(subject_t, OptionalType):
                expected_variants = {"Some", "None"}
                payload_types_map = {"Some": [subject_t.inner], "None": []}
            elif isinstance(subject_t, ResultType):
                expected_variants = {"Ok", "Err"}
                payload_types_map = {"Ok": [subject_t.ok], "Err": [subject_t.err]}
            elif isinstance(subject_t, ErrorUnionType):
                expected_variants = {self._error_pattern_name(member) for member in subject_t.alternatives}
                payload_types_map = {
                    self._error_pattern_name(member): [member]
                    for member in subject_t.alternatives
                }
            elif isinstance(subject_t, EnumType):
                if getattr(subject_t, "template_name", None) == "Option" and getattr(subject_t, "type_args", None):
                    expected_variants = {"Some", "None"}
                    payload_types_map = {"Some": [subject_t.type_args[0]], "None": []}
                elif getattr(subject_t, "template_name", None) == "Result" and getattr(subject_t, "type_args", None) and len(subject_t.type_args) == 2:
                    expected_variants = {"Ok", "Err"}
                    payload_types_map = {"Ok": [subject_t.type_args[0]], "Err": [subject_t.type_args[1]]}
                else:
                    expected_variants = set(subject_t.variants)
                    payload_types_map = subject_t.variant_payloads

            for arm in expr.arms:
                previous_coverage = set(covered_variants)
                previous_wildcard = has_wildcard
                arm.pattern.inferred_type_id = self.interner.intern(subject_t)
                arm_bindings: Dict[str, WType] = {}

                if isinstance(arm.pattern, WildcardPattern):
                    has_wildcard = True

                elif isinstance(arm.pattern, IdentifierPattern):
                    if arm.pattern.name in ("None", "none") and expected_variants and "None" in expected_variants:
                        covered_variants.add("None")
                    else:
                        has_wildcard = True
                        arm_bindings[arm.pattern.name] = subject_t

                elif isinstance(arm.pattern, TuplePattern):
                    self._bind_pattern_type(arm.pattern, subject_t, arm_bindings, arm.line, arm.col)

                elif isinstance(arm.pattern, LiteralPattern):
                    if isinstance(arm.pattern.literal, NoneLiteral) and expected_variants and "None" in expected_variants:
                        covered_variants.add("None")
                    else:
                        lit_t = self._check_expr(arm.pattern.literal)
                        if not is_assignable(lit_t, subject_t):
                            raise TypeError(
                                message=f"Literal pattern type '{lit_t}' incompatible with subject '{subject_t}'",
                                line=arm.line,
                                col=arm.col,
                                file=self.file,
                                code="T003"
                            )

                elif isinstance(arm.pattern, EnumPattern):
                    v_name = arm.pattern.variant
                    if isinstance(subject_t, ErrorUnionType):
                        if arm.pattern.enum_name is None:
                            matched_type = next(
                                (member for member in subject_t.alternatives
                                 if self._error_pattern_name(member) == v_name),
                                None
                            )
                        else:
                            qualified_name = f"{arm.pattern.enum_name}.{v_name}"
                            qualified_type = self._lookup_type_name(qualified_name)
                            matched_type = next(
                                (member for member in subject_t.alternatives
                                 if member == qualified_type),
                                None
                            )
                        if matched_type is None:
                            raise TypeError(
                                message=f"Pattern '{v_name}(...)' is not an alternative of error union '{subject_t}'",
                                line=arm.line,
                                col=arm.col,
                                file=self.file,
                                code="T003"
                            )
                        if len(arm.pattern.args) != 1:
                            raise TypeError(
                                message=f"Error type pattern '{v_name}(...)' requires exactly one binding pattern",
                                line=arm.line,
                                col=arm.col,
                                file=self.file,
                                code="T015"
                            )
                        if not isinstance(arm.pattern.args[0], (IdentifierPattern, WildcardPattern)):
                            raise TypeError(
                                message="Error type patterns accept one binding or wildcard, such as 'ParseError(err)'",
                                line=arm.line,
                                col=arm.col,
                                file=self.file,
                                code="T015"
                            )
                        arm.pattern.error_type_match = matched_type
                        arm_bindings = {}
                        self._bind_pattern_type(arm.pattern.args[0], matched_type, arm_bindings, arm.line, arm.col)
                        covered_variants.add(self._error_pattern_name(matched_type))
                    else:
                        if arm.pattern.enum_name:
                            if isinstance(subject_t, EnumType):
                                if arm.pattern.enum_name != subject_t.name and arm.pattern.enum_name != getattr(subject_t, "template_name", None):
                                    raise TypeError(
                                        message=f"Pattern '{arm.pattern.enum_name}.{v_name}' is incompatible with match subject '{subject_t}'",
                                        line=arm.line,
                                        col=arm.col,
                                        file=self.file,
                                        code="T003"
                                    )
                            elif isinstance(subject_t, OptionalType) and arm.pattern.enum_name != "Option":
                                raise TypeError(
                                    message=f"Pattern '{arm.pattern.enum_name}.{v_name}' is incompatible with optional subject '{subject_t}'",
                                    line=arm.line,
                                    col=arm.col,
                                    file=self.file,
                                    code="T003"
                                )
                            elif isinstance(subject_t, ResultType) and arm.pattern.enum_name != "Result":
                                raise TypeError(
                                    message=f"Pattern '{arm.pattern.enum_name}.{v_name}' is incompatible with result subject '{subject_t}'",
                                    line=arm.line,
                                    col=arm.col,
                                    file=self.file,
                                    code="T003"
                                )

                        if expected_variants is not None and v_name not in expected_variants:
                            raise TypeError(
                                message=f"Pattern variant '{v_name}' is incompatible with match subject '{subject_t}'",
                                line=arm.line,
                                col=arm.col,
                                file=self.file,
                                code="T003"
                            )
                        if isinstance(subject_t, EnumType) and getattr(subject_t, "template_name", None) not in ("Option", "Result"):
                            arm.pattern.enum_name = subject_t.name
                        covered_variants.add(v_name)
                        expected_payloads = payload_types_map.get(v_name, [])
                        if len(arm.pattern.args) != len(expected_payloads):
                            raise TypeError(
                                message=f"Variant '{v_name}' expects {len(expected_payloads)} arguments, found {len(arm.pattern.args)}",
                                line=arm.line,
                                col=arm.col,
                                file=self.file,
                                code="T015"
                            )
                        for arg_pat, arg_type in zip(arm.pattern.args, expected_payloads):
                            self._bind_pattern_type(arg_pat, arg_type, arm_bindings, arm.line, arm.col)

                if arm.guard is not None:
                    guard_scope = Scope(parent=self.current_scope)
                    for bn, bt in arm_bindings.items():
                        guard_scope.define_symbol(Symbol(bn, bt, is_mut=False, kind="var", line=arm.line, col=arm.col), file=self.file)
                    old_s = self.current_scope
                    self.current_scope = guard_scope
                    try:
                        g_t = self._check_expr(arm.guard)
                        if g_t != BoolType:
                            raise TypeError(
                                message=f"Match guard must be bool, found '{g_t}'",
                                line=arm.guard.line,
                                col=arm.guard.col,
                                file=self.file,
                                code="T003"
                            )
                    finally:
                        self.current_scope = old_s

                if arm.guard is not None:
                    covered_variants = previous_coverage
                    has_wildcard = previous_wildcard
                arm_t = self._check_block(arm.body, initial_bindings=arm_bindings) or UnitType
                arm_types.append(arm_t)

            # Guards do not contribute unconditional coverage. Specialize the
            # pattern matrix to account for nested variants and payload products.
            if expected_variants is not None or subject_t == BoolType or isinstance(subject_t, TupleType):
                rows = [[arm.pattern] for arm in expr.arms if arm.guard is None]
                if not self._pattern_matrix_exhaustive([subject_t], rows):
                    raise TypeError("Non-exhaustive match: missing variant or payload cases",
                                    line=expr.line, col=expr.col, file=self.file, code="W2003")
            else:
                # The subject domain is open (int, str, struct, ...), so the pattern
                # matrix can never be closed. The match is still only well defined when
                # it yields a value: a falling-through arm would return nothing where a
                # value is required, which the backends used to reject with an internal
                # error. A statement-position match may legitimately fall through.
                yields_value = (
                    any(at != UnitType for at in arm_types)
                    or (outer_expected is not None and outer_expected != UnitType)
                )
                if yields_value and not has_wildcard:
                    raise TypeError(
                        message=f"Non-exhaustive match: '{subject_t}' is an open domain, "
                                f"so a '_ =>' fallback arm is required when the match produces a value",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="W2003",
                    )

            if arm_types:
                first_t = arm_types[0]
                for at in arm_types[1:]:
                    if not is_assignable(at, first_t):
                        raise TypeError(
                            message=f"Incompatible return types in match arms: '{at}' vs '{first_t}'",
                            line=expr.line,
                            col=expr.col,
                            file=self.file,
                            code="T003"
                        )
                return first_t
            return UnitType

        return UnitType

    def _pattern_matrix_exhaustive(self, types: List[WType], rows: List[List[Any]]) -> bool:
        if not types:
            return bool(rows)
        if not rows:
            return False
        from hir.HirNodes import (
            HirWildcardPattern, HirBindingPattern, HirLiteralPattern, HirEnumPattern, HirTuplePattern
        )
        def wildcard(pattern):
            if isinstance(pattern, (WildcardPattern, HirWildcardPattern)):
                return True
            if isinstance(pattern, (IdentifierPattern, HirBindingPattern)) and pattern.name not in ("None", "none"):
                return True
            return False
        defaults = [row[1:] for row in rows if wildcard(row[0])]
        if defaults and self._pattern_matrix_exhaustive(types[1:], defaults):
            return True
        first = types[0]
        optional = self._builtin_arguments(first, "Option")
        result = self._builtin_arguments(first, "Result")
        if optional:
            constructors = {"Some": optional, "None": []}
        elif result:
            constructors = {"Ok": [result[0]], "Err": [result[1]]}
        elif isinstance(first, ErrorUnionType):
            constructors = {
                self._error_pattern_name(member): [member]
                for member in first.alternatives
            }
        elif isinstance(first, EnumType):
            constructors = {name: first.variant_payloads.get(name, []) for name in first.variants}
        elif isinstance(first, TupleType):
            constructors = {"tuple": first.elements}
        elif first == BoolType:
            constructors = {"true": [], "false": []}
        else:
            return False
        for name, payload in constructors.items():
            specialized = []
            for row in rows:
                pattern = row[0]
                if wildcard(pattern):
                    specialized.append([WildcardPattern() for _ in payload] + row[1:])
                elif (
                    isinstance(first, ErrorUnionType)
                    and isinstance(pattern, EnumPattern)
                    and getattr(pattern, "error_type_match", None) is not None
                    and self._error_pattern_name(pattern.error_type_match) == name
                ):
                    specialized.append(pattern.args + row[1:])
                elif isinstance(pattern, EnumPattern) and pattern.variant == name:
                    specialized.append(pattern.args + row[1:])
                elif isinstance(pattern, HirEnumPattern) and pattern.variant_name == name:
                    specialized.append(pattern.subpatterns + row[1:])
                elif isinstance(pattern, TuplePattern) and name == "tuple":
                    specialized.append(pattern.elements + row[1:])
                elif isinstance(pattern, HirTuplePattern) and name == "tuple":
                    specialized.append(pattern.elements + row[1:])
                elif name == "None" and (
                    (isinstance(pattern, (IdentifierPattern, HirBindingPattern)) and pattern.name in ("None", "none")) or
                    (isinstance(pattern, LiteralPattern) and isinstance(pattern.literal, NoneLiteral)) or
                    (isinstance(pattern, HirLiteralPattern) and pattern.literal_kind == "none")
                ):
                    specialized.append(row[1:])
                elif (
                    (isinstance(pattern, LiteralPattern) and isinstance(pattern.literal, BoolLiteral) and name == ("true" if pattern.literal.value else "false")) or
                    (isinstance(pattern, HirLiteralPattern) and pattern.literal_kind == "bool" and name == ("true" if pattern.value else "false"))
                ):
                    specialized.append(row[1:])
            if not self._pattern_matrix_exhaustive(payload + types[1:], specialized):
                return False
        return True

    @staticmethod
    def _error_pattern_name(error_type: WType) -> str:
        if error_type in (IntType, FloatType, BoolType, StrType):
            return str(error_type)
        if isinstance(error_type, (StructType, EnumType)):
            return error_type.name
        return str(error_type)

    def _bind_pattern_type(self, pattern: Pattern, expected_type: WType, bindings: Dict[str, WType], line: int, col: int) -> None:
        pattern.inferred_type_id = self.interner.intern(expected_type)
        if isinstance(pattern, IdentifierPattern):
            bindings[pattern.name] = expected_type
        elif isinstance(pattern, WildcardPattern):
            pass
        elif isinstance(pattern, TuplePattern):
            if not isinstance(expected_type, TupleType) or len(pattern.elements) != len(expected_type.elements):
                raise TypeError(
                    message=f"Tuple pattern cannot match type '{expected_type}'",
                    line=line,
                    col=col,
                    file=self.file,
                    code="T003"
                )
            for sub_p, sub_t in zip(pattern.elements, expected_type.elements):
                self._bind_pattern_type(sub_p, sub_t, bindings, line, col)
        elif isinstance(pattern, EnumPattern):
            optional = self._builtin_arguments(expected_type, "Option")
            result = self._builtin_arguments(expected_type, "Result")
            if optional:
                payloads = {"Some": optional, "None": []}
            elif result:
                payloads = {"Ok": [result[0]], "Err": [result[1]]}
            elif isinstance(expected_type, EnumType):
                payloads = expected_type.variant_payloads
                pattern.enum_name = expected_type.name
            else:
                raise TypeError("Enum pattern requires enum type", line=line, col=col, file=self.file, code="W2001")
            types = payloads.get(pattern.variant)
            if types is None or len(types) != len(pattern.args):
                raise TypeError("Enum pattern payload does not match variant", line=line, col=col, file=self.file, code="W2001")
            for child, child_type in zip(pattern.args, types):
                self._bind_pattern_type(child, child_type, bindings, line, col)
        elif isinstance(pattern, LiteralPattern):
            lit_t = self._check_expr(pattern.literal)
            if not is_assignable(lit_t, expected_type):
                raise TypeError(
                    message=f"Literal pattern type '{lit_t}' incompatible with '{expected_type}'",
                    line=line,
                    col=col,
                    file=self.file,
                    code="T003"
                )

    # ==========================================
    # Generics and Monomorphization Helpers
    # ==========================================

    def _concrete_type_args(self, template, bindings: Dict[str, WType]) -> List[WType]:
        """Builds the specialization arguments for a generic template.

        A type parameter with no binding keeps its own identity instead of collapsing
        to the `any` placeholder. `any` erases identity, so `Ok(42)` and `Err("bad")`
        would specialize to `Result__int__any` and `Result__any__int`, two distinct
        types that then fail to compare even though both are `Result[int, str]`.
        """
        arguments: List[WType] = []
        for parameter in template.type_params:
            name = parameter.name if hasattr(parameter, "name") else str(parameter)
            bound = bindings.get(name)
            if bound is None or isinstance(bound, AnyType):
                arguments.append(TypeParamType(name))
            else:
                arguments.append(bound)
        return arguments

    def _mangle_type_name(self, t: WType) -> str:
        return _mangle_type_static(t)

    def _wtype_to_type_node(self, t: WType) -> TypeNode:
        node = self._wtype_to_type_node_impl(t)
        if isinstance(t, (StructType, EnumType, ClassType, InterfaceType)) and self.current_scope.lookup_type(t.name) is not t:
            node.session_resolved_type = t
            node.session_arena_id = self.interner.arena_id
        return node

    def _wtype_to_type_node_impl(self, t: WType) -> TypeNode:
        if isinstance(t, AnyType):
            # Synthesized, never written by the user: this is the placeholder that
            # monomorphization binds to an uninferred type parameter. Mark it so the
            # resolver can tell it apart from a user-written `any`, which is rejected.
            synthesized = NamedType("any")
            synthesized.is_internal_any = True
            return synthesized
        if t == IntType:
            return NamedType("int")
        if t == FloatType:
            return NamedType("float")
        if t == BoolType:
            return NamedType("bool")
        if t == StrType:
            return NamedType("str")
        if t == UnitType:
            return NamedType("unit")
        if t == NoneType:
            return NamedType("none")
        if isinstance(t, StructType):
            return NamedType(t.name)
        if isinstance(t, EnumType):
            return NamedType(t.name)
        if isinstance(t, ClassType):
            return NamedType(t.name)
        if isinstance(t, InterfaceType):
            return NamedType(t.name)
        if isinstance(t, WeakType):
            return GenericType("Weak", [self._wtype_to_type_node(t.target)])
        if isinstance(t, OptionalType):
            return AstOptionalType(self._wtype_to_type_node(t.inner))
        if isinstance(t, ListType):
            return AstListType(self._wtype_to_type_node(t.element))
        if isinstance(t, DictType):
            return AstDictType(self._wtype_to_type_node(t.key), self._wtype_to_type_node(t.value))
        if isinstance(t, TupleType):
            return AstTupleType([self._wtype_to_type_node(e) for e in t.elements])
        if isinstance(t, ResultType):
            return AstResultType(self._wtype_to_type_node(t.ok), self._wtype_to_type_node(t.err))
        if isinstance(t, ErrorUnionType):
            return AstErrorUnionType([self._wtype_to_type_node(member) for member in t.alternatives])
        if isinstance(t, FunctionType):
            return AstFunctionType([self._wtype_to_type_node(p) for p in t.params], self._wtype_to_type_node(t.ret))
        if isinstance(t, TypeParamType):
            return NamedType(t.name)
        return NamedType(str(t))

    def _substitute_type_node(self, node: TypeNode, subst: Dict[str, WType]) -> TypeNode:
        if isinstance(node, AstFunctionType):
            return AstFunctionType([self._substitute_type_node(p, subst) for p in node.params],
                                   self._substitute_type_node(node.return_type, subst), node.line, node.col)
        if isinstance(node, NamedType):
            if node.name in subst:
                return self._wtype_to_type_node(subst[node.name])
            return NamedType(node.name, line=node.line, col=node.col)
        if isinstance(node, GenericType):
            new_args = [self._substitute_type_node(a, subst) for a in node.type_args]
            return GenericType(node.name, new_args, line=node.line, col=node.col)
        if isinstance(node, AstOptionalType):
            return AstOptionalType(self._substitute_type_node(node.inner, subst), line=node.line, col=node.col)
        if isinstance(node, AstListType):
            return AstListType(self._substitute_type_node(node.element_type, subst), line=node.line, col=node.col)
        if isinstance(node, AstDictType):
            return AstDictType(
                self._substitute_type_node(node.key_type, subst),
                self._substitute_type_node(node.value_type, subst),
                line=node.line,
                col=node.col
            )
        if isinstance(node, AstTupleType):
            return AstTupleType([self._substitute_type_node(e, subst) for e in node.element_types], line=node.line, col=node.col)
        if isinstance(node, AstResultType):
            return AstResultType(
                self._substitute_type_node(node.ok_type, subst),
                self._substitute_type_node(node.err_type, subst),
                line=node.line,
                col=node.col
            )
        if isinstance(node, AstErrorUnionType):
            return AstErrorUnionType(
                [self._substitute_type_node(member, subst) for member in node.error_types],
                line=node.line,
                col=node.col
            )
        return node

    def _substitute_ast_types(self, node: Any, subst: Dict[str, WType]) -> None:
        if node is None:
            return
        if isinstance(node, LambdaExpr):
            for parameter in node.params:
                if parameter.type_ann is not None:
                    parameter.type_ann = self._substitute_type_node(parameter.type_ann, subst)
            if node.return_type is not None:
                node.return_type = self._substitute_type_node(node.return_type, subst)
            self._substitute_ast_types(node.body, subst)
        elif isinstance(node, NewExpr):
            if getattr(node, 'type_args', None):
                node.type_args = [self._substitute_type_node(a, subst) for a in node.type_args]
            for argument in node.args:
                self._substitute_ast_types(argument, subst)
        elif isinstance(node, LetDecl):
            if node.type_ann is not None:
                node.type_ann = self._substitute_type_node(node.type_ann, subst)
            init_val = getattr(node, "initializer", getattr(node, "init", None))
            if init_val is not None:
                self._substitute_ast_types(init_val, subst)
        elif isinstance(node, StructInitExpr):
            if node.type_args:
                node.type_args = [self._substitute_type_node(a, subst) for a in node.type_args]
            for f in node.fields:
                self._substitute_ast_types(f.value, subst)
        elif isinstance(node, CallExpr):
            if node.type_args:
                node.type_args = [self._substitute_type_node(a, subst) for a in node.type_args]
            self._substitute_ast_types(node.callee, subst)
            for a in node.args:
                self._substitute_ast_types(a, subst)
        elif isinstance(node, Block):
            for s in node.statements:
                self._substitute_ast_types(s, subst)
            if node.tail_expr:
                self._substitute_ast_types(node.tail_expr, subst)
        elif isinstance(node, ExprStmt):
            self._substitute_ast_types(node.expr, subst)
        elif isinstance(node, ReturnStmt):
            if node.value:
                self._substitute_ast_types(node.value, subst)
        elif isinstance(node, WhileStmt):
            self._substitute_ast_types(node.condition, subst)
            self._substitute_ast_types(node.body, subst)
        elif isinstance(node, ForStmt):
            self._substitute_ast_types(node.iterable, subst)
            self._substitute_ast_types(node.body, subst)
        elif isinstance(node, IfExpr):
            self._substitute_ast_types(node.condition, subst)
            self._substitute_ast_types(node.then_branch, subst)
            for eb in node.elif_branches:
                self._substitute_ast_types(eb.condition, subst)
                self._substitute_ast_types(eb.body, subst)
            if node.else_branch:
                self._substitute_ast_types(node.else_branch, subst)
        elif isinstance(node, MatchExpr):
            self._substitute_ast_types(node.subject, subst)
            for arm in node.arms:
                if arm.guard:
                    self._substitute_ast_types(arm.guard, subst)
                self._substitute_ast_types(arm.body, subst)
        elif isinstance(node, BinaryExpr):
            self._substitute_ast_types(node.left, subst)
            self._substitute_ast_types(node.right, subst)
        elif isinstance(node, UnaryExpr):
            self._substitute_ast_types(node.operand, subst)
        elif isinstance(node, MemberExpr):
            self._substitute_ast_types(node.object, subst)
        elif isinstance(node, IndexExpr):
            self._substitute_ast_types(node.object, subst)
            self._substitute_ast_types(node.index, subst)
        elif isinstance(node, AssignmentExpr):
            self._substitute_ast_types(node.target, subst)
            self._substitute_ast_types(node.value, subst)
        elif isinstance(node, ListExpr):
            for e in node.elements:
                self._substitute_ast_types(e, subst)
        elif isinstance(node, DictExpr):
            for e in node.entries:
                if hasattr(e, "key"):
                    self._substitute_ast_types(e.key, subst)
                    self._substitute_ast_types(e.value, subst)
                elif isinstance(e, (list, tuple)) and len(e) == 2:
                    self._substitute_ast_types(e[0], subst)
                    self._substitute_ast_types(e[1], subst)
        elif isinstance(node, TupleExpr):
            for e in node.elements:
                self._substitute_ast_types(e, subst)
        elif isinstance(node, RangeExpr):
            self._substitute_ast_types(node.start, subst)
            self._substitute_ast_types(node.end, subst)
        elif isinstance(node, PostfixTryExpr):
            self._substitute_ast_types(node.operand, subst)
        elif isinstance(node, ElseErrExpr):
            self._substitute_ast_types(node.operand, subst)
            self._substitute_ast_types(node.handler, subst)
        elif isinstance(node, CoalesceExpr):
            self._substitute_ast_types(node.left, subst)
            self._substitute_ast_types(node.right, subst)

    def _unify_type(
        self,
        param_type_node: TypeNode,
        arg_wtype: WType,
        type_params: Set[str],
        bindings: Dict[str, WType]
    ) -> bool:
        if isinstance(param_type_node, NamedType) and param_type_node.name in type_params:
            p_name = param_type_node.name
            if p_name in bindings:
                return bindings[p_name] == arg_wtype
            bindings[p_name] = arg_wtype
            return True

        if isinstance(param_type_node, AstFunctionType) and isinstance(arg_wtype, FunctionType):
            return (len(param_type_node.params) == len(arg_wtype.params) and
                    all(self._unify_type(p, a, type_params, bindings)
                        for p, a in zip(param_type_node.params, arg_wtype.params)) and
                    self._unify_type(param_type_node.return_type, arg_wtype.ret, type_params, bindings))

        if isinstance(param_type_node, AstOptionalType) and isinstance(arg_wtype, OptionalType):
            return self._unify_type(param_type_node.inner, arg_wtype.inner, type_params, bindings)

        if isinstance(param_type_node, AstListType) and isinstance(arg_wtype, ListType):
            return self._unify_type(param_type_node.element_type, arg_wtype.element, type_params, bindings)

        if isinstance(param_type_node, AstDictType) and isinstance(arg_wtype, DictType):
            return (self._unify_type(param_type_node.key_type, arg_wtype.key, type_params, bindings) and
                    self._unify_type(param_type_node.value_type, arg_wtype.value, type_params, bindings))

        if isinstance(param_type_node, AstTupleType) and isinstance(arg_wtype, TupleType):
            if len(param_type_node.element_types) != len(arg_wtype.elements):
                return False
            return all(self._unify_type(pt, at, type_params, bindings)
                       for pt, at in zip(param_type_node.element_types, arg_wtype.elements))

        if isinstance(param_type_node, AstResultType) and isinstance(arg_wtype, ResultType):
            return (self._unify_type(param_type_node.ok_type, arg_wtype.ok, type_params, bindings) and
                    self._unify_type(param_type_node.err_type, arg_wtype.err, type_params, bindings))

        if isinstance(param_type_node, AstErrorUnionType) and isinstance(arg_wtype, ErrorUnionType):
            try:
                declared = ErrorUnionType([self._resolve_type_node(member) for member in param_type_node.error_types])
            except Exception:
                return False
            return declared == arg_wtype

        if isinstance(param_type_node, GenericType) and isinstance(arg_wtype, (StructType, EnumType, ClassType, InterfaceType)):
            tmpl_name = getattr(arg_wtype, "template_name", None)
            tmpl_args = getattr(arg_wtype, "type_args", None)
            if tmpl_name == param_type_node.name and tmpl_args and len(tmpl_args) == len(param_type_node.type_args):
                return all(self._unify_type(pt, at, type_params, bindings)
                           for pt, at in zip(param_type_node.type_args, tmpl_args))

        # The declared payload type mentions no type parameter, so it must be checked
        # against the argument. Returning True here (the previous behaviour) let
        # `enum Pair[T] { P(T, int) }` accept `P(1, "wrong")`: the checker certified a
        # program that both backends then rejected with an internal error.
        try:
            declared = self._resolve_type_node(param_type_node)
        except Exception:
            # Unresolvable here means "not a declared concrete type"; leave the
            # verdict to the dedicated resolution paths that report diagnostics.
            return True
        if isinstance(declared, (GenericStructTemplate, GenericEnumTemplate, GenericFnTemplate)):
            return True
        return is_assignable(arg_wtype, declared)
    def _resolve_constraint_interface(self, constraint: TypeNode, line: int, col: int) -> InterfaceType:
        if not isinstance(constraint, NamedType):
            raise TypeError("Generic constraints must name an interface", line=line,
                            col=col, file=self.file, code="W2012")
        resolved = self.global_scope.lookup_type(constraint.name)
        if not isinstance(resolved, InterfaceType):
            raise TypeError(f"Generic constraint '{constraint.name}' is not a declared interface",
                            line=line, col=col, file=self.file, code="W2012")
        return resolved

    def _check_type_constraint(self, type_arg: WType, constraint: Optional[TypeNode], line: int, col: int) -> None:
        if constraint is None:
            return
        c_name = constraint.name if isinstance(constraint, NamedType) else str(constraint)
        c_type = self._resolve_constraint_interface(constraint, line, col)
        if isinstance(c_type, InterfaceType):
            if isinstance(type_arg, ClassType):
                if not type_arg.implements_interface(c_name):
                    raise TypeError(
                        message=f"Type '{type_arg}' does not implement interface constraint '{c_name}'",
                        line=line,
                        col=col,
                        file=self.file,
                        code="T024"
                    )
            else:
                raise TypeError(
                    message=f"Type '{type_arg}' does not satisfy interface constraint '{c_name}'",
                    line=line,
                    col=col,
                    file=self.file,
                    code="T024"
                )

    def _type_complexity(self, t: WType) -> int:
        """Structural size of a type: 1 for a scalar, plus the size of every component.

        Used to bound generic specializations by *size* rather than only by recursion
        depth. A depth limit alone lets a chain of shallow but ever-growing instances
        (each level adding one list wrapper) allocate until it exhausts memory, because
        every level is a distinct specialization that is never rebuilt.
        """
        if isinstance(t, ListType):
            return 1 + self._type_complexity(t.element)
        if isinstance(t, DictType):
            return 1 + self._type_complexity(t.key) + self._type_complexity(t.value)
        if isinstance(t, OptionalType):
            return 1 + self._type_complexity(t.inner)
        if isinstance(t, ResultType):
            return 1 + self._type_complexity(t.ok) + self._type_complexity(t.err)
        if isinstance(t, ErrorUnionType):
            return 1 + sum(self._type_complexity(member) for member in t.alternatives)
        if isinstance(t, (StructType, EnumType)) and getattr(t, "type_args", None):
            return 1 + sum(self._type_complexity(a) for a in t.type_args)
        if isinstance(t, TupleType):
            return 1 + sum(self._type_complexity(a) for a in t.elements)
        if isinstance(t, FunctionType):
            return 1 + sum(self._type_complexity(p) for p in t.params) + self._type_complexity(t.ret)
        return 1

    def _check_specialization_size(
        self,
        template_name: str,
        concrete_args: Sequence[WType],
        line: int,
        col: int
    ) -> None:
        total = sum(self._type_complexity(a) for a in concrete_args)
        if total > MAX_SPECIALIZATION_COMPLEXITY:
            raise TypeError(
                message=f"Generic instantiation of '{template_name}' exceeds the maximum "
                        f"type size ({total} > {MAX_SPECIALIZATION_COMPLEXITY}); the "
                        f"specialization chain grows without a structural bound",
                line=line,
                col=col,
                file=self.file,
                code="W2011"
            )

    def _check_specialization_cycle(
        self,
        template_name: str,
        concrete_args: Sequence[WType],
        type_ids: Tuple[int, ...],
        line: int,
        col: int
    ) -> None:
        matching_frames = [f for f in self._instantiation_stack if f[0] == template_name]
        if len(matching_frames) >= 2:
            f0 = matching_frames[-2]
            f1 = matching_frames[-1]
            if len(f0[3]) == len(concrete_args) and len(f1[3]) == len(concrete_args):
                step1_sub = all(_type_contains(fa, fb) for fa, fb in zip(f0[3], f1[3]))
                step1_strict = any(type_strictly_contains(fa, fb) for fa, fb in zip(f0[3], f1[3]))
                step2_sub = all(_type_contains(fb, ca) for fb, ca in zip(f1[3], concrete_args))
                step2_strict = any(type_strictly_contains(fb, ca) for fb, ca in zip(f1[3], concrete_args))
                if step1_sub and step1_strict and step2_sub and step2_strict:
                    start_idx = self._instantiation_stack.index(f0)
                    chain_frames = self._instantiation_stack[start_idx:]
                    chain = [f"{frame[0]}[{', '.join(str(a) for a in frame[3])}]" for frame in chain_frames]
                    chain.append(f"{template_name}[{', '.join(str(a) for a in concrete_args)}]")
                    chain_str = " -> ".join(chain)
                    raise TypeError(
                        message=f"Monomorphization recursion depth limit exceeded (64) / structural generic expansion cycle detected for '{template_name}': instantiation chain {chain_str} expands argument types indefinitely",
                        line=line,
                        col=col,
                        file=self.file,
                        code="W2011"
                    )

        if self._monomorphize_depth >= 64:
            raise TypeError(
                message=f"Monomorphization recursion depth limit exceeded for '{template_name}': maximum instantiation depth reached without proven termination",
                line=line,
                col=col,
                file=self.file,
                code="W2011"
            )

    def _monomorphize_struct(
        self,
        template: GenericStructTemplate,
        concrete_args: List[WType],
        line: int,
        col: int
    ) -> StructType:
        if len(concrete_args) != len(template.type_params):
            raise TypeError(
                message=f"Generic struct '{template.name}' expects {len(template.type_params)} type arguments, found {len(concrete_args)}",
                line=line,
                col=col,
                file=self.file,
                code="T003"
            )

        type_ids = tuple(self.interner.intern(a) for a in concrete_args)
        decl_id = getattr(template, "decl_id", None)
        module_id = getattr(template, "module_id", getattr(self.session, "current_module_id", None))
        key = GenericInstanceKey(template.name, type_ids, module_id=module_id, decl_id=decl_id)
        self.telemetry.specialization_requests += 1

        if key in self.specializations:
            entry = self.specializations[key]
            if entry.state in (SpecializationState.COMPLETE, SpecializationState.SPECIALIZING):
                self.telemetry.deduplicated_hits += 1
                assert entry.specialized_type is not None
                return entry.specialized_type
            elif entry.state == SpecializationState.FAILED:
                raise TypeError(
                    message=f"Previous specialization failed for '{template.name}'",
                    line=line, col=col, file=self.file, code="W2011"
                )

        if key in self.monomorphized_structs:
            self.telemetry.deduplicated_hits += 1
            return self.monomorphized_structs[key]

        self._check_specialization_cycle(template.name, concrete_args, type_ids, line, col)

        # Frame slot 2 is reserved for a per-instantiation size measurement. Nothing
        # consumes it: termination is proven structurally by _check_specialization_cycle
        # and bounded by _monomorphize_depth, so it is recorded as 0 instead of
        # computing a number that is never read.
        curr_complexity = sum(self._type_complexity(a) for a in concrete_args)
        self._check_specialization_size(template.name, concrete_args, line, col)

        # Direct layout recursion detection
        for f in template.ast_decl.fields:
            if isinstance(f.type_ann, (NamedType, GenericType)) and f.type_ann.name == template.name:
                raise TypeError(
                    message=f"Recursive generic struct cycle detected for '{template.name}' without indirection",
                    line=f.line,
                    col=f.col,
                    file=self.file,
                    code="W2011"
                )

        subst: Dict[str, WType] = {}
        for p, arg in zip(template.type_params, concrete_args):
            p_name = p.name if hasattr(p, "name") else str(p)
            p_constraint = getattr(p, "constraint", None)
            if p_constraint:
                self._check_type_constraint(arg, p_constraint, line, col)
            subst[p_name] = arg

        mangled = mangle_generic_name(template.name, concrete_args, module_id)

        struct_t = StructType(name=mangled, fields={})
        struct_t.template_name = template.name
        struct_t.type_args = concrete_args
        entry = SpecializationEntry(key=key, state=SpecializationState.SPECIALIZING, specialized_type=struct_t)
        self.specializations[key] = entry
        self.monomorphized_structs[key] = struct_t
        self.global_scope.define_type(mangled, struct_t, line=line, col=col, file=self.file)

        frame = (template.name, type_ids, curr_complexity, tuple(concrete_args), line, col)
        self._instantiation_stack.append(frame)
        self._monomorphize_depth += 1
        previous_subst = self._active_type_subst
        self._active_type_subst = subst
        try:
            new_fields: List[StructField] = []
            fields_dict: Dict[str, WType] = {}
            for f in template.ast_decl.fields:
                subst_ann = self._substitute_type_node(f.type_ann, subst)
                f_type = self._resolve_type_node(subst_ann)
                fields_dict[f.name] = f_type
                new_fields.append(StructField(name=f.name, type_ann=subst_ann, line=f.line, col=f.col))
            struct_t.fields = fields_dict

            concrete_decl = StructDecl(name=mangled, fields=new_fields, type_params=[], line=template.ast_decl.line, col=template.ast_decl.col)
            self.monomorphized_struct_decls.append(concrete_decl)

            # Synthesize constructor function: fn mangled(f1, f2, ...) -> mangled
            ctor_params = [Param(f.name, f.type_ann, line=f.line, col=f.col) for f in new_fields]
            ctor_inits = [FieldInit(f.name, IdentExpr(f.name, line=f.line, col=f.col), line=f.line, col=f.col) for f in new_fields]
            ctor_ret = StructInitExpr(struct_name=mangled, fields=ctor_inits, line=template.ast_decl.line, col=template.ast_decl.col)
            ctor_body = Block(statements=[ReturnStmt(value=ctor_ret, line=template.ast_decl.line, col=template.ast_decl.col)], line=template.ast_decl.line, col=template.ast_decl.col)
            ctor_fn = FnDecl(
                name=mangled,
                params=ctor_params,
                return_type=NamedType(mangled, line=template.ast_decl.line, col=template.ast_decl.col),
                body=ctor_body,
                type_params=[],
                line=template.ast_decl.line,
                col=template.ast_decl.col
            )
            ctor_p_types = [fields_dict[f.name] for f in new_fields]
            ctor_type = FunctionType(params=ctor_p_types, ret=struct_t)
            ctor_sym = Symbol(mangled, ctor_type, is_mut=False, kind="fn", line=template.ast_decl.line, col=template.ast_decl.col)
            self.global_scope.define_symbol(ctor_sym, file=self.file)
            self._check_fn_decl(ctor_fn)
            self.monomorphized_fn_decls.append(ctor_fn)
            self.telemetry.specialized_structs += 1
            entry.state = SpecializationState.COMPLETE
            entry.ast_decl = concrete_decl

            return struct_t
        except Exception:
            entry.state = SpecializationState.FAILED
            raise
        finally:
            self._monomorphize_depth -= 1
            self._instantiation_stack.pop()
            self._active_type_subst = previous_subst

    def _monomorphize_fn(
        self,
        template: GenericFnTemplate,
        concrete_args: List[WType],
        line: int,
        col: int
    ) -> Symbol:
        if len(concrete_args) != len(template.type_params):
            raise TypeError(
                message=f"Generic function '{template.name}' expects {len(template.type_params)} type arguments, found {len(concrete_args)}",
                line=line,
                col=col,
                file=self.file,
                code="T003"
            )

        type_ids = tuple(self.interner.intern(a) for a in concrete_args)
        decl_id = getattr(template, "decl_id", None)
        module_id = getattr(template, "module_id", getattr(self.session, "current_module_id", None))
        key = GenericInstanceKey(template.name, type_ids, module_id=module_id, decl_id=decl_id)
        self.telemetry.specialization_requests += 1

        if key in self.specializations:
            entry = self.specializations[key]
            if entry.state in (SpecializationState.COMPLETE, SpecializationState.SPECIALIZING):
                self.telemetry.deduplicated_hits += 1
                assert entry.specialized_symbol is not None
                return entry.specialized_symbol
            elif entry.state == SpecializationState.FAILED:
                raise TypeError(
                    message=f"Previous specialization failed for '{template.name}'",
                    line=line, col=col, file=self.file, code="W2011"
                )

        if key in self.monomorphized_fns:
            self.telemetry.deduplicated_hits += 1
            return self.monomorphized_fns[key]

        self._check_specialization_cycle(template.name, concrete_args, type_ids, line, col)

        # Frame slot 2 is reserved for a per-instantiation size measurement. Nothing
        # consumes it: termination is proven structurally by _check_specialization_cycle
        # and bounded by _monomorphize_depth, so it is recorded as 0 instead of
        # computing a number that is never read.
        curr_complexity = sum(self._type_complexity(a) for a in concrete_args)
        self._check_specialization_size(template.name, concrete_args, line, col)

        subst: Dict[str, WType] = {}
        for p, arg in zip(template.type_params, concrete_args):
            p_name = p.name if hasattr(p, "name") else str(p)
            p_constraint = getattr(p, "constraint", None)
            if p_constraint:
                self._check_type_constraint(arg, p_constraint, line, col)
            subst[p_name] = arg

        mangled = mangle_generic_name(template.name, concrete_args, module_id)

        cloned_fn = copy.deepcopy(template.ast_decl)
        cloned_fn.name = mangled
        cloned_fn.type_params = []
        previous_subst = self._active_type_subst
        self._active_type_subst = subst
        try:
            cloned_fn.return_type = self._substitute_type_node(cloned_fn.return_type, subst)
            cloned_fn.params = [
                Param(p.name, self._substitute_type_node(p.type_ann, subst), line=p.line, col=p.col)
                for p in cloned_fn.params
            ]
            self._substitute_ast_types(cloned_fn.body, subst)

            p_types = [self._resolve_type_node(p.type_ann) for p in cloned_fn.params]
            ret_t = self._resolve_type_node(cloned_fn.return_type)
        finally:
            self._active_type_subst = previous_subst
        fn_type = FunctionType(params=p_types, ret=ret_t)
        fn_sym = Symbol(mangled, fn_type, is_mut=False, kind="fn", line=line, col=col)
        entry = SpecializationEntry(key=key, state=SpecializationState.SPECIALIZING, specialized_symbol=fn_sym, ast_decl=cloned_fn)
        self.specializations[key] = entry
        self.monomorphized_fns[key] = fn_sym
        self.global_scope.define_symbol(fn_sym, file=self.file)
        self.monomorphized_fn_decls.append(cloned_fn)
        self.telemetry.specialized_functions += 1

        frame = (template.name, type_ids, curr_complexity, tuple(concrete_args), line, col)
        self._instantiation_stack.append(frame)
        self._monomorphize_depth += 1
        try:
            self._check_fn_decl(cloned_fn)
            entry.state = SpecializationState.COMPLETE
            return fn_sym
        except Exception:
            entry.state = SpecializationState.FAILED
            raise
        finally:
            self._monomorphize_depth -= 1
            self._instantiation_stack.pop()

    def _monomorphize_enum(
        self,
        template: GenericEnumTemplate,
        concrete_args: List[WType],
        line: int,
        col: int
    ) -> EnumType:
        if len(concrete_args) != len(template.type_params):
            raise TypeError(
                message=f"Generic enum '{template.name}' expects {len(template.type_params)} type arguments, found {len(concrete_args)}",
                line=line,
                col=col,
                file=self.file,
                code="T003"
            )

        type_ids = tuple(self.interner.intern(a) for a in concrete_args)
        decl_id = getattr(template, "decl_id", None)
        module_id = getattr(template, "module_id", getattr(self.session, "current_module_id", None))
        key = GenericInstanceKey(template.name, type_ids, module_id=module_id, decl_id=decl_id)
        self.telemetry.specialization_requests += 1

        if key in self.specializations:
            entry = self.specializations[key]
            if entry.state in (SpecializationState.COMPLETE, SpecializationState.SPECIALIZING):
                self.telemetry.deduplicated_hits += 1
                assert entry.specialized_type is not None
                return entry.specialized_type
            elif entry.state == SpecializationState.FAILED:
                raise TypeError(
                    message=f"Previous specialization failed for '{template.name}'",
                    line=line, col=col, file=self.file, code="W2011"
                )

        if key in self.monomorphized_enums:
            self.telemetry.deduplicated_hits += 1
            return self.monomorphized_enums[key]

        self._check_specialization_cycle(template.name, concrete_args, type_ids, line, col)

        # Frame slot 2 is reserved for a per-instantiation size measurement. Nothing
        # consumes it: termination is proven structurally by _check_specialization_cycle
        # and bounded by _monomorphize_depth, so it is recorded as 0 instead of
        # computing a number that is never read.
        curr_complexity = sum(self._type_complexity(a) for a in concrete_args)
        self._check_specialization_size(template.name, concrete_args, line, col)

        subst: Dict[str, WType] = {}
        for p, arg in zip(template.type_params, concrete_args):
            p_name = p.name if hasattr(p, "name") else str(p)
            p_constraint = getattr(p, "constraint", None)
            if p_constraint:
                self._check_type_constraint(arg, p_constraint, line, col)
            subst[p_name] = arg

        mangled = mangle_generic_name(template.name, concrete_args, module_id)

        enum_t = EnumType(name=mangled, variants=[], variant_payloads={})
        enum_t.template_name = template.name
        enum_t.type_args = concrete_args
        entry = SpecializationEntry(key=key, state=SpecializationState.SPECIALIZING, specialized_type=enum_t)
        self.specializations[key] = entry
        self.monomorphized_enums[key] = enum_t
        self.global_scope.define_type(mangled, enum_t, line=line, col=col, file=self.file)

        frame = (template.name, type_ids, curr_complexity, tuple(concrete_args), line, col)
        self._instantiation_stack.append(frame)
        self._monomorphize_depth += 1
        previous_subst = self._active_type_subst
        self._active_type_subst = subst
        try:
            variant_names: List[str] = []
            variant_payloads: Dict[str, List[WType]] = {}
            new_variants: List[VariantDecl] = []

            for v in template.ast_decl.variants:
                v_name = v.name if hasattr(v, "name") else str(v)
                variant_names.append(v_name)
                payload_wtypes: List[WType] = []
                new_payload_types: List[TypeNode] = []
                if hasattr(v, "payload_types") and v.payload_types:
                    for pt in v.payload_types:
                        subst_pt = self._substitute_type_node(pt, subst)
                        resolved_pt = self._resolve_type_node(subst_pt)
                        payload_wtypes.append(resolved_pt)
                        new_payload_types.append(subst_pt)
                variant_payloads[v_name] = payload_wtypes
                new_variants.append(VariantDecl(name=v_name, payload_types=new_payload_types, line=v.line if hasattr(v, "line") else line, col=v.col if hasattr(v, "col") else col))

            enum_t.variants = variant_names
            enum_t.variant_payloads = variant_payloads

            concrete_decl = EnumDecl(name=mangled, variants=new_variants, type_params=[], line=template.ast_decl.line, col=template.ast_decl.col)
            self.monomorphized_enum_decls.append(concrete_decl)
            self.telemetry.specialized_enums += 1
            entry.state = SpecializationState.COMPLETE
            entry.ast_decl = concrete_decl

            return enum_t
        except Exception:
            entry.state = SpecializationState.FAILED
            raise
        finally:
            self._monomorphize_depth -= 1
            self._instantiation_stack.pop()
            self._active_type_subst = previous_subst

    # ==========================================
    # Type Node Resolution
    # ==========================================

    def _is_valid_dict_key_type(self, t: WType) -> bool:
        if isinstance(t, AnyType):
            return True
        if t in (IntType, StrType, BoolType):
            return True
        if isinstance(t, EnumType):
            return all(self._is_valid_dict_key_type(payload)
                       for payloads in t.variant_payloads.values() for payload in payloads)
        return False

    def _resolve_type_node(self, node: TypeNode) -> WType:
        if hasattr(node, 'session_resolved_type'):
            if node.session_arena_id != self.interner.arena_id:
                raise TypeError("Synthesized type belongs to another arena", file=self.file,
                                line=node.line, col=node.col, code="W9999")
            resolved = node.session_resolved_type
        else:
            # Inside a specialization a type-parameter name is bound by `subst`, so it
            # must be resolved from that binding rather than looked up as a declared
            # type: an unbound parameter keeps its own name (see _concrete_type_args)
            # and there is nothing declared to find.
            subst = self._active_type_subst
            if subst and isinstance(node, NamedType) and node.name in subst:
                resolved = subst[node.name]
            else:
                resolved = self._resolve_type_node_impl(node)
        if node is not None:
            node.resolved_type_id = self.interner.from_wtype(resolved)
        return resolved

    def _lookup_type_name(self, name):
        if '.' not in name:
            return self.current_scope.lookup_type(name)
        parts = name.split('.')
        symbol = self.current_scope.lookup_symbol(parts[0])
        module = symbol.type if symbol else None
        for part in parts[1:-1]:
            symbol = module.scope.lookup_symbol(part) if isinstance(module, ModuleType) else None
            module = symbol.type if symbol else None
        return module.scope.lookup_type(parts[-1]) if isinstance(module, ModuleType) else None

    def _resolve_type_node_impl(self, node: TypeNode) -> WType:
        if isinstance(node, AstFunctionType):
            return FunctionType([self._resolve_type_node(p) for p in node.params],
                                self._resolve_type_node(node.return_type))
        if isinstance(node, NamedType):
            if node.name == "any":
                if getattr(node, "is_internal_any", False):
                    return AnyType()
                # `any` is reserved for internal variadic builtin signatures and is
                # deliberately unreachable from source. See checker/WType.py:AnyType.
                raise TypeError(
                    message="Unknown type 'any' (reserved for compiler builtins)",
                    line=node.line,
                    col=node.col,
                    file=self.file,
                    code="W1001",
                )
            resolved = self._lookup_type_name(node.name)
            if resolved is None:
                if node.name in self.generic_enum_templates:
                    raise TypeError(
                        message=f"Generic enum '{node.name}' requires type arguments",
                        line=node.line,
                        col=node.col,
                        file=self.file,
                        code="T003"
                    )
                raise TypeError(
                    message=f"Unknown type '{node.name}'",
                    line=node.line,
                    col=node.col,
                    file=self.file,
                    code="T002"
                )
            if isinstance(resolved, (GenericStructTemplate, GenericEnumTemplate, GenericOopTemplate)):
                raise TypeError(
                    message=f"Generic type '{node.name}' requires type arguments",
                    line=node.line,
                    col=node.col,
                    file=self.file,
                    code="T003"
                )
            return resolved

        if isinstance(node, GenericType):
            if node.name == "Weak":
                if len(node.type_args) != 1:
                    raise TypeError("Weak requires exactly one class type", line=node.line,
                                    col=node.col, file=self.file, code="W2003")
                target = self._resolve_type_node(node.type_args[0])
                if not isinstance(target, ClassType):
                    raise TypeError("Weak target must be a concrete class", line=node.line,
                                    col=node.col, file=self.file, code="W2003")
                return WeakType(target)
            lookup = self._lookup_type_name(node.name)
            if lookup is None:
                lookup = self.generic_struct_templates.get(node.name)
            if lookup is None:
                lookup = self.generic_enum_templates.get(node.name)
            if isinstance(lookup, GenericOopTemplate):
                specialized = specialize_oop(lookup, [self._resolve_type_node(a) for a in node.type_args], node.line, node.col)
                if self.global_scope.lookup_type(specialized.name) is None:
                    self.global_scope.define_type(specialized.name, specialized, file=self.file)
                return specialized
            if isinstance(lookup, GenericStructTemplate):
                resolved_args = [self._resolve_type_node(a) for a in node.type_args]
                return self._monomorphize_struct(lookup, resolved_args, node.line, node.col)
            if isinstance(lookup, GenericEnumTemplate):
                resolved_args = [self._resolve_type_node(a) for a in node.type_args]
                return self._monomorphize_enum(lookup, resolved_args, node.line, node.col)
            raise TypeError(
                message=f"Unknown generic type '{node.name}'",
                line=node.line,
                col=node.col,
                file=self.file,
                code="T002"
            )

        if isinstance(node, AstOptionalType):
            inner = self._resolve_type_node(node.inner)
            return OptionalType(inner)

        if isinstance(node, AstListType):
            elem = self._resolve_type_node(node.element_type)
            return ListType(elem)

        if isinstance(node, AstDictType):
            key_t = self._resolve_type_node(node.key_type)
            if not self._is_valid_dict_key_type(key_t):
                raise TypeError(
                    message=f"Invalid dictionary key type '{key_t}'; allowed key types are int, str, bool, or enum",
                    line=node.key_type.line,
                    col=node.key_type.col,
                    file=self.file,
                    code="W2010"
                )
            val_t = self._resolve_type_node(node.value_type)
            return DictType(key_t, val_t)

        if isinstance(node, AstTupleType):
            elems = [self._resolve_type_node(t) for t in node.element_types]
            return TupleType(elems)

        if isinstance(node, AstResultType):
            ok_t = self._resolve_type_node(node.ok_type)
            if isinstance(node.err_type, AstErrorUnionType):
                err_t = self._resolve_error_union_node(node.err_type)
            else:
                err_t = self._resolve_type_node(node.err_type)
            return ResultType(ok_t, err_t)

        # Type substitution in the canonical Result[T, E] enum can place the
        # error-set node inside a generic payload annotation, even though source
        # syntax only introduces unions after `!`.
        if isinstance(node, AstErrorUnionType):
            return self._resolve_error_union_node(node)

        raise TypeError(
            message=f"Unsupported type construct '{node.__class__.__name__}'",
            line=node.line,
            col=node.col,
            file=self.file,
            code="T002"
        )

    def _resolve_error_union_node(self, node: AstErrorUnionType) -> ErrorUnionType:
        if len(node.error_types) < 2:
            raise TypeError("An error union requires at least two alternatives", line=node.line,
                            col=node.col, file=self.file, code="T003")

        alternatives = [self._resolve_type_node(member) for member in node.error_types]
        for alternative, source_node in zip(alternatives, node.error_types):
            is_scalar = alternative in (IntType, FloatType, BoolType, StrType)
            is_nominal = isinstance(alternative, (StructType, EnumType))
            is_generic_nominal = is_nominal and bool(getattr(alternative, "type_args", ()))
            if not (is_scalar or (is_nominal and not is_generic_nominal)):
                raise TypeError(
                    message=f"Error union alternative '{alternative}' has no distinct runtime type identity; use int, float, bool, str, a non-generic struct, or a non-generic enum",
                    line=source_node.line,
                    col=source_node.col,
                    file=self.file,
                    code="T003"
                )

        union = ErrorUnionType(alternatives)
        if len(union.alternatives) < 2:
            raise TypeError("An error union must contain at least two distinct alternatives",
                            line=node.line, col=node.col, file=self.file, code="T003")
        return union
