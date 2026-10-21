from checker.TypeChecker import TypeChecker
from checker.TypeInterner import TypeInterner
from checker.WType import BoolType, EnumType, ErrorUnionType, IntType, ResultType, StrType, StructType, is_assignable
from compiler.CompilationSession import CompilationSession
from error.Error import TypeError as WTypeError
from formatter.Formatter import Formatter
from hir.HirBuilder import HirBuilder
from hir.HirDump import HirDumper
from parser.Parser import Parser


def _nodes(value, node_type, seen=None):
    if seen is None:
        seen = set()
    if isinstance(value, (list, tuple)):
        for child in value:
            yield from _nodes(child, node_type, seen)
    elif type(value).__module__ in ('node.NodeType', 'hir.HirNodes'):
        if id(value) in seen:
            return
        seen.add(id(value))
        if isinstance(value, node_type):
            yield value
        for child in vars(value).values():
            yield from _nodes(child, node_type, seen)


def _checked_pattern_module():
    source = '''struct FirstError { message: str }
enum SecondError { Missing }
fn fail() -> int ! FirstError | SecondError { return Err(SecondError.Missing) }
fn recover() -> int { return fail() else err { match err {
    FirstError(error) if error.message == "first" => 1,
    FirstError(_) => 2,
    SecondError(_) => 3
} } }
fn variant(error: SecondError) -> int { return match error { SecondError.Missing => 4 } }
'''
    ast = Parser().parse(source)
    checker = TypeChecker()
    checker.check(ast)
    return ast, checker, HirBuilder(checker.interner).lower(ast)


def test_checked_error_patterns_are_distinct_from_enum_variants():
    from node.NodeType import EnumPattern, ErrorTypePattern
    from hir.HirNodes import HirEnumPattern, HirErrorTypePattern

    ast, checker, module = _checked_pattern_module()
    errors = list(_nodes(ast, ErrorTypePattern))
    assert [pattern.type_name for pattern in errors] == ['FirstError', 'FirstError', 'SecondError']
    assert all(pattern.to_dict()['kind'] == 'ErrorTypePattern' for pattern in errors)
    assert list(_nodes(ast, EnumPattern))[0].variant == 'Missing'
    lowered = list(_nodes(module, HirErrorTypePattern))
    assert len(lowered) == 3
    assert all(pattern.binding.type_id == pattern.error_type_id for pattern in lowered)
    assert all(not hasattr(pattern, 'variant_id') for pattern in lowered)
    assert list(_nodes(module, HirEnumPattern))[0].variant_name == 'Missing'
    dump = HirDumper().format_pattern(lowered[0])
    assert 'error_type(FirstError, type_id=' in dump
    assert '__W_ERROR_TYPE__' not in dump
    assert [Formatter().format_pattern(pattern) for pattern in errors] == [
        'FirstError(error)', 'FirstError(_)', 'SecondError(_)'
    ]


def test_hir_rejects_invalid_error_type_patterns_before_emission():
    from copy import deepcopy
    from error.Error import WError
    from hir.HirCCodeGen import HirCCodeGen
    from hir.HirNodes import HirErrorTypePattern, HirWildcardPattern, HirEnumPattern, HirMatch
    from hir.HirVerifier import HirVerifier
    from checker.TypeInterner import TYPE_INT

    _, checker, module = _checked_pattern_module()
    for defect in ('foreign_alternative', 'wrong_subject', 'wrong_binding_type', 'missing_binding',
                   'enum_substitution', 'different_union_subject'):
        broken = deepcopy(module)
        pattern = next(_nodes(broken, HirErrorTypePattern))
        if defect == 'foreign_alternative':
            pattern.error_type_id = TYPE_INT
        elif defect == 'wrong_subject':
            pattern.type_id = TYPE_INT
        elif defect == 'wrong_binding_type':
            pattern.binding = HirWildcardPattern(TYPE_INT, pattern.span)
        elif defect == 'missing_binding':
            pattern.binding = None
        elif defect == 'different_union_subject':
            pattern.type_id = checker.interner.mk_error_union((pattern.error_type_id, TYPE_INT))
        else:
            match = next(node for node in _nodes(broken, HirMatch)
                         if node.arms[0].pattern is pattern)
            match.arms[0].pattern = HirEnumPattern('FirstError', 'FirstError', 0, [pattern.binding],
                                                   pattern.type_id, pattern.span)
        for check in (lambda: HirVerifier(checker.interner, '<test>').verify(broken),
                      lambda: HirCCodeGen(checker.interner, file_path='<test>').generate(broken)):
            try:
                check()
            except WError as error:
                assert error.code == 'W9999'
                assert error.stage == 'hir-verification'
            else:
                raise AssertionError(f'Invalid error pattern reached C emission: {defect}')


