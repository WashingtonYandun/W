from typing import Any, Dict, List, Optional, Tuple, Union


class Span:
    def __init__(self, line: int = 1, col: int = 1):
        self.line = line
        self.col = col

    def __repr__(self) -> str:
        return f"Span({self.line}:{self.col})"


# ==========================================
# HIR Base Nodes
# ==========================================

class HirNode:
    def __init__(self, span: Span):
        self.span = span


class HirExpr(HirNode):
    def __init__(self, type_id: int, span: Span):
        super().__init__(span)
        self.type_id = type_id


class HirStmt(HirNode):
    pass


# ==========================================
# HIR Top-Level Declarations
# ==========================================

class HirParam:
    def __init__(self, name: str, type_id: int, span: Span):
        self.name = name
        self.type_id = type_id
        self.span = span


class HirBlock(HirNode):
    def __init__(self, statements: List[HirStmt], span: Span, tail_expr: Optional[HirExpr] = None):
        super().__init__(span)
        self.statements = statements
        self.tail_expr = tail_expr


class HirFnDecl(HirNode):
    def __init__(
        self,
        name: str,
        params: List[HirParam],
        return_type_id: int,
        body: HirBlock,
        is_fallible: bool = False,
        err_type_name: str = "",
        is_method: bool = False,
        is_public: bool = True,
        span: Span = Span()
    ):
        super().__init__(span)
        self.name = name
        self.params = params
        self.return_type_id = return_type_id
        self.body = body
        self.is_fallible = is_fallible
        self.err_type_name = err_type_name
        self.is_method = is_method
        self.is_public = is_public


class HirFieldDef:
    def __init__(self, name: str, type_id: int, is_public: bool = True, span: Span = Span()):
        self.name = name
        self.type_id = type_id
        self.is_public = is_public
        self.span = span


class HirStructDecl(HirNode):
    def __init__(self, name: str, type_id: int, fields: List[HirFieldDef], span: Span):
        super().__init__(span)
        self.name = name
        self.type_id = type_id
        self.fields = fields


class HirEnumDecl(HirNode):
    def __init__(self, name: str, type_id: int, variants: List[str], span: Span):
        super().__init__(span)
        self.name = name
        self.type_id = type_id
        self.variants = variants


class HirInterfaceDecl(HirNode):
    def __init__(self, name: str, type_id: int, methods: List[Tuple[str, int]], span: Span):
        super().__init__(span)
        self.name = name
        self.type_id = type_id
        self.methods = methods  # [(name, function_type_id)]


class HirClassDecl(HirNode):
    def __init__(
        self,
        name: str,
        type_id: int,
        superclass: Optional[str],
        interfaces: List[str],
        fields: List[HirFieldDef],
        methods: List[HirFnDecl],
        init_method: Optional[HirFnDecl],
        span: Span
    ):
        super().__init__(span)
        self.name = name
        self.type_id = type_id
        self.superclass = superclass
        self.interfaces = interfaces
        self.fields = fields
        self.methods = methods
        self.init_method = init_method


class HirModule:
    def __init__(
        self,
        file_path: str,
        structs: List[HirStructDecl],
        enums: List[HirEnumDecl],
        interfaces: List[HirInterfaceDecl],
        classes: List[HirClassDecl],
        functions: List[HirFnDecl],
        top_level_stmts: List[HirStmt]
    ):
        self.file_path = file_path
        self.structs = structs
        self.enums = enums
        self.interfaces = interfaces
        self.classes = classes
        self.functions = functions
        self.top_level_stmts = top_level_stmts


# ==========================================
# HIR Statements
# ==========================================

class HirLet(HirStmt):
    def __init__(self, name: str, type_id: int, is_mut: bool, init_expr: HirExpr, span: Span):
        super().__init__(span)
        self.name = name
        self.type_id = type_id
        self.is_mut = is_mut
        self.init_expr = init_expr


