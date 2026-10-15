"""Definite initialization and escape checks for class constructors."""
from node import NodeType as A
from error.Error import TypeError


def check_constructor(declaration, class_type, method, file):
    required = {field.name for field in declaration.fields}

    def fail(node, message):
        raise TypeError(message, file=file, line=node.line, col=node.col, code='W3004')

    def is_self(node):
        return isinstance(node, A.ThisExpr) or isinstance(node, A.IdentExpr) and node.name == 'self'

    def super_call(node):
        return (isinstance(node, A.CallExpr) and isinstance(node.callee, A.MemberExpr)
                and isinstance(node.callee.object, A.SuperExpr) and node.callee.property == 'init')

    statements = list(method.body.statements)
    if method.body.tail_expr is not None:
        statements.append(A.ExprStmt(method.body.tail_expr))
    parent = class_type.superclass
    needs_super = False
    while parent is not None:
        needs_super = needs_super or parent.init_type is not None
        parent = parent.superclass
    first = statements[0].expr if statements and isinstance(statements[0], A.ExprStmt) else None
    if needs_super and not super_call(first):
        fail(method, "super.init must be the first statement in a derived constructor")
    calls = []

    def collect(node):
        if super_call(node):
            calls.append(node)
        if isinstance(node, A.Node):
            for child in vars(node).values():
                if isinstance(child, A.Node):
                    collect(child)
                elif isinstance(child, list):
                    for item in child:
                        if isinstance(item, A.Node):
                            collect(item)
    collect(method.body)
    if len(calls) > 1 or calls and not super_call(first):
        fail(method, "super.init must occur exactly once, as the first statement")

    def complete(node, initialized):
        missing = required - initialized
        if missing:
            fail(node, 'Constructor leaves uninitialized fields: ' + ', '.join(sorted(missing)))

    def expression(node, initialized):
        if node is None or initialized is None:
            return initialized
        if isinstance(node, A.AssignmentExpr):
            target = node.target
            if isinstance(target, A.MemberExpr) and is_self(target.object):
                initialized = expression(node.value, initialized)
                if initialized is not None:
                    initialized = initialized | {target.property}
                return initialized
        if isinstance(node, A.MemberExpr) and is_self(node.object):
            if node.property in required and node.property not in initialized:
                fail(node, "Read before initialization: this." + node.property)
            if node.property in class_type.methods:
                fail(node, "Virtual method calls are forbidden during construction")
            return initialized
        if is_self(node):
            fail(node, "The receiver cannot escape during construction")
        if super_call(node):
            for argument in node.args:
                initialized = expression(argument, initialized)
            return initialized
        if isinstance(node, A.IfExpr):
            expression(node.condition, initialized)
            branches = [block(node.then_branch, set(initialized))]
            for alternative in node.elif_branches:
                expression(alternative.condition, initialized)
                branches.append(block(alternative.body, set(initialized)))
            branches.append(block(node.else_branch, set(initialized)) if node.else_branch else set(initialized))
            live = [branch for branch in branches if branch is not None]
            return set.intersection(*live) if live else None
        if isinstance(node, A.MatchExpr):
            expression(node.subject, initialized)
            branches = []
            for arm in node.arms:
                expression(arm.guard, initialized)
                branches.append(block(arm.body, set(initialized)))
            live = [branch for branch in branches if branch is not None]
            return set.intersection(*live) if live else None
        if isinstance(node, A.Node):
            for child in vars(node).values():
                if isinstance(child, A.Node):
                    initialized = expression(child, initialized)
                elif isinstance(child, list):
                    for item in child:
                        if isinstance(item, A.Node):
                            initialized = expression(item, initialized)
        return initialized

    def block(node, initialized):
        if node is None:
            return initialized
        for statement in node.statements:
            if initialized is None:
                break
            if isinstance(statement, A.ReturnStmt):
                expression(statement.value, initialized)
                complete(statement, initialized)
                initialized = None
            elif isinstance(statement, (A.ForStmt, A.WhileStmt)):
                expression(getattr(statement, 'condition', getattr(statement, 'iterable', None)), initialized)
                block(statement.body, set(initialized))
            else:
                initialized = expression(getattr(statement, 'expr', getattr(statement, 'initializer', None)), initialized)
        return expression(node.tail_expr, initialized)

    final = block(method.body, set())
    if final is not None:
        complete(method, final)
