"""Verify terminating function tails and reject incomplete return paths."""


def run_hir_return_path_tests():
    from parser.Parser import Parser
    from checker.TypeChecker import TypeChecker
    from hir.HirBuilder import HirBuilder
    from hir.HirCCodeGen import HirCCodeGen
    from error.Error import WysnaError
    sources = [
        'fn choose(b: bool) -> int { if b { return 1 } else { return 2 } }',
        'enum E { A, B }\nfn choose(e: E) -> int { match e { E.A => { return 1 }, E.B => { return 2 } } }',
    ]
    for source in sources:
        ast = Parser().parse(source)
        checker = TypeChecker()
        checker.check(ast)
        module = HirBuilder(checker.interner).lower(ast)
        HirCCodeGen(checker.interner).generate(module)
        tail = module.functions[0].body.tail_expr
        if hasattr(tail, 'else_block'):
            tail.else_block = None
        else:
            tail.arms.pop()
        try:
            HirCCodeGen(checker.interner).generate(module)
        except WysnaError as error:
            assert error.code == 'W9999'
        else:
            raise AssertionError('Non-terminating malformed HIR tail was accepted')
    print('HIR terminating and incomplete return-path contracts passed')


if __name__ == '__main__':
    run_hir_return_path_tests()