class HirBindTemp(HirStmt):
    def __init__(self, temp_name: str, type_id: int, init_expr: HirExpr, span: Span):
        super().__init__(span)
        self.temp_name = temp_name
        self.type_id = type_id
        self.init_expr = init_expr


class HirAssign(HirStmt):
    def __init__(self, target: HirExpr, value: HirExpr, span: Span):
        super().__init__(span)
        self.target = target
        self.value = value


class HirWhile(HirStmt):
    def __init__(self, cond_expr: HirExpr, body: HirBlock, span: Span):
        super().__init__(span)
        self.cond_expr = cond_expr
        self.body = body


class HirForList(HirStmt):
    def __init__(self, pattern: Any, elem_type_id: int, list_expr: HirExpr, body: HirBlock, span: Span):
        super().__init__(span)
        self.pattern = pattern
        self.elem_name = getattr(pattern, "name", str(pattern))
        self.elem_type_id = elem_type_id
        self.list_expr = list_expr
        self.body = body


class HirReturn(HirStmt):
    def __init__(self, value_expr: HirExpr, span: Span):
        super().__init__(span)
        self.value_expr = value_expr


class HirBreak(HirStmt):
    def __init__(self, span: Span):
        super().__init__(span)


class HirContinue(HirStmt):
    def __init__(self, span: Span):
        super().__init__(span)


class HirExprStmt(HirStmt):
    def __init__(self, expr: HirExpr, span: Span):
        super().__init__(span)
        self.expr = expr


# ==========================================
# HIR Expressions (18 Canonical Variants)
# ==========================================

class HirConstInt(HirExpr):
    def __init__(self, value: int, type_id: int, span: Span):
        super().__init__(type_id, span)
        self.value = value


class HirConstFloat(HirExpr):
    def __init__(self, value: float, type_id: int, span: Span):
        super().__init__(type_id, span)
        self.value = value


class HirConstBool(HirExpr):
    def __init__(self, value: bool, type_id: int, span: Span):
        super().__init__(type_id, span)
        self.value = value


class HirConstStr(HirExpr):
    def __init__(self, value: str, type_id: int, span: Span):
        super().__init__(type_id, span)
        self.value = value


class HirConstNone(HirExpr):
    def __init__(self, type_id: int, span: Span):
        super().__init__(type_id, span)


class HirConstUnit(HirExpr):
    def __init__(self, type_id: int, span: Span):
        super().__init__(type_id, span)


class HirLocalRef(HirExpr):
    def __init__(self, name: str, type_id: int, span: Span):
        super().__init__(type_id, span)
        self.name = name


class HirThisRef(HirExpr):
    def __init__(self, type_id: int, span: Span):
        super().__init__(type_id, span)


class HirSuperRef(HirExpr):
    def __init__(self, type_id: int, span: Span):
        super().__init__(type_id, span)


class HirUnaryOp(HirExpr):
    def __init__(self, op: str, operand: HirExpr, type_id: int, span: Span):
        super().__init__(type_id, span)
        self.op = op
        self.operand = operand


class HirBinaryOp(HirExpr):
    def __init__(self, op: str, left: HirExpr, right: HirExpr, type_id: int, span: Span):
        super().__init__(type_id, span)
        self.op = op
        self.left = left
        self.right = right


class HirConstructStruct(HirExpr):
    def __init__(self, struct_name: str, fields: List[Tuple[str, HirExpr]], type_id: int, span: Span):
        super().__init__(type_id, span)
        self.struct_name = struct_name
        self.fields = fields


class HirConstructEnum(HirExpr):
    def __init__(self, enum_name: str, variant_name: str, variant_idx: int, type_id: int, span: Span, payload: Optional[HirExpr] = None):
        super().__init__(type_id, span)
        self.enum_name = enum_name
        self.variant_name = variant_name
        self.variant_idx = variant_idx
        self.payload = payload


