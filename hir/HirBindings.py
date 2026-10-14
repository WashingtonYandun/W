"""Verify lexical names and direct-call/return contracts in the current HIR."""
from hir import HirNodes as H
from node.NodeType import IdentifierPattern, TuplePattern, EnumPattern
from checker.TypeInterner import TYPE_UNIT


class HirBindings:
    def __init__(self, verifier):
        self.verifier = verifier
        self.interner = verifier.interner
        self.functions = {}
        self.return_type = None

    def compatible(self, source, target):
        from checker.WType import is_assignable
        return self.interner.is_assignable(source, target) or is_assignable(
            self.interner.to_wtype(source), self.interner.to_wtype(target))

    def check(self, module):
        self.functions = {function.name: function for function in module.functions}
        globals_ = {node.name: node.type_id for node in module.top_level_stmts if isinstance(node, H.HirLet)}
        for node in module.top_level_stmts:
            self.visit(node, globals_)
        for function in module.functions:
            self.function(function, globals_)
        for class_ in module.classes:
            for function in class_.methods:
                self.function(function, globals_)

    def function(self, function, globals_):
        previous = self.return_type
        self.return_type = function.return_type_id
        scope = dict(globals_)
        scope.update((parameter.name, parameter.type_id) for parameter in function.params)
        try:
            self.visit(function.body, scope)
            if function.body.tail_expr is not None and not self.compatible(function.body.tail_expr.type_id, function.return_type_id):
                self.verifier._fail(function, 'Function tail type does not match return type')
        finally:
            self.return_type = previous

    def bind(self, pattern, scope, type_id=None):
        type_id = getattr(pattern, "inferred_type_id", type_id)
        if isinstance(pattern, IdentifierPattern) and pattern.name not in ('None', 'none'):
            scope[pattern.name] = type_id
        elif isinstance(pattern, TuplePattern):
            entry = self.interner.get_entry(type_id) if type_id is not None else None
            types = entry.data if entry and entry.tag == 'tuple' else [None] * len(pattern.elements)
            for subpattern, subtype in zip(pattern.elements, types):
                self.bind(subpattern, scope, subtype)
        elif isinstance(pattern, EnumPattern):
            for subpattern in getattr(pattern, 'args', getattr(pattern, 'payload', [])):
                self.bind(subpattern, scope)

    def visit(self, node, scope):
        if isinstance(node, H.HirBlock):
            scope = dict(scope)
            for statement in node.statements:
                self.visit(statement, scope)
            self.visit(node.tail_expr, scope)
            return
        if isinstance(node, (H.HirLet, H.HirBindTemp)):
            self.visit(node.init_expr, scope)
            if not self.compatible(node.init_expr.type_id, node.type_id):
                self.verifier._fail(node, 'Initializer type does not match binding type')
            scope[getattr(node, 'name', getattr(node, 'temp_name', ''))] = node.type_id
            return
        if isinstance(node, H.HirLocalRef):
            if node.name not in scope:
                self.verifier._fail(node, f'Unresolved HIR local: {node.name}')
            if scope[node.name] is not None and scope[node.name] != node.type_id:
                self.verifier._fail(node, f'HIR local type does not match binding: {node.name}')
        if isinstance(node, H.HirReturn) and self.return_type is not None:
            if not self.compatible(node.value_expr.type_id, self.return_type):
                self.verifier._fail(node, 'Returned value type does not match function return type')
        if isinstance(node, H.HirTryPropagate) and self.return_type is not None:
            returned = self.interner.get_entry(self.return_type)
            operand = self.interner.get_entry(node.operand.type_id)
            if returned.tag != operand.tag or (operand.tag == "result" and returned.data[1] != operand.data[1]):
                self.verifier._fail(node, "Propagation channel does not match function return type")
        if isinstance(node, H.HirDirectCall):
            function = self.functions.get(node.fn_name)
            if function is None:
                self.verifier._fail(node, f'Unresolved HIR function: {node.fn_name}')
            if len(node.args) != len(function.params) or node.type_id != function.return_type_id:
                self.verifier._fail(node, 'Direct call arity/result does not match declaration')
            for argument, parameter in zip(node.args, function.params):
                if not self.compatible(argument.type_id, parameter.type_id):
                    self.verifier._fail(node, 'Direct call argument type does not match declaration')
        if isinstance(node, H.HirForList):
            self.visit(node.list_expr, scope)
            inner = dict(scope)
            self.bind(node.pattern, inner, node.elem_type_id)
            self.visit(node.body, inner)
            return
        if isinstance(node, H.HirMatch):
            self.visit(node.subject, scope)
            for arm in node.arms:
                inner = dict(scope)
                self.bind(arm.pattern, inner)
                self.visit(arm.guard, inner)
                self.visit(arm.body, inner)
            return
        if isinstance(node, H.HirElseHandle):
            self.visit(node.operand, scope)
            inner = dict(scope)
            if node.err_var:
                entry = self.interner.get_entry(node.operand.type_id)
                inner[node.err_var] = entry.data[1] if entry.tag == 'result' else None
            self.visit(node.handler, inner)
            return
        if isinstance(node, H.HirAssign) and not self.compatible(node.value.type_id, node.target.type_id):
            self.verifier._fail(node, 'Assigned value type does not match target type')
        if isinstance(node, H.HirNode):
            for child in vars(node).values():
                self.visit(child, scope)
        elif isinstance(node, (list, tuple)):
            for child in node:
                self.visit(child, scope)
