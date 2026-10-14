import copy
import os
from typing import Any, Dict, List, Optional, Set, Tuple, NamedTuple
from node.NodeType import (
    Node, Program, Stmt, Expr, TypeNode, Pattern, Block,
    NamedType, OptionalType as AstOptionalType, ListType as AstListType,
    DictType as AstDictType, TupleType as AstTupleType, ResultType as AstResultType,
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
    OptionalType, ListType, DictType, TupleType, StructType, EnumType,
    InterfaceType, ClassFieldInfo, ClassMethodInfo, ClassType,
    ResultType, FunctionType, ModuleType, AnyType,
    TypeParamType, GenericStructTemplate, GenericFnTemplate, GenericEnumTemplate, is_assignable
)
from checker.SymbolTable import Scope, Symbol, create_global_scope
from checker.TypeInterner import TypeInterner
from error.Error import TypeError


class GenericInstanceKey(NamedTuple):
    """Session-local specialization identity; not a persistent hash or ABI name."""
    template_name: str
    type_ids: Tuple[int, ...]


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
        checked_modules: Optional[Dict[str, ModuleType]] = None,
        active_imports: Optional[Set[str]] = None
    ) -> None:
        self.file = file
        self.global_scope = create_global_scope()
        self.current_scope = self.global_scope
        self.current_fn_ret_type: Optional[WType] = None
        self.expected_type: Optional[WType] = None
        self.current_class: Optional[ClassType] = None
        self.loop_depth: int = 0
        self.checked_modules: Dict[str, ModuleType] = checked_modules if checked_modules is not None else {}
        self.active_imports: Set[str] = active_imports if active_imports is not None else set()
        self.interner: TypeInterner = TypeInterner()
        self.generic_struct_templates: Dict[str, GenericStructTemplate] = {}
        self.generic_fn_templates: Dict[str, GenericFnTemplate] = {}
        self.generic_enum_templates: Dict[str, GenericEnumTemplate] = {}
        self.monomorphized_structs: Dict[GenericInstanceKey, StructType] = {}
        self.monomorphized_fns: Dict[GenericInstanceKey, Symbol] = {}
        self.monomorphized_enums: Dict[GenericInstanceKey, EnumType] = {}
        self.monomorphized_struct_decls: List[StructDecl] = []
        self.monomorphized_fn_decls: List[FnDecl] = []
        self.monomorphized_enum_decls: List[EnumDecl] = []
        self._monomorphize_depth: int = 0
        self._instantiation_stack: List[Tuple[str, Tuple[int, ...], int]] = []
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
        # Pass 1: Collect declarations
        self._pass1_collect_declarations(program)

        # Pass 2: Typecheck bodies & statements
        self._pass2_check_program(program)

        # Filter out uninstantiated generic templates and insert monomorphized declarations
        filtered_body: List[Stmt] = []
        for stmt in program.body:
            if isinstance(stmt, (StructDecl, FnDecl, EnumDecl)) and stmt.type_params:
                continue
            filtered_body.append(stmt)

        final_body: List[Stmt] = []
        final_body.extend(self.monomorphized_struct_decls)
        final_body.extend(self.monomorphized_enum_decls)
        final_body.extend(self.monomorphized_fn_decls)
        final_body.extend(filtered_body)
        program.body = final_body

        program.interner = self.interner

    # ==========================================
    # Pass 1: Collect Top-Level Declarations
    # ==========================================

    def _resolve_import(self, stmt: ImportDecl) -> WType:
        current_dir = os.path.dirname(os.path.abspath(self.file)) if self.file not in ("<stdin>", "<repl>") else os.getcwd()
        candidate = os.path.abspath(os.path.join(current_dir, stmt.path))
        if not os.path.exists(candidate):
            candidate = os.path.abspath(stmt.path)

        if not os.path.exists(candidate):
            raise TypeError(
                message=f"Module not found: '{stmt.path}'",
                line=stmt.line,
                col=stmt.col,
                file=self.file,
                code="W1003"
            )

        if candidate in self.active_imports:
            raise TypeError(
                message=f"Circular import detected for module '{stmt.path}'",
                line=stmt.line,
                col=stmt.col,
                file=self.file,
                code="W1003"
            )

        if candidate in self.checked_modules:
            cached = self.checked_modules[candidate]
            return ModuleType(stmt.namespace, cached.scope)

        with open(candidate, "r", encoding="utf-8") as f:
            source = f.read()

        from parser.Parser import Parser
        sub_ast = Parser(file=candidate).parse(source)
        sub_checker = TypeChecker(
            file=candidate,
            checked_modules=self.checked_modules,
            active_imports=self.active_imports | {candidate}
        )
        sub_checker.check(sub_ast)

        mod_type = ModuleType(stmt.namespace, sub_checker.global_scope)
        self.checked_modules[candidate] = mod_type
        return mod_type

    def _pass1_collect_declarations(self, program: Program) -> None:
        # Step 1a: Pre-register nominal type shells (Enums, Interfaces, Classes, Imports)
        for stmt in program.body:
            if isinstance(stmt, EnumDecl):
                if stmt.type_params:
                    template = GenericEnumTemplate(stmt.name, stmt.type_params, stmt)
                    self.generic_enum_templates[stmt.name] = template
                    self.global_scope.define_type(stmt.name, template, line=stmt.line, col=stmt.col, file=self.file)
                    continue

                seen_variants: Set[str] = set()
                variant_names: List[str] = []
                variant_payloads: Dict[str, List[WType]] = {}
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
                    payload_wtypes: List[WType] = []
                    if hasattr(v, "payload_types") and v.payload_types:
                        for pt in v.payload_types:
                            payload_wtypes.append(self._resolve_type_node(pt))
                    variant_payloads[v_name] = payload_wtypes

                enum_type = EnumType(name=stmt.name, variants=variant_names, variant_payloads=variant_payloads)
                self.global_scope.define_type(stmt.name, enum_type, line=stmt.line, col=stmt.col, file=self.file)

            elif isinstance(stmt, InterfaceDecl):
                intf_type = InterfaceType(name=stmt.name)
                self.global_scope.define_type(stmt.name, intf_type, line=stmt.line, col=stmt.col, file=self.file)

            elif isinstance(stmt, ClassDecl):
                cls_type = ClassType(name=stmt.name)
                self.global_scope.define_type(stmt.name, cls_type, line=stmt.line, col=stmt.col, file=self.file)

            elif isinstance(stmt, ImportDecl):
                mod_type = self._resolve_import(stmt)
                self.global_scope.define_symbol(
                    Symbol(stmt.namespace, mod_type, is_mut=False, kind="import", line=stmt.line, col=stmt.col),
                    file=self.file
                )

        # Step 1b: Resolve Structs and Interface method signatures
        for stmt in program.body:
            if isinstance(stmt, StructDecl):
                if stmt.type_params:
                    template = GenericStructTemplate(name=stmt.name, type_params=stmt.type_params, ast_decl=stmt)
                    self.generic_struct_templates[stmt.name] = template
                    self.global_scope.define_type(stmt.name, template, line=stmt.line, col=stmt.col, file=self.file)
                else:
                    fields_dict: Dict[str, WType] = {}
                    for f in stmt.fields:
                        if f.name in fields_dict:
                            raise TypeError(
                                message=f"Duplicate field '{f.name}' in struct '{stmt.name}'",
                                line=f.line,
                                col=f.col,
                                file=self.file,
                                code="T014"
                            )
                        f_type = self._resolve_type_node(f.type_ann)
                        fields_dict[f.name] = f_type
                    struct_type = StructType(name=stmt.name, fields=fields_dict)
                    self.global_scope.define_type(stmt.name, struct_type, line=stmt.line, col=stmt.col, file=self.file)

            elif isinstance(stmt, InterfaceDecl):
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

        # Step 1c: Resolve Class hierarchies, fields, methods, and top-level Functions
        class_decls: List[ClassDecl] = []
        for stmt in program.body:
            if isinstance(stmt, ClassDecl):
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

                # Own fields & methods first
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
                merged_fields[fname] = finfo
            for mname, minfo in cls_type.methods.items():
                if mname in merged_methods:
                    base_m = merged_methods[mname]
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
            val_t = self._check_expr(stmt.value) if stmt.value else UnitType
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

    def _check_class_decl(self, stmt: ClassDecl) -> None:
        cls_type = self.global_scope.lookup_type(stmt.name)
        assert isinstance(cls_type, ClassType)
        old_class = self.current_class
        self.current_class = cls_type
        try:
            for m in stmt.methods:
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

        try:
            for s in block.statements:
                self._check_stmt(s)
            if block.tail_expr:
                return self._check_expr(block.tail_expr, is_statement_context=is_statement_context)
            return None
        finally:
            self.current_scope = old_scope

    def _check_let_decl(self, stmt: LetDecl) -> None:
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

    def _check_expr(self, expr: Expr, is_statement_context: bool = False) -> WType:
        wtype = self._check_expr_impl(expr, is_statement_context)
        try:
            expr.inferred_type = wtype
            expr.inferred_type_id = self.interner.from_wtype(wtype)
        except Exception:
            pass
        return wtype

    def _check_expr_impl(self, expr: Expr, is_statement_context: bool = False) -> WType:
        if isinstance(expr, IntLiteral):
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
                return sym.type
            # Check if referencing an Enum type
            enum_type = self.current_scope.lookup_type(expr.name)
            if enum_type is not None and isinstance(enum_type, EnumType):
                return enum_type
            # Check if referencing an unqualified enum variant
            for t in self.global_scope.types.values():
                if isinstance(t, EnumType) and expr.name in t.variants:
                    return t
            for tmpl in self.generic_enum_templates.values():
                var_names = [v.name if hasattr(v, "name") else str(v) for v in tmpl.ast_decl.variants]
                if expr.name in var_names:
                    if tmpl.name == "Option" and expr.name in ("None", "none"):
                        return NoneType
                    concrete_args = [AnyType() for _ in tmpl.type_params]
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
                if not is_assignable(lhs_t, rhs_t) and not is_assignable(rhs_t, lhs_t):
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
            rhs_t = self._check_expr(expr.right)
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
                if res_err != cur_err:
                    raise TypeError(
                        message=f"Error type mismatch in '?' propagation: '{res_err}' vs declared '{cur_err}'",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T010"
                    )
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
                            code="T012"
                        )
                    if not is_assignable(val_t, f_info.type):
                        raise TypeError(
                            message=f"Type mismatch on field '{expr.target.property}': expected '{f_info.type}', found '{val_t}'",
                            line=expr.line,
                            col=expr.col,
                            file=self.file,
                            code="T003"
                        )
                    return f_info.type

                sym = self._find_value_root_symbol(expr.target.object)
                if sym and not sym.is_mut:
                    raise TypeError(
                        message=f"Cannot mutate field of immutable binding '{sym.name}'",
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
                    concrete_args = [AnyType() for _ in tmpl.type_params]
                    return self._monomorphize_enum(tmpl, concrete_args, expr.line, expr.col)

            obj_t = self._check_expr(expr.object)
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
                            code="T012"
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
                            code="T012"
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
                return OptionalType(obj_t.value)
            raise TypeError(
                message=f"Cannot index type '{obj_t}'",
                line=expr.line,
                col=expr.col,
                file=self.file,
                code="T005"
            )

        if isinstance(expr, CallExpr):
            # Support generic function calls and generic struct constructors
            callee_t: Optional[WType] = None
            if isinstance(expr.callee, IdentExpr):
                callee_name = expr.callee.name
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
                            self._unify_type(p_decl.type_ann, a_type, type_params_set, bindings)
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
                        concrete_args = [bindings[p.name if hasattr(p, "name") else str(p)] for p in template.type_params]

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
                            self._unify_type(f_decl.type_ann, a_type, type_params_set, bindings)
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
                        concrete_args = [bindings[p.name if hasattr(p, "name") else str(p)] for p in template.type_params]

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
                    arg_t = self._check_expr(expr.args[0])
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
                    arg_t = self._check_expr(expr.args[0])
                    err_t = AnyType()
                    ctx_t = self.expected_type or self.current_fn_ret_type
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
                    err_t = self._check_expr(expr.args[0])
                    ok_t = AnyType()
                    ctx_t = self.expected_type or self.current_fn_ret_type
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
                        concrete_args = [bindings[p.name if hasattr(p, "name") else str(p)] for p in found_tmpl.type_params]
                        enum_t = self._monomorphize_enum(found_tmpl, concrete_args, expr.line, expr.col)
                        expr.callee = MemberExpr(IdentExpr(enum_t.name, line=expr.line, col=expr.col), callee_name, line=expr.line, col=expr.col)
                        expr.type_args = []
                        return enum_t

                    if expr.type_args:
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
                    for pt, a_expr in zip(payload_types, expr.args):
                        a_type = self._check_expr(a_expr)
                        self._unify_type(pt, a_type, type_params_set, bindings)
                    ctx_t = self.expected_type or self.current_fn_ret_type
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
                    concrete_args = [bindings[p.name if hasattr(p, "name") else str(p)] for p in template.type_params]

                enum_t = self._monomorphize_enum(template, concrete_args, expr.line, expr.col)
                expr.callee.object.name = enum_t.name
                expr.type_args = []
                return enum_t

            # Mutating method check on receiver (transitive across value-type paths)
            if callee_t is None:
                if isinstance(expr.callee, MemberExpr):
                    callee_t = self._check_expr(expr.callee)
                    if isinstance(callee_t, FunctionType) and callee_t.is_mutating:
                        sym = self._find_value_root_symbol(expr.callee.object)
                        if sym and not sym.is_mut:
                            raise TypeError(
                                message=f"Cannot call mutating method '{expr.callee.property}' on immutable binding '{sym.name}'",
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
                raise TypeError(
                    message=f"Cannot call non-function of type '{callee_t}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T015"
                )


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
                a_type = self._check_expr(a_expr)
                if not is_assignable(a_type, p_type):
                    raise TypeError(
                        message=f"Argument {i + 1} type mismatch: expected '{p_type}', found '{a_type}'",
                        line=a_expr.line,
                        col=a_expr.col,
                        file=self.file,
                        code="T003"
                    )
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
                            self._unify_type(template_fields[f.name], a_t, type_params_set, bindings)
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
                    concrete_args = [bindings[p.name if hasattr(p, "name") else str(p)] for p in template.type_params]

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
            return struct_t

        if isinstance(expr, ListExpr):
            if len(expr.elements) == 0:
                return ListType(AnyType())
            elem_types = [self._check_expr(e) for e in expr.elements]
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
            if len(expr.entries) == 0:
                return DictType(AnyType(), AnyType())
            first_key_t = self._check_expr(expr.entries[0].key)
            if not self._is_valid_dict_key_type(first_key_t):
                raise TypeError(
                    message=f"Invalid dictionary key type '{first_key_t}'; allowed key types are int, str, bool, or enum",
                    line=expr.entries[0].key.line,
                    col=expr.entries[0].key.col,
                    file=self.file,
                    code="W2010"
                )
            first_val_t = self._check_expr(expr.entries[0].value)
            for entry in expr.entries[1:]:
                kt = self._check_expr(entry.key)
                vt = self._check_expr(entry.value)
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
                arm_bindings: Dict[str, WType] = {}

                if isinstance(arm.pattern, WildcardPattern):
                    has_wildcard = True

                elif isinstance(arm.pattern, IdentifierPattern):
                    if arm.pattern.name in ("None", "none") and expected_variants and "None" in expected_variants:
                        covered_variants.add("None")
                    else:
                        has_wildcard = True
                        arm_bindings[arm.pattern.name] = subject_t

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

                arm_t = self._check_block(arm.body, initial_bindings=arm_bindings) or UnitType
                arm_types.append(arm_t)

            # Exhaustiveness check
            if expected_variants is not None and not has_wildcard:
                missing = [v for v in expected_variants if v not in covered_variants]
                if missing:
                    raise TypeError(
                        message=f"Non-exhaustive match on '{subject_t}'. Missing: {', '.join(missing)}",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T007"
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

    def _bind_pattern_type(self, pattern: Pattern, expected_type: WType, bindings: Dict[str, WType], line: int, col: int) -> None:
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

    def _mangle_type_name(self, t: WType) -> str:
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
        if isinstance(t, StructType):
            return t.name
        if isinstance(t, EnumType):
            return t.name
        if isinstance(t, ClassType):
            return t.name
        if isinstance(t, InterfaceType):
            return t.name
        if isinstance(t, OptionalType):
            return f"opt__{self._mangle_type_name(t.inner)}"
        if isinstance(t, ListType):
            return f"list__{self._mangle_type_name(t.element)}"
        if isinstance(t, DictType):
            return f"dict__{self._mangle_type_name(t.key)}__{self._mangle_type_name(t.value)}"
        if isinstance(t, TupleType):
            elems = "__".join(self._mangle_type_name(e) for e in t.elements)
            return f"tuple__{elems}"
        if isinstance(t, ResultType):
            return f"res__{self._mangle_type_name(t.ok)}__{self._mangle_type_name(t.err)}"
        if isinstance(t, TypeParamType):
            return t.name
        return str(t).replace("[", "__").replace("]", "").replace(", ", "__").replace(" ", "_")

    def _wtype_to_type_node(self, t: WType) -> TypeNode:
        if isinstance(t, AnyType):
            return NamedType("any")
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
        if isinstance(t, TypeParamType):
            return NamedType(t.name)
        return NamedType(str(t))

    def _substitute_type_node(self, node: TypeNode, subst: Dict[str, WType]) -> TypeNode:
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
        return node

    def _substitute_ast_types(self, node: Any, subst: Dict[str, WType]) -> None:
        if node is None:
            return
        if isinstance(node, LetDecl):
            if node.type_ann is not None:
                node.type_ann = self._substitute_type_node(node.type_ann, subst)
            self._substitute_ast_types(node.init, subst)
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

        if isinstance(param_type_node, GenericType) and isinstance(arg_wtype, (StructType, EnumType)):
            tmpl_name = getattr(arg_wtype, "template_name", None)
            tmpl_args = getattr(arg_wtype, "type_args", None)
            if tmpl_name == param_type_node.name and tmpl_args and len(tmpl_args) == len(param_type_node.type_args):
                return all(self._unify_type(pt, at, type_params, bindings)
                           for pt, at in zip(param_type_node.type_args, tmpl_args))

        return True

    def _check_type_constraint(self, type_arg: WType, constraint: Optional[TypeNode], line: int, col: int) -> None:
        if constraint is None:
            return
        c_name = constraint.name if isinstance(constraint, NamedType) else str(constraint)
        c_type = self.global_scope.lookup_type(c_name)
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
        if isinstance(t, ListType):
            return 1 + self._type_complexity(t.element)
        if isinstance(t, DictType):
            return 1 + self._type_complexity(t.key) + self._type_complexity(t.value)
        if isinstance(t, OptionalType):
            return 1 + self._type_complexity(t.inner)
        if isinstance(t, ResultType):
            return 1 + self._type_complexity(t.ok) + self._type_complexity(t.err)
        if isinstance(t, (StructType, EnumType)) and getattr(t, "type_args", None):
            return 1 + sum(self._type_complexity(a) for a in t.type_args)
        if isinstance(t, TupleType):
            return 1 + sum(self._type_complexity(a) for a in t.elements)
        if isinstance(t, FunctionType):
            return 1 + sum(self._type_complexity(p) for p in t.params) + self._type_complexity(t.ret)
        return 1

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
        key = GenericInstanceKey(template.name, type_ids)
        self.telemetry.specialization_requests += 1

        if key in self.monomorphized_structs:
            self.telemetry.deduplicated_hits += 1
            return self.monomorphized_structs[key]

        if self._monomorphize_depth >= 64:
            raise TypeError(
                message=f"Monomorphization recursion depth limit exceeded for struct '{template.name}'",
                line=line,
                col=col,
                file=self.file,
                code="W2011"
            )

        curr_complexity = sum(self._type_complexity(a) for a in concrete_args)

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

        mangled = f"{template.name}__{'__'.join(self._mangle_type_name(a) for a in concrete_args)}"

        struct_t = StructType(name=mangled, fields={})
        struct_t.template_name = template.name
        struct_t.type_args = concrete_args
        self.monomorphized_structs[key] = struct_t
        self.global_scope.define_type(mangled, struct_t, line=line, col=col, file=self.file)

        self._instantiation_stack.append((template.name, type_ids, curr_complexity))
        self._monomorphize_depth += 1
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
            self.monomorphized_fn_decls.append(ctor_fn)
            self.telemetry.specialized_structs += 1

            return struct_t
        finally:
            self._monomorphize_depth -= 1
            self._instantiation_stack.pop()

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
        key = GenericInstanceKey(template.name, type_ids)
        self.telemetry.specialization_requests += 1

        if key in self.monomorphized_fns:
            self.telemetry.deduplicated_hits += 1
            return self.monomorphized_fns[key]

        if self._monomorphize_depth >= 64:
            raise TypeError(
                message=f"Monomorphization recursion depth limit exceeded for function '{template.name}'",
                line=line,
                col=col,
                file=self.file,
                code="W2011"
            )

        curr_complexity = sum(self._type_complexity(a) for a in concrete_args)

        subst: Dict[str, WType] = {}
        for p, arg in zip(template.type_params, concrete_args):
            p_name = p.name if hasattr(p, "name") else str(p)
            p_constraint = getattr(p, "constraint", None)
            if p_constraint:
                self._check_type_constraint(arg, p_constraint, line, col)
            subst[p_name] = arg

        mangled = f"{template.name}__{'__'.join(self._mangle_type_name(a) for a in concrete_args)}"

        cloned_fn = copy.deepcopy(template.ast_decl)
        cloned_fn.name = mangled
        cloned_fn.type_params = []
        cloned_fn.return_type = self._substitute_type_node(cloned_fn.return_type, subst)
        cloned_fn.params = [
            Param(p.name, self._substitute_type_node(p.type_ann, subst), line=p.line, col=p.col)
            for p in cloned_fn.params
        ]
        self._substitute_ast_types(cloned_fn.body, subst)

        p_types = [self._resolve_type_node(p.type_ann) for p in cloned_fn.params]
        ret_t = self._resolve_type_node(cloned_fn.return_type)
        fn_type = FunctionType(params=p_types, ret=ret_t)
        fn_sym = Symbol(mangled, fn_type, is_mut=False, kind="fn", line=line, col=col)
        self.monomorphized_fns[key] = fn_sym
        self.global_scope.define_symbol(fn_sym, file=self.file)
        self.monomorphized_fn_decls.append(cloned_fn)
        self.telemetry.specialized_functions += 1

        self._instantiation_stack.append((template.name, type_ids, curr_complexity))
        self._monomorphize_depth += 1
        try:
            self._check_fn_decl(cloned_fn)
            return fn_sym
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
        key = GenericInstanceKey(template.name, type_ids)
        self.telemetry.specialization_requests += 1

        if key in self.monomorphized_enums:
            self.telemetry.deduplicated_hits += 1
            return self.monomorphized_enums[key]

        if self._monomorphize_depth >= 64:
            raise TypeError(
                message=f"Monomorphization recursion depth limit exceeded for enum '{template.name}'",
                line=line,
                col=col,
                file=self.file,
                code="W2011"
            )

        curr_complexity = sum(self._type_complexity(a) for a in concrete_args)

        self._instantiation_stack.append((template.name, type_ids, curr_complexity))
        self._monomorphize_depth += 1
        try:
            subst: Dict[str, WType] = {}
            for p, arg in zip(template.type_params, concrete_args):
                p_name = p.name if hasattr(p, "name") else str(p)
                p_constraint = getattr(p, "constraint", None)
                if p_constraint:
                    self._check_type_constraint(arg, p_constraint, line, col)
                subst[p_name] = arg

            arg_mangles = [self._mangle_type_name(a) for a in concrete_args]
            mangled = f"{template.name}__{'__'.join(arg_mangles)}"

            enum_t = EnumType(name=mangled, variants=[], variant_payloads={})
            enum_t.template_name = template.name
            enum_t.type_args = concrete_args
            self.monomorphized_enums[key] = enum_t
            self.global_scope.define_type(mangled, enum_t, line=line, col=col, file=self.file)

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
                        # Infinite recursive layout rule: T025
                        if isinstance(pt, (NamedType, GenericType)) and pt.name == template.name:
                            raise TypeError(
                                message=f"Recursive ADT variant '{v_name}' contains '{template.name}' directly without indirection; use 'Box[...]'",
                                line=v.line if hasattr(v, "line") else line,
                                col=v.col if hasattr(v, "col") else col,
                                file=self.file,
                                code="T025"
                            )
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

            return enum_t
        finally:
            self._monomorphize_depth -= 1
            self._instantiation_stack.pop()

    # ==========================================
    # Type Node Resolution
    # ==========================================

    def _is_valid_dict_key_type(self, t: WType) -> bool:
        if isinstance(t, AnyType):
            return True
        if t in (IntType, StrType, BoolType):
            return True
        if isinstance(t, EnumType):
            return True
        return False

    def _resolve_type_node(self, node: TypeNode) -> WType:
        if isinstance(node, NamedType):
            if node.name == "any":
                return AnyType()
            resolved = self.current_scope.lookup_type(node.name)
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
            if isinstance(resolved, (GenericStructTemplate, GenericEnumTemplate)):
                raise TypeError(
                    message=f"Generic type '{node.name}' requires type arguments",
                    line=node.line,
                    col=node.col,
                    file=self.file,
                    code="T003"
                )
            return resolved

        if isinstance(node, GenericType):
            lookup = self.current_scope.lookup_type(node.name)
            if lookup is None:
                lookup = self.generic_struct_templates.get(node.name)
            if lookup is None:
                lookup = self.generic_enum_templates.get(node.name)
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
            err_t = self._resolve_type_node(node.err_type)
            return ResultType(ok_t, err_t)

        raise TypeError(
            message=f"Unsupported type construct '{node.__class__.__name__}'",
            line=node.line,
            col=node.col,
            file=self.file,
            code="T002"
        )
