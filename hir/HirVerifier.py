"""Validate HIR structure, type decorations and control-flow invariants."""
from error.Error import WError
from checker.TypeInterner import TYPE_BOOL, TYPE_INT, TYPE_FLOAT, TYPE_STR, TYPE_UNIT, TYPE_NONE
from hir import HirNodes as H


class HirVerifier:
    def __init__(self, interner, file_path):
        self.interner = interner
        self.file_path = file_path
        self.active = set()

    def verify(self, module):
        self.active.clear()
        if not isinstance(module, H.HirModule):
            self._fail(module, 'Expected HirModule')
        self._visit(module, 0, False)

    def _fail(self, owner, message):
        span = getattr(owner, 'span', H.Span())
        raise WError(message, line=span.line, col=span.col, file=self.file_path,
                     code='W9999', stage='hir-verification')

    def _type(self, type_id, owner, field):
        if type(type_id) is not int or self.interner.get_entry(type_id).tag == 'error':
            self._fail(owner, f'Invalid HIR type in {type(owner).__name__}.{field}: {type_id!r}')

    def _relations(self, value):
        literals = {H.HirConstInt: TYPE_INT, H.HirConstFloat: TYPE_FLOAT,
                    H.HirConstBool: TYPE_BOOL, H.HirConstStr: TYPE_STR,
                    H.HirConstUnit: TYPE_UNIT, H.HirConstNone: TYPE_NONE}
        if type(value) in literals and value.type_id != literals[type(value)]:
            self._fail(value, 'Literal type does not match its value kind')
        if isinstance(value, H.HirUnaryOp):
            operand = value.operand.type_id
            valid = ((value.op == '-' and operand in (TYPE_INT, TYPE_FLOAT)) or
                     (value.op == 'not' and operand == TYPE_BOOL))
            if not valid or value.type_id != operand:
                self._fail(value, 'Invalid unary operand/result types')
        if isinstance(value, H.HirBinaryOp):
            left, right = value.left.type_id, value.right.type_id
            expected = None
            if value.op in ('+', '-', '*', '/') and left == right:
                if left in (TYPE_INT, TYPE_FLOAT) or (value.op == '+' and left == TYPE_STR):
                    expected = left
            elif value.op == '%' and left == right == TYPE_INT:
                expected = TYPE_INT
            elif value.op in ('and', 'or') and left == right == TYPE_BOOL:
                expected = TYPE_BOOL
            elif value.op in ('<', '<=', '>', '>=') and left == right and left in (TYPE_INT, TYPE_FLOAT):
                expected = TYPE_BOOL
            elif value.op in ('==', '!='):
                # Alias-aware equality compatibility remains a frontend contract.
                expected = TYPE_BOOL
            if expected is None or value.type_id != expected:
                self._fail(value, 'Invalid binary operand/result types')
        if isinstance(value, H.HirRange):
            entry = self.interner.get_entry(value.type_id)
            if value.start.type_id != TYPE_INT or value.end.type_id != TYPE_INT or entry.tag != 'list' or entry.data != TYPE_INT:
                self._fail(value, 'Range requires int bounds and list[int] result')
        if isinstance(value, H.HirConstructTuple):
            if any(element.type_id != type_id for element, type_id in zip(value.elems, value.elem_type_ids)):
                self._fail(value, 'Tuple operand types do not match element metadata')
        if isinstance(value, H.HirConstructList):
            entry = self.interner.get_entry(value.type_id)
            if entry.tag != 'list' or entry.data != value.elem_type_id:
                self._fail(value, 'List metadata does not match result type')
        if isinstance(value, H.HirConstructDict):
            entry = self.interner.get_entry(value.type_id)
            if entry.tag != 'dict' or entry.data != (value.key_type_id, value.val_type_id):
                self._fail(value, 'Dictionary metadata does not match result type')

    def _visit(self, value, loop_depth, in_function):
        if isinstance(value, (list, tuple)):
            if id(value) in self.active:
                self._fail(value, 'Cyclic HIR container')
            self.active.add(id(value))
            try:
                for child in value:
                    self._visit(child, loop_depth, in_function)
            finally:
                self.active.remove(id(value))
            return
        if not isinstance(value, (H.HirNode, H.HirModule, H.HirParam, H.HirFieldDef, H.HirMatchArm)):
            return
        if type(value).__module__ != H.__name__ or type(value) in (H.HirNode, H.HirExpr, H.HirStmt):
            self._fail(value, f'Unsupported HIR node: {type(value).__name__}')
        if id(value) in self.active:
            self._fail(value, f'Cyclic HIR node: {type(value).__name__}')

        required = []
        if isinstance(value, (H.HirExpr, H.HirParam, H.HirFieldDef, H.HirLet,
                              H.HirBindTemp, H.HirStructDecl, H.HirEnumDecl,
                              H.HirClassDecl, H.HirInterfaceDecl)):
            required.append('type_id')
        if isinstance(value, (H.HirConstructList, H.HirForList)):
            required.append('elem_type_id')
        if isinstance(value, H.HirConstructDict):
            required.extend(('key_type_id', 'val_type_id'))
        if isinstance(value, H.HirConstructTuple):
            if not isinstance(getattr(value, 'elem_type_ids', None), (list, tuple)):
                self._fail(value, 'Missing or invalid tuple element type metadata')
        if isinstance(value, H.HirFnDecl):
            required.append('return_type_id')
            loop_depth, in_function = 0, True
        for field in required:
            self._type(getattr(value, field, None), value, field)
        if isinstance(value, (H.HirBreak, H.HirContinue)) and loop_depth == 0:
            self._fail(value, 'Loop transfer outside a loop')
        if isinstance(value, H.HirReturn) and not in_function:
            self._fail(value, 'Return outside a function')
        if isinstance(value, (H.HirIf, H.HirWhile)):
            condition = value.cond if isinstance(value, H.HirIf) else value.cond_expr
            if not isinstance(condition, H.HirExpr) or getattr(condition, 'type_id', None) != TYPE_BOOL:
                self._fail(value, 'HIR condition must have bool type')
        if isinstance(value, H.HirIf):
            for condition, _ in value.elifs:
                if not isinstance(condition, H.HirExpr) or getattr(condition, 'type_id', None) != TYPE_BOOL:
                    self._fail(value, 'HIR elif condition must have bool type')
        if isinstance(value, H.HirConstructTuple):
            entry = self.interner.get_entry(value.type_id)
            if entry.tag != 'tuple' or tuple(value.elem_type_ids) != entry.data:
                self._fail(value, 'Tuple element metadata does not match its type')
            if len(value.elems) != len(value.elem_type_ids):
                self._fail(value, 'Tuple element count does not match its type')
        self.active.add(id(value))
        try:
            for field, child in vars(value).items():
                if field.endswith('type_id'):
                    self._type(child, value, field)
                elif field.endswith('type_ids'):
                    for type_id in child:
                        self._type(type_id, value, field)
                child_depth = loop_depth
                if field == 'body' and isinstance(value, (H.HirWhile, H.HirForList)):
                    child_depth += 1
                self._visit(child, child_depth, in_function)
            if isinstance(value, H.HirInterfaceDecl):
                for _, type_id in value.methods:
                    self._type(type_id, value, 'methods')
            self._relations(value)
        finally:
            self.active.remove(id(value))
