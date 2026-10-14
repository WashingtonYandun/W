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

    path = 'tests/runtime/generic_pair.w'
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

    builder = HirBuilder(checker.interner, file_path='boundary.w')
    generator = HirCCodeGen(checker.interner, file_path='boundary.w')
    for action in [lambda: builder._lower_expr(Expr()),
                   lambda: builder._lower_stmt(Stmt()),
                   lambda: generator.emit_expr(HirExpr(1, Span(3, 4)), [])]:
        try:
            action()
        except WError as error:
            assert error.code == 'W9999', str(error)
            assert error.file == 'boundary.w'
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
    print('  [PASS] Constraint validation, constructor types, lowering and HIR verification boundaries')


if __name__ == '__main__':
    test_compiler_boundaries()
