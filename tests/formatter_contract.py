"""Shared formatter corpus and structural preservation contract."""
from pathlib import Path

from formatter.Formatter import Formatter
from parser.Parser import Parser


ROOT = Path(__file__).resolve().parents[1]


def formatter_paths():
    patterns = ('tests/formatter/*.w', 'tests/runtime/*.w', 'examples/**/*.w',
                'selfhost/**/*.w', 'stdlib/**/*.w')
    return sorted({path for pattern in patterns for path in ROOT.glob(pattern)})


def structural_ast(value):
    if hasattr(value, 'to_dict'):
        return structural_ast(value.to_dict())
    if isinstance(value, dict):
        return {key: structural_ast(item) for key, item in value.items() if key not in ('line', 'col')}
    if isinstance(value, (list, tuple)):
        return [structural_ast(item) for item in value]
    if isinstance(value, float):
        return ('float', value.hex())
    return value


def verify_formatting(source, file='<stdin>'):
    original = Parser(file=file).parse(source)
    formatted = Formatter().format(original)
    reparsed = Parser(file=file).parse(formatted)
    assert structural_ast(original) == structural_ast(reparsed), 'formatter changed the program AST'
    assert formatted == Formatter().format(reparsed), 'formatter is not idempotent'
    return formatted