def test_guarded_error_type_pattern_does_not_prove_exhaustiveness():
    source = '''struct FirstError { message: str }
enum SecondError { Missing }
fn fail() -> int ! FirstError | SecondError { return Err(SecondError.Missing) }
fn recover() -> int { return fail() else err { match err {
    FirstError(error) if error.message == "first" => 1,
    SecondError(_) => 2
} } }
'''
    try:
        TypeChecker().check(Parser().parse(source))
    except WTypeError as error:
        assert error.code == 'W2003'
    else:
        raise AssertionError('A guarded error alternative incorrectly closed the match')


def test_terminating_hir_error_match_uses_the_module_type_arena():
    from hir.HirBindings import HirBindings
    from hir.HirNodes import HirMatch, HirErrorTypePattern, HirReturn, HirConstInt
    from hir.HirVerifier import HirVerifier
    from checker.TypeInterner import TYPE_INT

    _, checker, module = _checked_pattern_module()
    match = next(node for node in _nodes(module, HirMatch)
                 if isinstance(node.arms[0].pattern, HirErrorTypePattern))
    match.arms = [arm for arm in match.arms if arm.guard is None]
    for arm in match.arms:
        arm.body.statements = [HirReturn(HirConstInt(1, TYPE_INT, arm.span), arm.span)]
        arm.body.tail_expr = None
    bindings = HirBindings(HirVerifier(checker.interner, '<test>'))
    assert bindings.always_returns(match)
    match.arms.pop()
    assert not bindings.always_returns(match)


def test_module_error_patterns_preserve_distinct_nominal_identities():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from node.NodeType import ErrorTypePattern

    with TemporaryDirectory(prefix='w-error-identities-') as temporary:
        directory = Path(temporary)
        for name in ('left', 'right'):
            (directory / f'{name}.wysna').write_text('''pub struct SharedError { message: str }
pub fn fail() -> int ! SharedError { return Err(SharedError { message: "error" }) }
''')
        source = '''import "left.wysna"
import "right.wysna"
fn fail() -> int ! left.SharedError | right.SharedError {
    return left.fail()
}
fn recover() -> int { return fail() else err { match err {
    left.SharedError(error) => 1,
    right.SharedError(error) => 2
} } }
'''
        unit = CompilationSession(project_root=temporary).check_source(source, str(directory / 'main.wysna'))
        patterns = list(_nodes(unit.program, ErrorTypePattern))
        assert patterns[0].type_name == 'left.SharedError'
        assert patterns[1].type_name == 'right.SharedError'
        assert patterns[0].matched_type != patterns[1].matched_type


def test_error_union_type_identity_and_subset_assignability():
    interner = TypeInterner()
    first = interner.mk_struct("FirstError", {})
    second = interner.mk_struct("SecondError", {})

    wide = interner.mk_error_union((first, second))
    assert wide == interner.mk_error_union((second, first, first))
    assert interner.get_capabilities(wide).needs_retain
    assert interner.get_capabilities(wide).needs_release
    assert interner.is_assignable(first, wide)
    assert interner.is_assignable(wide, wide)
    assert not interner.is_assignable(wide, first)

    first_type = StructType("FirstError", {})
    second_type = StructType("SecondError", {})
    wide_type = ErrorUnionType([first_type, second_type])
    assert is_assignable(first_type, wide_type)
    assert is_assignable(wide_type, wide_type)
    assert not is_assignable(wide_type, first_type)
    assert not is_assignable(IntType, wide_type)

    narrow_result = ResultType(IntType, first_type)
    wide_result = ResultType(IntType, wide_type)
    assert is_assignable(narrow_result, wide_result)
    assert not is_assignable(wide_result, narrow_result)

    narrow_result_id = interner.mk_result(interner.intern(IntType), first)
    wide_result_id = interner.mk_result(interner.intern(IntType), wide)
    assert interner.is_assignable(narrow_result_id, wide_result_id)
    assert not interner.is_assignable(wide_result_id, narrow_result_id)

    scalar_error_result_id = interner.mk_result(interner.intern(IntType), interner.intern(StrType))
    nested_error_id = interner.mk_result(interner.intern(StrType), interner.intern(BoolType))
    nested_result_id = interner.mk_result(interner.intern(IntType), nested_error_id)
    assert not interner.is_assignable(scalar_error_result_id, nested_result_id)
    assert not is_assignable(ResultType(IntType, StrType), ResultType(IntType, ResultType(StrType, BoolType)))

    result_value = EnumType("Result[int, str]", ["Ok", "Err"])
    result_value.template_name = "Result"
    result_value.type_args = [IntType, StrType]
    assert is_assignable(result_value, ResultType(result_value, BoolType))


