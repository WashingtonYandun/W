from checker.TypeChecker import TypeChecker
from checker.TypeInterner import TypeInterner
from checker.WType import BoolType, EnumType, ErrorUnionType, IntType, ResultType, StrType, StructType, is_assignable
from compiler.CompilationSession import CompilationSession
from error.Error import TypeError as WTypeError
from formatter.Formatter import Formatter
from hir.HirBuilder import HirBuilder
from hir.HirDump import HirDumper
from parser.Parser import Parser


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
    fixture = root / "tests/runtime/error_union_composition.w"
    session = CompilationSession(project_root=str(root))

    session.check_source(fixture.read_text(), str(fixture))
