from error.Error import WError
from typing import Any, Dict, List, Optional, Tuple, Set
from node.NodeType import (
    Program, Stmt, Expr, TypeNode, ResultType as AstResultType,
    NamedType, OptionalType as AstOptionalType, ListType as AstListType, DictType as AstDictType,
    GenericType,
    Pattern, IdentifierPattern, TuplePattern, EnumPattern, LiteralPattern, WildcardPattern,
    Block, ExprStmt, Param, FnDecl, StructDecl, EnumDecl, ImportDecl,
    InterfaceDecl, ClassDecl, ClassField, MethodDecl,
    LetDecl, WhileStmt, ForStmt, ReturnStmt, BreakStmt, ContinueStmt,
    IntLiteral, FloatLiteral, StringLiteral, BoolLiteral, NoneLiteral, IdentExpr,
    ThisExpr, SuperExpr, NewExpr,
    UnaryExpr, BinaryExpr, CoalesceExpr, RangeExpr, PostfixTryExpr, ElseErrExpr,
    CallExpr, MemberExpr, IndexExpr, AssignmentExpr, StructInitExpr,
    ListExpr, DictExpr, TupleExpr, IfExpr, MatchExpr
)
from checker.TypeInterner import (
    TypeInterner, TYPE_ERROR, TYPE_UNIT, TYPE_BOOL, TYPE_INT, TYPE_FLOAT, TYPE_STR, TYPE_NONE
)
from hir.HirNodes import (
    Span, HirNode, HirExpr, HirStmt, HirParam, HirBlock, HirFieldDef,
    HirFnDecl, HirStructDecl, HirEnumDecl, HirInterfaceDecl, HirClassDecl, HirModule,
    HirLet, HirBindTemp, HirAssign, HirWhile, HirForList, HirReturn, HirBreak, HirContinue, HirExprStmt,
    HirConstInt, HirConstFloat, HirConstBool, HirConstStr, HirConstNone, HirConstUnit,
    HirLocalRef, HirThisRef, HirSuperRef, HirUnaryOp, HirBinaryOp,
    HirConstructStruct, HirConstructEnum, HirConstructObject, HirConstructList, HirConstructDict, HirConstructTuple,
    HirDirectCall, HirBuiltinCall, HirMethodCall, HirFieldRead, HirIndexRead,
    HirTryPropagate, HirCoalesce, HirElseHandle, HirIf, HirMatch, HirMatchArm, HirRange
)


BUILTIN_NAMES = {
    "weak", "upgrade", "print", "eprint", "len", "range", "ord", "chr", "slice", "str", "int", "float", "bool",
    "bytes", "args", "exit", "enumerate", "dict_items", "read_file", "write_file",
    "w_read_file", "w_write_file"
}


