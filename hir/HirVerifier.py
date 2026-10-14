"""Validate type decorations at the HIR/backend boundary."""
from error.Error import WError
from hir import HirNodes


class HirVerifier:
    def __init__(self, interner, file_path):
        self.interner = interner
        self.file_path = file_path
        self.seen = set()

    def verify(self, module):
        self.seen.clear()
        self._visit(module)

    def _type(self, type_id, owner, field):
        if type(type_id) is not int or self.interner.get_entry(type_id).tag == 'error':
            span = getattr(owner, 'span', HirNodes.Span())
            raise WError(f'Invalid HIR type in {type(owner).__name__}.{field}: {type_id!r}',
                         line=span.line, col=span.col, file=self.file_path,
                         code='W9999', stage='hir-verification')

    def _visit(self, value):
        if isinstance(value, (list, tuple)):
            for child in value:
                self._visit(child)
            return
        if type(value).__module__ != HirNodes.__name__:
            return
        if id(value) in self.seen:
            return
        self.seen.add(id(value))
        if isinstance(value, HirNodes.HirExpr) and not hasattr(value, 'type_id'):
            self._type(None, value, 'type_id')
        for field, child in vars(value).items():
            if field.endswith('type_id'):
                self._type(child, value, field)
            elif field.endswith('type_ids'):
                for type_id in child:
                    self._type(type_id, value, field)
            self._visit(child)
        if isinstance(value, HirNodes.HirInterfaceDecl):
            for _, type_id in value.methods:
                self._type(type_id, value, 'methods')
