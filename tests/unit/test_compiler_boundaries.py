"""Regression coverage for semantic and lowering error boundaries."""
from checker.TypeChecker import TypeChecker
from error.Error import WError
from hir.HirBuilder import HirBuilder
from hir.HirCCodeGen import HirCCodeGen
from hir.HirNodes import HirExpr, HirNode, Span
from node.NodeType import Expr, Stmt
from parser.Parser import Parser


def test_compiler_boundaries():
    for declaration in [
        'fn unused[T: Missing](x: T) -> T { return x }',
        'struct Box[T: int] { value: T }',
        'enum Choice[T: list[int]] { Item(T) }',
    ]:
        try:
            TypeChecker().check(Parser().parse(declaration))
        except WError as error:
            assert error.code == 'W2012', str(error)
        else:
            raise AssertionError('Invalid unused constraints must be rejected')

    valid = 'fn unused[T: Printable](x: T) -> T { return x }\ninterface Printable { fn show() -> str }'
    TypeChecker().check(Parser().parse(valid))

    path = 'tests/runtime/generic_pair.wysna'
    with open(path, encoding='utf-8') as stream:
        ast = Parser(file=path).parse(stream.read())
    checker = TypeChecker(file=path)
    checker.check(ast)
    module = HirBuilder(checker.interner, file_path=path).lower(ast)

    def visit(value):
        if isinstance(value, HirExpr):
            assert value.type_id != 0, type(value).__name__
        if isinstance(value, (HirNode, type(module))):
            for child in vars(value).values():
                visit(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child)
    visit(module)

    builder = HirBuilder(checker.interner, file_path='boundary.wysna')
    generator = HirCCodeGen(checker.interner, file_path='boundary.wysna')
    for action in [lambda: builder._lower_expr(Expr()),
                   lambda: builder._lower_stmt(Stmt()),
                   lambda: generator.emit_expr(HirExpr(1, Span(3, 4)), [])]:
        try:
            action()
        except WError as error:
            assert error.code == 'W9999', str(error)
            assert error.file == 'boundary.wysna'
            assert error.to_dict()['stage'] in ('hir', 'codegen')
        else:
            raise AssertionError('Unsupported nodes must not silently become unit')
    from copy import deepcopy
    from hir.HirVerifier import HirVerifier
    for invalid in [0, -1, 100000, None, True]:
        broken = deepcopy(module)
        broken.functions[0].params[0].type_id = invalid
        for action in [lambda: HirVerifier(checker.interner, path).verify(broken),
                       lambda: HirCCodeGen(checker.interner, file_path=path).generate(broken)]:
            try:
                action()
            except WError as error:
                assert error.code == 'W9999'
                assert error.stage == 'hir-verification'
                assert 'HirParam.type_id' in error.message
            else:
                raise AssertionError('Invalid parameter types must block emission')
    broken = deepcopy(module)
    broken.functions[0].return_type_id = 0
    try:
        HirVerifier(checker.interner, path).verify(broken)
    except WError as error:
        assert 'return_type_id' in error.message
    else:
        raise AssertionError('Invalid function return types must be rejected')
    from hir import HirNodes as H
    from checker.TypeInterner import TYPE_BOOL, TYPE_INT

    def rejected(unit, message):
        try:
            HirCCodeGen(checker.interner, file_path=path).generate(unit)
        except WError as error:
            assert error.code == 'W9999'
            assert message in error.message, str(error)
        else:
            raise AssertionError('Malformed HIR must block C emission')

    for field, owner in [('type_id', 'parameter'), ('return_type_id', 'function')]:
        broken = deepcopy(module)
        target = broken.functions[0].params[0] if owner == 'parameter' else broken.functions[0]
        delattr(target, field)
        rejected(broken, field)

    broken = deepcopy(module)
    broken.functions.append(broken.functions)
    rejected(broken, 'Cyclic HIR container')
    broken = deepcopy(module)
    broken.functions[0].body.statements.append(broken.functions[0].body)
    rejected(broken, 'Cyclic HIR node')

    for transfer in [H.HirBreak, H.HirContinue]:
        broken = deepcopy(module)
        broken.functions[0].body.statements.append(transfer(Span(5, 2)))
        rejected(broken, 'outside a loop')
    broken = deepcopy(module)
    broken.top_level_stmts.append(H.HirReturn(H.HirConstInt(1, TYPE_INT, Span()), Span()))
    rejected(broken, 'outside a function')
    broken = deepcopy(module)
    broken.top_level_stmts.append(H.HirWhile(H.HirConstInt(1, TYPE_INT, Span()), H.HirBlock([], Span()), Span()))
    rejected(broken, 'bool type')

    tuple_id = checker.interner.mk_tuple((TYPE_INT,))
    for metadata, elements in [([TYPE_BOOL], [H.HirConstInt(1, TYPE_INT, Span())]), ([TYPE_INT], [])]:
        broken = deepcopy(module)
        bad_tuple = H.HirConstructTuple(metadata, elements, tuple_id, Span())
        broken.top_level_stmts.append(H.HirExprStmt(bad_tuple, Span()))
        rejected(broken, 'Tuple element')

    valid = deepcopy(module)
    loop = H.HirWhile(H.HirConstBool(True, TYPE_BOOL, Span()),
                     H.HirBlock([H.HirBreak(Span())], Span()), Span())
    valid.top_level_stmts.append(loop)
    HirVerifier(checker.interner, path).verify(valid)
    shared = deepcopy(module)
    shared.functions.append(shared.functions[0])
    HirVerifier(checker.interner, path).verify(shared)

    try:
        generator.emit_stmt(H.HirStmt(Span(7, 8)), [])
    except WError as error:
        assert error.code == 'W9999' and error.stage == 'codegen'
        assert error.line == 7 and error.col == 8
    else:
        raise AssertionError('Unknown statements must not be silently ignored')
    broken = deepcopy(module)
    broken.top_level_stmts.append(H.HirExprStmt(H.HirLocalRef("missing", TYPE_INT, Span()), Span()))
    rejected(broken, 'Unresolved HIR local')
    broken = deepcopy(module)
    broken.top_level_stmts.append(H.HirExprStmt(H.HirDirectCall("missing", [], TYPE_INT, Span()), Span()))
    rejected(broken, 'Unresolved HIR function')
    broken = deepcopy(module)
    broken.top_level_stmts.append(H.HirExprStmt(H.HirDirectCall(broken.functions[0].name, [], TYPE_INT, Span()), Span()))
    rejected(broken, 'Direct call arity/result')
    broken = deepcopy(module)
    broken.functions[0].body.statements.append(H.HirReturn(H.HirConstBool(True, TYPE_BOOL, Span()), Span()))
    rejected(broken, 'Returned value type')
    broken = deepcopy(module)
    bad_signature = checker.interner.mk_function((0,), TYPE_INT)
    broken.functions[0].params[0].type_id = bad_signature
    rejected(broken, '.component')

    broken = deepcopy(module)
    broken.top_level_stmts.append(H.HirExprStmt(H.HirBuiltinCall("missing", [], TYPE_INT, Span()), Span()))
    rejected(broken, 'Unresolved HIR builtin')
    broken = deepcopy(module)
    broken.top_level_stmts.append(H.HirExprStmt(H.HirConstructObject("Missing", [], TYPE_INT, Span()), Span()))
    rejected(broken, 'Unresolved HIR class constructor')
    broken = deepcopy(module)
    declaration = broken.structs[0]
    broken.top_level_stmts.append(H.HirExprStmt(H.HirConstructStruct(declaration.name, [], declaration.type_id, Span()), Span()))
    rejected(broken, 'Struct constructor fields')
    broken = deepcopy(module)
    bad_optional = H.HirConstructEnum("Option", "Some", 0, checker.interner.mk_optional(TYPE_INT), Span(), H.HirConstBool(True, TYPE_BOOL, Span()))
    broken.top_level_stmts.append(H.HirExprStmt(bad_optional, Span()))
    rejected(broken, 'Builtin constructor payload')

    from checker.TypeInterner import TYPE_STR
    integer = H.HirConstInt(1, TYPE_INT, Span())
    boolean = H.HirConstBool(True, TYPE_BOOL, Span())
    for expression, message in [
        (H.HirConstInt(1, TYPE_BOOL, Span()), 'Literal type'),
        (H.HirUnaryOp('-', boolean, TYPE_BOOL, Span()), 'unary'),
        (H.HirBinaryOp('+', integer, boolean, TYPE_INT, Span()), 'binary'),
        (H.HirBinaryOp('+', integer, integer, TYPE_BOOL, Span()), 'binary'),
        (H.HirBinaryOp('==', integer, integer, TYPE_INT, Span()), 'binary'),
        (H.HirRange(boolean, integer, False, checker.interner.mk_list(TYPE_INT), Span()), 'Range'),
        (H.HirConstructTuple([TYPE_INT], [boolean], tuple_id, Span()), 'Tuple operand'),
        (H.HirConstructList(TYPE_STR, [], checker.interner.mk_list(TYPE_INT), Span()), 'List metadata'),
        (H.HirConstructDict(TYPE_INT, TYPE_INT, [], checker.interner.mk_dict(TYPE_STR, TYPE_INT), Span()), 'Dictionary metadata'),
    ]:
        broken = deepcopy(module)
        broken.top_level_stmts.append(H.HirExprStmt(expression, Span()))
        rejected(broken, message)
    source = 'let xs: list[str] = []\nlet data: dict[int, str] = {1: "value"}'
    checked_ast = Parser().parse(source)
    typed_checker = TypeChecker()
    typed_checker.check(checked_ast)
    HirBuilder(typed_checker.interner).lower(checked_ast)
    print('  [PASS] Structural, control-flow, operand/result and collection metadata invariants')


if __name__ == '__main__':
    test_compiler_boundaries()
