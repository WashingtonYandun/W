"""Validate HIR structure, type decorations and control-flow invariants."""
from error.Error import WError
from node.NodeType import (Pattern, IdentifierPattern, WildcardPattern, TuplePattern, EnumPattern, LiteralPattern, IntLiteral, FloatLiteral, BoolLiteral, StringLiteral, NoneLiteral)
from checker.TypeInterner import TYPE_BOOL, TYPE_INT, TYPE_FLOAT, TYPE_STR, TYPE_UNIT, TYPE_NONE
from hir import HirNodes as H


class HirVerifier:
    def __init__(self, interner, file_path):
        self.interner = interner
        self.file_path = file_path
        self.active = set()
        self.checked_types = set()

    def verify(self, module):
        self.active.clear()
        self.checked_types.clear()
        if not isinstance(module, H.HirModule):
            self._fail(module, 'Expected HirModule')
        self._visit(module, 0, False)
        from hir.HirBindings import HirBindings
        HirBindings(self).check(module)

    def _fail(self, owner, message):
        span = getattr(owner, 'span', H.Span(getattr(owner, 'line', 1), getattr(owner, 'col', 1)))
        raise WError(message, line=span.line, col=span.col, file=self.file_path,
                     code='W9999', stage='hir-verification')

    def _type(self, type_id, owner, field):
        if type(type_id) is not int or self.interner.get_entry(type_id).tag == 'error':
            self._fail(owner, f'Invalid HIR type in {type(owner).__name__}.{field}: {type_id!r}')
        if type_id in self.checked_types:
            return
        self.checked_types.add(type_id)
        entry = self.interner.get_entry(type_id)
        children = []
        if entry.tag in ("optional", "list"):
            children = [entry.data]
        elif entry.tag in ("dict", "result", "tuple"):
            children = list(entry.data)
        elif entry.tag == "function":
            children = list(entry.data[0]) + [entry.data[1]]
        elif entry.tag == "struct":
            definition = self.interner.struct_defs.get(entry.data)
            children = list(definition.fields.values()) if definition else []
        elif entry.tag == "interface":
            definition = self.interner.interface_defs.get(entry.data)
            children = list(definition.methods.values()) if definition else []
        elif entry.tag == "class":
            definition = self.interner.class_defs.get(entry.data)
            if definition:
                children = [type_ for type_, _ in definition.fields.values()]
                children.extend(type_ for type_, _ in definition.methods.values())
                children.extend(definition.interfaces)
                if definition.superclass is not None:
                    children.append(definition.superclass)
                if definition.init_sig is not None:
                    children.append(definition.init_sig)
        for child in children:
            self._type(child, owner, field + ".component")

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
        if isinstance(value, H.HirTryPropagate):
            entry = self.interner.get_entry(value.operand.type_id)
            if value.kind != entry.tag or entry.tag not in ("optional", "result"):
                self._fail(value, "Propagation kind does not match outer type")
            expected = entry.data if entry.tag == "optional" else entry.data[0]
            if value.type_id != expected:
                self._fail(value, "Propagation result does not match outer payload")
        if isinstance(value, H.HirCoalesce):
            entry = self.interner.get_entry(value.opt_expr.type_id)
            expected = entry.data if entry.tag == "optional" else value.fallback_expr.type_id
            if (entry.tag != "optional" and value.opt_expr.type_id != TYPE_NONE) or value.type_id != expected:
                self._fail(value, "Coalesce type does not match optional payload")
        if isinstance(value, H.HirElseHandle):
            entry = self.interner.get_entry(value.operand.type_id)
            if entry.tag not in ("optional", "result"):
                self._fail(value, "Error handler requires optional or result operand")
            expected = entry.data if entry.tag == "optional" else entry.data[0]
            if value.type_id != expected:
                self._fail(value, "Error handler result does not match payload")
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
        if isinstance(value, Pattern):
            if type(value) not in (IdentifierPattern, WildcardPattern, TuplePattern, EnumPattern, LiteralPattern):
                self._fail(value, "Unsupported HIR pattern")
            if isinstance(value, LiteralPattern):
                if not isinstance(value.literal, (IntLiteral, FloatLiteral, BoolLiteral, StringLiteral, NoneLiteral)):
                    self._fail(value, "Unsupported HIR pattern literal")
                self._type(getattr(value.literal, "inferred_type_id", None), value, "literal type")
            self._type(getattr(value, "inferred_type_id", None), value, "pattern type")
            if id(value) in self.active:
                self._fail(value, "Cyclic HIR pattern")
            self.active.add(id(value))
            try:
                for field in ("args", "elements"):
                    self._visit(getattr(value, field, []), loop_depth, in_function)
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
        if isinstance(value, H.HirMatchArm) and value.guard is not None:
            if value.guard.type_id != TYPE_BOOL:
                self._fail(value, "Match guard must have bool type")
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