class HirBuilder:
    """
    Lowers a fully type-checked surface AST into a canonical Typed HIR.
    Invariants guaranteed:
    1. Every HirExpr carries an interned TypeId.
    2. Constructors ClassName(...) and new ClassName(...) are normalized to HirConstructObject.
    3. Missing function return expressions are normalized to HirConstUnit.
    4. Method calls and member accesses are categorized.
    """
    def __init__(self, interner: TypeInterner, file_path: str = "<stdin>"):
        self.interner = interner
        self.file_path = file_path
        self.classes: Set[str] = set()
        self.structs: Set[str] = set()
        self.enums: Set[str] = {"Option", "Result"}
        self.enum_variants: Dict[str, str] = {
            "Some": "Option",
            "None": "Option",
            "Ok": "Result",
            "Err": "Result",
        }
        self.modules: Set[str] = set()
        self.imported_files: Set[str] = set()

    def _span(self, node):
        return Span(node.line, node.col, file_path=getattr(node, 'source_file', self.file_path),
                    file_id=getattr(node, 'module_id', None))

    def lower(self, program: Program) -> HirModule:
        if hasattr(program, "session"):
            if self.interner is not program.session.interner:
                raise WError("HIR builder must use the checked module arena", file=self.file_path,
                             code="W9999", stage="hir-lowering")
            program = program.session.link(program)
        # Pre-scan top-level nominal types to distinguish constructors from calls
        for stmt in program.body:
            if isinstance(stmt, ClassDecl):
                self.classes.add(stmt.name)
            elif isinstance(stmt, StructDecl):
                self.structs.add(stmt.name)
            elif isinstance(stmt, EnumDecl):
                self.enums.add(stmt.name)
                for v in stmt.variants:
                    v_name = v.name if hasattr(v, "name") else str(v)
                    self.enum_variants[v_name] = stmt.name

        struct_decls: List[HirStructDecl] = []
        enum_decls: List[HirEnumDecl] = []
        intf_decls: List[HirInterfaceDecl] = []
        class_decls: List[HirClassDecl] = []
        fn_decls: List[HirFnDecl] = []
        top_stmts: List[HirStmt] = []

        for stmt in program.body:
            if isinstance(stmt, StructDecl):
                struct_decls.append(self._lower_struct_decl(stmt))
            elif isinstance(stmt, EnumDecl):
                enum_decls.append(self._lower_enum_decl(stmt))
            elif isinstance(stmt, InterfaceDecl):
                intf_decls.append(self._lower_interface_decl(stmt))
            elif isinstance(stmt, ClassDecl):
                class_decls.append(self._lower_class_decl(stmt))
            elif isinstance(stmt, FnDecl):
                fn_decls.append(self._lower_fn_decl(stmt))
            elif isinstance(stmt, ImportDecl):
                self._handle_import(stmt, fn_decls)
            else:
                top_stmts.append(self._lower_stmt(stmt))

        module = HirModule(
            file_path=self.file_path,
            structs=struct_decls,
            enums=enum_decls,
            interfaces=intf_decls,
            classes=class_decls,
            functions=fn_decls,
            top_level_stmts=top_stmts
        )
        module.arena_id = self.interner.arena_id
        module.call_entrypoint = getattr(program, "call_entrypoint", not top_stmts)
        from hir.HirVerifier import HirVerifier
        HirVerifier(self.interner, self.file_path).verify(module)
        return module

    def _handle_import(self, stmt: ImportDecl, fn_decls: List[HirFnDecl]) -> None:
        raise WError("HIR imports require a checked compilation session", file=self.file_path,
                     line=stmt.line, col=stmt.col, code="W9999", stage="hir-lowering")

    # -------------------------------------------------------------
    # Nominal Declarations
    # -------------------------------------------------------------

    def _lower_struct_decl(self, decl: StructDecl) -> HirStructDecl:
        tid = self.interner.mk_struct(decl.name)
        fields = [
            HirFieldDef(f.name, self._get_type_id_from_node(getattr(f, "type_ann", getattr(f, "type_annotation", None))), is_public=True, span=self._span(f))
            for f in decl.fields
        ]
        return HirStructDecl(decl.name, tid, fields, self._span(decl))

    def _lower_enum_decl(self, decl: EnumDecl) -> HirEnumDecl:
        variants = [variant.name if hasattr(variant, "name") else variant for variant in decl.variants]
        tid = self.interner.mk_enum(decl.name, variants)
        payloads = {variant.name: [self._get_type_id_from_node(type_) for type_ in variant.payload_types]
                    for variant in decl.variants if hasattr(variant, "payload_types")}
        return HirEnumDecl(decl.name, tid, variants, self._span(decl), payloads)

    def _lower_interface_decl(self, decl: InterfaceDecl) -> HirInterfaceDecl:
        methods: List[Tuple[str, int]] = []
        for m in decl.methods:
            params = tuple(self._get_type_id_from_node(getattr(p, "type_ann", getattr(p, "type_annotation", None))) for p in m.params)
            ret = self._get_type_id_from_node(m.return_type) if m.return_type else TYPE_UNIT
            fn_tid = self.interner.mk_function(params, ret)
            methods.append((m.name, fn_tid))
        tid = self.interner.mk_interface(decl.name, dict(methods))
        return HirInterfaceDecl(decl.name, tid, methods, self._span(decl))

    def _lower_class_decl(self, decl: ClassDecl) -> HirClassDecl:
        tid = self.interner.mk_class(decl.name)
        fields = [
            HirFieldDef(f.name, self._get_type_id_from_node(getattr(f, "type_ann", getattr(f, "type_annotation", None))), is_public=f.is_public, span=self._span(f))
            for f in decl.fields
        ]
        methods: List[HirFnDecl] = []
        init_method: Optional[HirFnDecl] = None
        for m in decl.methods:
            m_hir = self._lower_method_decl(m)
            if m.name == "init":
                init_method = m_hir
            methods.append(m_hir)

        return HirClassDecl(
            name=decl.name,
            type_id=tid,
            superclass=decl.superclass,
            interfaces=decl.interfaces,
            fields=fields,
            methods=methods,
            init_method=init_method,
            span=self._span(decl)
        )

    def _lower_fn_decl(self, decl: FnDecl) -> HirFnDecl:
        params = [
            HirParam(p.name, self._get_type_id_from_node(getattr(p, "type_ann", getattr(p, "type_annotation", None))), self._span(p))
            for p in decl.params
        ]
        ret_tid = self._get_type_id_from_node(decl.return_type) if decl.return_type else TYPE_UNIT
        body_hir = self._lower_block(decl.body)
        is_fallible = False
        err_type_name = ""
        if decl.return_type and isinstance(decl.return_type, AstResultType):
            is_fallible = True
            err_type_name = decl.return_type.err_type.name if hasattr(decl.return_type.err_type, "name") else "Error"

        return HirFnDecl(
            name=decl.name,
            params=params,
            return_type_id=ret_tid,
            body=body_hir,
            is_fallible=is_fallible,
            err_type_name=err_type_name,
            is_method=False,
            is_public=True,
            span=self._span(decl)
        )

    def _lower_method_decl(self, decl: MethodDecl) -> HirFnDecl:
        params = [
            HirParam(p.name, self._get_type_id_from_node(getattr(p, "type_ann", getattr(p, "type_annotation", None))), self._span(p))
            for p in decl.params
        ]
        ret_tid = self._get_type_id_from_node(decl.return_type) if decl.return_type else TYPE_UNIT
        body_hir = self._lower_block(decl.body)
        is_fallible = False
        err_type_name = ""
        if decl.return_type and isinstance(decl.return_type, AstResultType):
            is_fallible = True
            err_type_name = decl.return_type.err_type.name if hasattr(decl.return_type.err_type, "name") else "Error"

        return HirFnDecl(
            name=decl.name,
            params=params,
            return_type_id=ret_tid,
            body=body_hir,
            is_fallible=is_fallible,
            err_type_name=err_type_name,
            is_method=True,
            is_public=decl.is_public,
            span=self._span(decl)
        )

    # -------------------------------------------------------------
    # Blocks and Statements
    # -------------------------------------------------------------

    def _lower_block(self, block: Block) -> HirBlock:
        stmts = [self._lower_stmt(s) for s in block.statements]
        tail_hir = None
        if block.tail_expr is not None:
            if isinstance(block.tail_expr, AssignmentExpr):
                tgt_hir = self._lower_expr(block.tail_expr.target)
                val_hir = self._lower_expr(block.tail_expr.value)
                stmts.append(HirAssign(tgt_hir, val_hir, Span(block.tail_expr.line, block.tail_expr.col)))
                tail_hir = HirConstUnit(TYPE_UNIT, Span(block.tail_expr.line, block.tail_expr.col))
            else:
                tail_hir = self._lower_expr(block.tail_expr)
        return HirBlock(stmts, self._span(block), tail_expr=tail_hir)

    def _lower_stmt(self, stmt: Stmt) -> HirStmt:
        span = self._span(stmt)
        if isinstance(stmt, LetDecl):
            ann_node = getattr(stmt, "type_ann", getattr(stmt, "type_annotation", None))
            tid = self._get_type_id_from_node(ann_node) if ann_node else self._get_expr_type_id(stmt.initializer)
            init_hir = self._lower_expr(stmt.initializer)
            return HirLet(stmt.name, tid, stmt.is_mut, init_hir, span)
        elif isinstance(stmt, WhileStmt):
            cond_hir = self._lower_expr(stmt.condition)
            body_hir = self._lower_block(stmt.body)
            return HirWhile(cond_hir, body_hir, span)
        elif isinstance(stmt, ForStmt):
            list_hir = self._lower_expr(stmt.iterable)
            list_tid = list_hir.type_id
            elem_tid = TYPE_INT
            entry = self.interner.get_entry(list_tid)
            if entry.tag == "list":
                elem_tid = entry.data
            body_hir = self._lower_block(stmt.body)
            return HirForList(stmt.pattern, elem_tid, list_hir, body_hir, span)
        elif isinstance(stmt, ReturnStmt):
            if stmt.value is not None:
                val_hir = self._lower_expr(stmt.value)
            else:
                val_hir = HirConstUnit(TYPE_UNIT, span)
            return HirReturn(val_hir, span)
        elif isinstance(stmt, BreakStmt):
            return HirBreak(span)
        elif isinstance(stmt, ContinueStmt):
            return HirContinue(span)
        elif isinstance(stmt, ExprStmt):
            if isinstance(stmt.expr, AssignmentExpr):
                tgt_hir = self._lower_expr(stmt.expr.target)
                val_hir = self._lower_expr(stmt.expr.value)
                return HirAssign(tgt_hir, val_hir, span)
            return HirExprStmt(self._lower_expr(stmt.expr), span)

        # Fallback to expression statement
        raise WError(f"Unsupported AST statement: {type(stmt).__name__}",
                     line=span.line, col=span.col, file=self.file_path,
                     code="W9999", stage="hir")

    # -------------------------------------------------------------
    # Expressions
    # -------------------------------------------------------------

    def _construct_enum(self, name, variant, index, type_id, span, payload=None):
        entry = self.interner.get_entry(type_id)
        if entry.tag in ("optional", "result"):
            name = "Option" if entry.tag == "optional" else "Result"
        if entry.tag == "enum":
            definition = self.interner.enum_defs.get(entry.data)
            if definition and variant in definition.variants:
                index = definition.variants.index(variant)
        return HirConstructEnum(name, variant, index, type_id, span, payload)

    def _lower_expr(self, expr: Expr) -> HirExpr:
        value = self._lower_expr_impl(expr)
        if hasattr(expr, "force_result_wrap_id"):
            return self._construct_enum("Result", "Ok", 0, expr.force_result_wrap_id,
                                    self._span(expr), value)
        return value

    def _lower_expr_impl(self, expr: Expr) -> HirExpr:
        span = self._span(expr)
        tid = self._get_expr_type_id(expr)

        if isinstance(expr, IntLiteral):
            return HirConstInt(expr.value, tid or TYPE_INT, span)
        elif isinstance(expr, FloatLiteral):
            return HirConstFloat(expr.value, tid or TYPE_FLOAT, span)
        elif isinstance(expr, BoolLiteral):
            return HirConstBool(expr.value, tid or TYPE_BOOL, span)
        elif isinstance(expr, StringLiteral):
            return HirConstStr(expr.value, tid or TYPE_STR, span)
        elif isinstance(expr, NoneLiteral):
            return HirConstNone(tid or TYPE_NONE, span)
        elif isinstance(expr, IdentExpr):
            if expr.name in ("None", "none"):
                return HirConstNone(tid or TYPE_NONE, span)
            if expr.name in self.enum_variants:
                en_name = self.enum_variants[expr.name]
                return self._construct_enum(en_name, expr.name, 0, tid or self.interner.mk_enum(en_name), span)
            return HirLocalRef(expr.name, tid, span)
        elif isinstance(expr, ThisExpr):
            return HirThisRef(tid, span)
        elif isinstance(expr, SuperExpr):
            return HirSuperRef(tid, span)
        elif isinstance(expr, UnaryExpr):
            operand_hir = self._lower_expr(expr.operand)
            return HirUnaryOp(getattr(expr, "op", getattr(expr, "operator", "-")), operand_hir, tid, span)
        elif isinstance(expr, BinaryExpr):
            left_hir = self._lower_expr(expr.left)
            right_hir = self._lower_expr(expr.right)
            return HirBinaryOp(getattr(expr, "op", getattr(expr, "operator", "+")), left_hir, right_hir, tid, span)
        elif isinstance(expr, NewExpr):
            raw_args = getattr(expr, "arguments", getattr(expr, "args", []))
            args_hir = [self._lower_expr(a) for a in raw_args]
            return HirConstructObject(expr.class_name, args_hir, tid, span)
        elif isinstance(expr, StructInitExpr):
            s_name = getattr(expr, "struct_name", getattr(expr, "name", "Struct"))
            fields_hir = [(f.name, self._lower_expr(f.value)) for f in expr.fields]
            return HirConstructStruct(s_name, fields_hir, tid, span)
        elif isinstance(expr, ListExpr):
            elems_hir = [self._lower_expr(e) for e in expr.elements]
            entry = self.interner.get_entry(tid)
            elem_tid = entry.data if entry.tag == "list" else (elems_hir[0].type_id if elems_hir else TYPE_INT)
            return HirConstructList(elem_tid, elems_hir, tid or self.interner.mk_list(elem_tid), span)
        elif isinstance(expr, DictExpr):
            entries_hir = [
                (self._lower_expr(e.key), self._lower_expr(e.value)) if hasattr(e, "key")
                else (self._lower_expr(e[0]), self._lower_expr(e[1]))
                for e in expr.entries
            ]
            entry = self.interner.get_entry(tid)
            k_tid, v_tid = entry.data if entry.tag == "dict" else (TYPE_STR, TYPE_INT)
            return HirConstructDict(k_tid, v_tid, entries_hir, tid or self.interner.mk_dict(k_tid, v_tid), span)
        elif isinstance(expr, TupleExpr):
            elems_hir = [self._lower_expr(e) for e in expr.elements]
            elem_tids = [e.type_id for e in elems_hir]
            return HirConstructTuple(elem_tids, elems_hir, tid or self.interner.mk_tuple(tuple(elem_tids)), span)
        elif isinstance(expr, CallExpr):
            raw_args = getattr(expr, "args", getattr(expr, "arguments", []))
            # Check if this call is an unqualified Enum variant constructor
            if isinstance(expr.callee, IdentExpr):
                c_name = expr.callee.name
                if c_name == "Some" and len(raw_args) == 1:
                    arg_hir = self._lower_expr(raw_args[0])
                    return self._construct_enum("Option", "Some", 0, tid or self.interner.mk_enum("Option"), span, arg_hir)
                if c_name == "Ok" and len(raw_args) == 1:
                    arg_hir = self._lower_expr(raw_args[0])
                    return self._construct_enum("Result", "Ok", 0, tid or self.interner.mk_enum("Result"), span, arg_hir)
                if c_name == "Err" and len(raw_args) == 1:
                    arg_hir = self._lower_expr(raw_args[0])
                    return self._construct_enum("Result", "Err", 1, tid or self.interner.mk_enum("Result"), span, arg_hir)
                if c_name in self.enum_variants:
                    en_name = self.enum_variants[c_name]
                    args_hir = [self._lower_expr(a) for a in raw_args]
                    payload_hir = args_hir[0] if len(args_hir) == 1 else (HirConstructTuple([a.type_id for a in args_hir], args_hir, self.interner.mk_tuple(tuple(a.type_id for a in args_hir)), span) if len(args_hir) > 1 else None)
                    return self._construct_enum(en_name, c_name, 0, tid or self.interner.mk_enum(en_name), span, payload_hir)

            # Check if this call is a qualified Enum variant constructor: Enum.Variant(...)
            if isinstance(expr.callee, MemberExpr) and isinstance(expr.callee.object, IdentExpr) and expr.callee.object.name in self.enums:
                en_name = expr.callee.object.name
                v_name = expr.callee.property
                args_hir = [self._lower_expr(a) for a in raw_args]
                payload_hir = args_hir[0] if len(args_hir) == 1 else (HirConstructTuple([a.type_id for a in args_hir], args_hir, self.interner.mk_tuple(tuple(a.type_id for a in args_hir)), span) if len(args_hir) > 1 else None)
                return self._construct_enum(en_name, v_name, 0, tid or self.interner.mk_enum(en_name), span, payload_hir)

            # Check if this call is an object construction: ClassName(...)
            if isinstance(expr.callee, IdentExpr) and expr.callee.name in self.classes:
                args_hir = [self._lower_expr(a) for a in raw_args]
                return HirConstructObject(expr.callee.name, args_hir, tid or self.interner.mk_class(expr.callee.name), span)
            # Check if this call is a struct construction: StructName(...)
            elif isinstance(expr.callee, IdentExpr) and expr.callee.name in self.structs:
                args_hir = [self._lower_expr(a) for a in raw_args]
                sdef = self.interner.struct_defs.get(expr.callee.name)
                field_names = list(sdef.fields.keys()) if sdef else []
                fields = [(field_names[i] if i < len(field_names) else f"f{i}", args_hir[i]) for i in range(len(args_hir))]
                return HirConstructStruct(expr.callee.name, fields, tid or self.interner.mk_struct(expr.callee.name), span)
            # Check if builtin call
            elif isinstance(expr.callee, IdentExpr) and expr.callee.name in BUILTIN_NAMES:
                args_hir = [self._lower_expr(a) for a in raw_args]
                return HirBuiltinCall(expr.callee.name, args_hir, tid, span)
            # Check if method call or module function call
            elif isinstance(expr.callee, MemberExpr):
                if isinstance(expr.callee.object, IdentExpr) and expr.callee.object.name in self.modules:
                    args_hir = [self._lower_expr(a) for a in raw_args]
                    return HirDirectCall(f"{expr.callee.object.name}__{expr.callee.property}", args_hir, tid, span)
                rec_hir = self._lower_expr(expr.callee.object)
                args_hir = [self._lower_expr(a) for a in raw_args]
                return HirMethodCall(rec_hir, expr.callee.property, args_hir, tid, span)
            # Direct top-level function call
            elif isinstance(expr.callee, IdentExpr):
                args_hir = [self._lower_expr(a) for a in raw_args]
                return HirDirectCall(expr.callee.name, args_hir, tid, span)
            else:
                args_hir = [self._lower_expr(a) for a in raw_args]
                callee_name = getattr(expr.callee, "name", "anon_fn")
                return HirDirectCall(callee_name, args_hir, tid, span)
        elif isinstance(expr, MemberExpr):
            # Check if this is an Enum variant: EnumName.Variant
            if isinstance(expr.object, IdentExpr) and expr.object.name in self.enums:
                enum_name = expr.object.name
                variant_name = expr.property
                if enum_name == "Option" and variant_name in ("None", "none"):
                    return HirConstNone(tid or TYPE_NONE, span)
                edef = self.interner.enum_defs.get(enum_name)
                v_idx = edef.variants.index(variant_name) if edef and variant_name in edef.variants else 0
                return self._construct_enum(enum_name, variant_name, v_idx, tid or self.interner.mk_enum(enum_name), span)
            obj_hir = self._lower_expr(expr.object)
            return HirFieldRead(obj_hir, expr.property, tid, span)
        elif isinstance(expr, IndexExpr):
            obj_hir = self._lower_expr(expr.object)
            idx_hir = self._lower_expr(expr.index)
            return HirIndexRead(obj_hir, idx_hir, tid, span)
        elif isinstance(expr, PostfixTryExpr):
            op_hir = self._lower_expr(expr.operand)
            return HirTryPropagate(op_hir, expr.propagation_kind, tid, span)
        elif isinstance(expr, CoalesceExpr):
            opt_hir = self._lower_expr(expr.left)
            fb_hir = self._lower_expr(expr.right)
            return HirCoalesce(opt_hir, fb_hir, tid, span)
        elif isinstance(expr, ElseErrExpr):
            op_hir = self._lower_expr(expr.operand)
            h_block = getattr(expr, "handler", getattr(expr, "body", None))
            handler_hir = self._lower_block(h_block)
            err_var = getattr(expr, "err_name", getattr(expr, "err_variable", None))
            return HirElseHandle(op_hir, err_var, handler_hir, tid, span)
        elif isinstance(expr, IfExpr):
            cond_hir = self._lower_expr(expr.condition)
            then_hir = self._lower_block(expr.then_branch)
            elifs_hir = [(self._lower_expr(b.condition), self._lower_block(b.body)) for b in expr.elif_branches]
            else_hir = self._lower_block(expr.else_branch) if expr.else_branch else None
            return HirIf(cond_hir, then_hir, elifs_hir, else_hir, tid, span)
        elif isinstance(expr, MatchExpr):
            sub_hir = self._lower_expr(expr.subject)
            arms_hir = [HirMatchArm(arm.pattern, self._lower_block(arm.body), self._span(arm), self._lower_expr(arm.guard) if arm.guard is not None else None) for arm in expr.arms]
            return HirMatch(sub_hir, arms_hir, tid, span)
        elif isinstance(expr, RangeExpr):
            s_hir = self._lower_expr(expr.start)
            e_hir = self._lower_expr(expr.end)
            return HirRange(s_hir, e_hir, expr.inclusive, tid, span)

        raise WError(f"Unsupported AST expression: {type(expr).__name__}",
                     line=span.line, col=span.col, file=self.file_path,
                     code="W9999", stage="hir")

    # -------------------------------------------------------------
    # Type Resolution Helpers
    # -------------------------------------------------------------

    def _get_expr_type_id(self, expr: Expr) -> int:
        if hasattr(expr, "inferred_type_id") and expr.inferred_type_id is not None:
            return expr.inferred_type_id
        if hasattr(expr, "inferred_type") and expr.inferred_type is not None:
            return self.interner.from_wtype(expr.inferred_type)
        return TYPE_ERROR

    def _get_type_id_from_node(self, node: Optional[TypeNode]) -> int:
        if node is None:
            return TYPE_UNIT
        if hasattr(node, "resolved_type_id"):
            return node.resolved_type_id
        if isinstance(node, NamedType):
            name = node.name
            if name == "int":
                return TYPE_INT
            elif name == "float":
                return TYPE_FLOAT
            elif name == "bool":
                return TYPE_BOOL
            elif name == "str":
                return TYPE_STR
            elif name == "unit":
                return TYPE_UNIT
            elif name == "none":
                return TYPE_NONE
            elif name in self.structs:
                return self.interner.mk_struct(name)
            elif name in self.enums:
                return self.interner.mk_enum(name)
            elif name in self.classes:
                return self.interner.mk_class(name)
            return TYPE_ERROR
        elif isinstance(node, AstOptionalType):
            return self.interner.mk_optional(self._get_type_id_from_node(node.inner))
        elif isinstance(node, AstListType):
            return self.interner.mk_list(self._get_type_id_from_node(node.element_type))
        elif isinstance(node, AstDictType):
            return self.interner.mk_dict(
                self._get_type_id_from_node(node.key_type),
                self._get_type_id_from_node(node.value_type)
            )
        elif isinstance(node, AstResultType):
            return self.interner.mk_result(
                self._get_type_id_from_node(node.ok_type),
                self._get_type_id_from_node(node.err_type)
            )
        elif isinstance(node, GenericType):
            args_mangled = "__".join(self._get_type_name_from_node(a) for a in node.type_args)
            mangled_name = f"{node.name}__{args_mangled}"
            if mangled_name in self.structs:
                return self.interner.mk_struct(mangled_name)
            return TYPE_ERROR
        return TYPE_ERROR

    def _get_type_name_from_node(self, node: TypeNode) -> str:
        if isinstance(node, NamedType):
            return node.name
        if isinstance(node, GenericType):
            args = "__".join(self._get_type_name_from_node(a) for a in node.type_args)
            return f"{node.name}__{args}"
        if isinstance(node, AstOptionalType):
            return f"opt__{self._get_type_name_from_node(node.inner)}"
        if isinstance(node, AstListType):
            return f"list__{self._get_type_name_from_node(node.element_type)}"
        return "val"