class HirConstructObject(HirExpr):
    def __init__(self, class_name: str, args: List[HirExpr], type_id: int, span: Span):
        super().__init__(type_id, span)
        self.class_name = class_name
        self.args = args


class HirConstructList(HirExpr):
    def __init__(self, elem_type_id: int, elems: List[HirExpr], type_id: int, span: Span):
        super().__init__(type_id, span)
        self.elem_type_id = elem_type_id
        self.elems = elems


class HirConstructDict(HirExpr):
    def __init__(self, key_type_id: int, val_type_id: int, entries: List[Tuple[HirExpr, HirExpr]], type_id: int, span: Span):
        super().__init__(type_id, span)
        self.key_type_id = key_type_id
        self.val_type_id = val_type_id
        self.entries = entries


class HirConstructTuple(HirExpr):
    def __init__(self, elem_type_ids: List[int], elems: List[HirExpr], type_id: int, span: Span):
        super().__init__(type_id, span)
        self.elem_type_ids = elem_type_ids
        self.elems = elems


class HirDirectCall(HirExpr):
    def __init__(self, fn_name: str, args: List[HirExpr], type_id: int, span: Span):
        super().__init__(type_id, span)
        self.fn_name = fn_name
        self.args = args


class HirBuiltinCall(HirExpr):
    def __init__(self, builtin_name: str, args: List[HirExpr], type_id: int, span: Span):
        super().__init__(type_id, span)
        self.builtin_name = builtin_name
        self.args = args


class HirMethodCall(HirExpr):
    def __init__(self, receiver: HirExpr, method_name: str, args: List[HirExpr], type_id: int, span: Span):
        super().__init__(type_id, span)
        self.receiver = receiver
        self.method_name = method_name
        self.args = args


class HirFieldRead(HirExpr):
    def __init__(self, object: HirExpr, field_name: str, type_id: int, span: Span):
        super().__init__(type_id, span)
        self.object = object
        self.field_name = field_name


class HirIndexRead(HirExpr):
    def __init__(self, object: HirExpr, index: HirExpr, type_id: int, span: Span):
        super().__init__(type_id, span)
        self.object = object
        self.index = index


class HirTryPropagate(HirExpr):
    def __init__(self, operand: HirExpr, kind: str, type_id: int, span: Span):
        super().__init__(type_id, span)
        self.operand = operand
        self.kind = kind  # "optional" or "result"


class HirCoalesce(HirExpr):
    def __init__(self, opt_expr: HirExpr, fallback_expr: HirExpr, type_id: int, span: Span):
        super().__init__(type_id, span)
        self.opt_expr = opt_expr
        self.fallback_expr = fallback_expr


class HirElseHandle(HirExpr):
    def __init__(self, operand: HirExpr, err_var: Optional[str], handler: HirBlock, type_id: int, span: Span):
        super().__init__(type_id, span)
        self.operand = operand
        self.err_var = err_var
        self.handler = handler


class HirRange(HirExpr):
    def __init__(self, start: HirExpr, end: HirExpr, inclusive: bool, type_id: int, span: Span):
        super().__init__(type_id, span)
        self.start = start
        self.end = end
        self.inclusive = inclusive


class HirIf(HirExpr):
    def __init__(
        self,
        cond: HirExpr,
        then_block: HirBlock,
        elifs: List[Tuple[HirExpr, HirBlock]],
        else_block: Optional[HirBlock],
        type_id: int,
        span: Span
    ):
        super().__init__(type_id, span)
        self.cond = cond
        self.then_block = then_block
        self.elifs = elifs
        self.else_block = else_block


class HirMatchArm:
    def __init__(self, pattern: Any, body: HirBlock, span: Span):
        self.pattern = pattern
        self.body = body
        self.span = span


class HirMatch(HirExpr):
    def __init__(self, subject: HirExpr, arms: List[HirMatchArm], type_id: int, span: Span):
        super().__init__(type_id, span)
        self.subject = subject
        self.arms = arms
