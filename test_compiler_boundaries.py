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
    print('  [PASS] Constraint validation, synthesized constructor types, and lowering boundaries')


if __name__ == '__main__':
    test_compiler_boundaries()