def test_error_union_type_formatting_round_trip():
    parser = Parser()
    formatter = Formatter()
    source = """struct AlphaError { message: str }
struct ZetaError { message: str }
fn combine() -> int ! ZetaError | AlphaError { return Err(1) }
"""

    rendered = formatter.format(parser.parse(source))
    assert "int ! ZetaError | AlphaError" in rendered
    assert formatter.format(parser.parse(rendered)) == rendered


def test_hir_dump_preserves_error_union_alternatives():
    source = """struct FirstError { message: str }
struct SecondError { message: str }
fn run() -> int ! SecondError | FirstError { return 1 }
"""
    parser = Parser()
    ast = parser.parse(source)
    checker = TypeChecker()
    checker.check(ast)
    hir_module = HirBuilder(checker.interner).lower(ast)
    dump = HirDumper().dump_module(hir_module)

    assert "! SecondError | FirstError" in dump


def test_error_union_widens_propagation_and_rejects_missing_alternatives():
    valid = """struct FirstError { message: str }
struct SecondError { message: str }
struct ThirdError { message: str }
fn first() -> int ! FirstError { return Err(FirstError { message: "first" }) }
fn wider() -> int ! FirstError | SecondError { return first()? }
fn widest() -> int ! FirstError | SecondError | ThirdError { return wider()? }
"""
    TypeChecker().check(Parser().parse(valid))

    invalid = """struct FirstError { message: str }
struct SecondError { message: str }
fn first() -> int ! FirstError { return Err(FirstError { message: "first" }) }
fn narrower() -> int ! SecondError { return first()? }
"""
    try:
        TypeChecker().check(Parser().parse(invalid))
    except WTypeError as error:
        assert error.code == "W2006"
    else:
        raise AssertionError("A source error outside the target error set was accepted")


def test_narrow_result_can_be_returned_as_a_wider_error_result():
    source = """struct FirstError { message: str }
struct SecondError { message: str }
fn narrow() -> int ! FirstError { return Err(FirstError { message: "first" }) }
fn wider() -> int ! FirstError | SecondError { return narrow() }
"""
    TypeChecker().check(Parser().parse(source))


def test_error_payload_is_not_implicitly_lifted_into_a_nested_result_channel():
    source = """fn narrow() -> int ! str { return 1 }
fn nested() -> int ! (str ! bool) { return narrow() }
"""
    try:
        TypeChecker().check(Parser().parse(source))
    except WTypeError as error:
        assert error.code == "W2004"
    else:
        raise AssertionError("A scalar error was implicitly lifted into a nested Result error channel")


def test_error_union_payload_type_is_resolved_through_result_specialization():
    source = """struct FirstError { message: str }
struct SecondError { message: str }
fn fail() -> int ! FirstError | SecondError { return Err(FirstError { message: "first" }) }
fn recover() -> int { return fail() else err { match err {
    FirstError(first) => 1,
    SecondError(second) => 2
} } }
"""
    TypeChecker().check(Parser().parse(source))


def test_error_union_accepts_module_qualified_alternatives_and_patterns():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    fixture = root / "tests/runtime/error_union_composition.wysna"
    session = CompilationSession(project_root=str(root))

    unit = session.check_source(fixture.read_text(), str(fixture))
    from node.NodeType import ErrorTypePattern
    patterns = list(_nodes(unit.program, ErrorTypePattern))
    assert [pattern.type_name for pattern in patterns] == ['errors.ParseError', 'errors.FileError', 'int']
    library = root / 'tests/modules/error_union/errors.wysna'
    library_patterns = list(_nodes(session.modules[str(library)].program, ErrorTypePattern))
    assert [pattern.type_name for pattern in library_patterns] == ['ParseError', 'FileError']
    assert all(pattern.source_file == str(library) for pattern in library_patterns)


def run_error_union_tests():
    tests = [test for name, test in sorted(globals().items()) if name.startswith('test_') and callable(test)]
    for test in tests:
        test()
    print(f'F03 type and pattern contracts: {len(tests)} passed')


if __name__ == '__main__':
    run_error_union_tests()
