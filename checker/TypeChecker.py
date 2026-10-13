import os
from typing import Dict, List, Optional, Set, Tuple
from node.NodeType import (
    Node, Program, Stmt, Expr, TypeNode, Pattern, Block,
    NamedType, OptionalType as AstOptionalType, ListType as AstListType,
    DictType as AstDictType, TupleType as AstTupleType, ResultType as AstResultType,
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
    IfExpr, ElifBranch, MatchExpr, MatchArm
)
from checker.WType import (
    WType, IntType, FloatType, BoolType, StrType, UnitType, NoneType,
    OptionalType, ListType, DictType, TupleType, StructType, EnumType,
    InterfaceType, ClassFieldInfo, ClassMethodInfo, ClassType,
    ResultType, FunctionType, ModuleType, AnyType, is_assignable
)
from checker.SymbolTable import Scope, Symbol, create_global_scope
from error.Error import TypeError

class TypeChecker:
    """
    Two-pass Semantic Analyzer and Type Checker for W Language v0.1.
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
        self.current_class: Optional[ClassType] = None
        self.loop_depth: int = 0
        self.checked_modules: Dict[str, ModuleType] = checked_modules if checked_modules is not None else {}
        self.active_imports: Set[str] = active_imports if active_imports is not None else set()

    def check(self, program: Program) -> None:
        # Pass 1: Collect declarations
        self._pass1_collect_declarations(program)

        # Pass 2: Typecheck bodies & statements
        self._pass2_check_program(program)

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
                seen_variants: Set[str] = set()
                for v in stmt.variants:
                    if v in seen_variants:
                        raise TypeError(
                            message=f"Duplicate variant '{v}' in enum '{stmt.name}'",
                            line=stmt.line,
                            col=stmt.col,
                            file=self.file,
                            code="T008"
                        )
                    seen_variants.add(v)
                enum_type = EnumType(name=stmt.name, variants=stmt.variants)
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


    def _check_block(self, block: Block, is_statement_context: bool = False) -> Optional[WType]:
        block_scope = Scope(parent=self.current_scope)
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

        init_type = self._check_expr(stmt.initializer)

        if stmt.type_ann is not None:
            expected_type = self._resolve_type_node(stmt.type_ann)
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
            sym = self.current_scope.lookup_symbol(expr.name)
            if sym is not None:
                return sym.type
            # Check if referencing an Enum type
            enum_type = self.current_scope.lookup_type(expr.name)
            if enum_type is not None and isinstance(enum_type, EnumType):
                return enum_type
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
            if not isinstance(lhs_t, OptionalType):
                raise TypeError(
                    message=f"Left operand of '??' must be an optional type (T?), found '{lhs_t}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T009"
                )
            rhs_t = self._check_expr(expr.right)
            if not is_assignable(rhs_t, lhs_t.inner):
                raise TypeError(
                    message=f"Right operand of '??' type mismatch: expected '{lhs_t.inner}', found '{rhs_t}'",
                    line=expr.line,
                    col=expr.col,
                    file=self.file,
                    code="T003"
                )
            return lhs_t.inner

        if isinstance(expr, PostfixTryExpr):
            operand_t = self._check_expr(expr.operand)
            if isinstance(operand_t, OptionalType):
                if not isinstance(self.current_fn_ret_type, OptionalType):
                    raise TypeError(
                        message=f"Cannot use '?' on optional in function returning non-optional type '{self.current_fn_ret_type}'",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T010"
                    )
                return operand_t.inner

            if isinstance(operand_t, ResultType):
                if not isinstance(self.current_fn_ret_type, ResultType):
                    raise TypeError(
                        message=f"Cannot use '?' on result in function returning non-result type '{self.current_fn_ret_type}'",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T010"
                    )
                if operand_t.err != self.current_fn_ret_type.err:
                    raise TypeError(
                        message=f"Error type mismatch in '?' propagation: '{operand_t.err}' vs declared '{self.current_fn_ret_type.err}'",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T010"
                    )
                return operand_t.ok

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

            if isinstance(operand_t, ResultType):
                unwrapped_t = operand_t.ok
                bound_err_t = operand_t.err
            elif isinstance(operand_t, OptionalType):
                if expr.err_name is not None:
                    raise TypeError(
                        message=f"Cannot bind error variable '{expr.err_name}' on optional type '{operand_t}'; use 'else {{ ... }}' or '??'",
                        line=expr.line,
                        col=expr.col,
                        file=self.file,
                        code="T009"
                    )
                unwrapped_t = operand_t.inner
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
            # Support direct constructor call syntax: ClassName(...)
            if isinstance(expr.callee, IdentExpr):
                if self.current_scope.lookup_symbol(expr.callee.name) is None:
                    maybe_cls = self.current_scope.lookup_type(expr.callee.name)
                    if isinstance(maybe_cls, ClassType):
                        return self._check_class_instantiation(maybe_cls, expr.args, expr.line, expr.col)

            # Mutating method check on receiver (transitive across value-type paths)
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
                    code="W2001"
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
                        code="W2001"
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

            for arm in expr.arms:
                if isinstance(arm.pattern, WildcardPattern):
                    has_wildcard = True
                elif isinstance(arm.pattern, EnumPattern):
                    if not isinstance(subject_t, EnumType) or arm.pattern.enum_name != subject_t.name:
                        raise TypeError(
                            message=f"Pattern '{arm.pattern.enum_name}' is incompatible with match subject '{subject_t}'",
                            line=arm.line,
                            col=arm.col,
                            file=self.file,
                            code="T003"
                        )
                    if arm.pattern.variant not in subject_t.variants:
                        raise TypeError(
                            message=f"Enum '{subject_t.name}' has no variant '{arm.pattern.variant}'",
                            line=arm.line,
                            col=arm.col,
                            file=self.file,
                            code="T001"
                        )
                    covered_variants.add(arm.pattern.variant)
                elif isinstance(arm.pattern, LiteralPattern):
                    lit_t = self._check_expr(arm.pattern.literal)
                    if not is_assignable(lit_t, subject_t):
                        raise TypeError(
                            message=f"Literal pattern type '{lit_t}' incompatible with subject '{subject_t}'",
                            line=arm.line,
                            col=arm.col,
                            file=self.file,
                            code="T003"
                        )

                arm_t = self._check_block(arm.body) or UnitType
                arm_types.append(arm_t)

            # Exhaustiveness check for Enum
            if isinstance(subject_t, EnumType) and not has_wildcard:
                missing = [v for v in subject_t.variants if v not in covered_variants]
                if missing:
                    raise TypeError(
                        message=f"Non-exhaustive match on enum '{subject_t.name}'. Missing: {', '.join(missing)}",
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
            resolved = self.current_scope.lookup_type(node.name)
            if resolved is None:
                raise TypeError(
                    message=f"Unknown type '{node.name}'",
                    line=node.line,
                    col=node.col,
                    file=self.file,
                    code="T002"
                )
            return resolved

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
                    code="W2001"
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
