"""Validate HIR structure, type decorations and control-flow invariants."""
from error.Error import WError
from checker.TypeInterner import TYPE_BOOL
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
        finally:
            self.active.remove(id(value))
