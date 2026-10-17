"""Audit closure gates: allocation oracles, typed composition and safe formatting."""
from collections import Counter
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from main import ensure_selfhost_w1_binary
from tests.engine_harness import verify
from tests.formatter_contract import formatter_paths, structural_ast, verify_formatting
from tests.fuzz.typed_properties import generate_typed_properties

ROOT = Path(__file__).resolve().parents[2]
SEEDS = (0, 1, 2, 3, 5, 8, 13, 21)


def test_ascii_allocation_and_lifetime_contract():
    source = r'''#include "runtime/w_runtime.h"
#include <assert.h>
int main(void) {
    assert(W_RUNTIME_ABI_VERSION == 2 && sizeof(WVal) <= 32);
    for (int64_t code = 0; code < 128; code++) {
        WVal character = w_builtin_chr(w_int(code));
        assert(character.tag == W_STR && character.as.string.length == 1);
        assert(w_builtin_ord(character).as.i == code);
        WVal retained = w_clone(character);
        w_release(character);
        assert(w_builtin_ord(retained).as.i == code);
        w_release(retained);
    }
    assert(w_g_alloc_count == 0);
    WVal owner = w_copy_str("abc");
    WVal character = w_index_get_owned(owner, w_int(1));
    w_release(owner);
    assert(w_builtin_ord(character).as.i == 'b');
    w_release(character);
    assert(w_g_alloc_count == 1 && w_g_free_count == 1);
    WVal unicode = w_builtin_chr(w_int(128578));
    WVal copied = w_index_get_owned(unicode, w_int(0));
    w_release(unicode);
    assert(w_builtin_ord(copied).as.i == 128578);
    w_release(copied);
    assert(w_g_alloc_count == w_g_free_count && w_g_live_objects == 0);
    w_runtime_cleanup();
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix='w-ascii-contract-') as temporary:
        path = Path(temporary) / 'contract.c'
        binary = Path(temporary) / 'contract'
        path.write_text(source)
        subprocess.run([os.environ.get('CC', 'cc'), '-std=c99', '-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer', '-I' + str(ROOT), str(path), '-o', str(binary)],
                       check=True, capture_output=True, text=True, timeout=60)
        environment = dict(os.environ, W_MEM_CHECK='1', UBSAN_OPTIONS='halt_on_error=1')
        environment['ASAN_OPTIONS'] = 'detect_leaks=' + ('1' if sys.platform.startswith('linux') else '0')
        result = subprocess.run([str(binary)], env=environment, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0 and result.stdout == '' and result.stderr == '', result


def test_formatter_preserves_guards_and_production_sources():
    paths = formatter_paths()
    required = ['selfhost/w1.w', 'selfhost/src/07_parser_decl.w',
                'examples/ffi/sqlite/import_csv.w', 'stdlib/text.w']
    assert all(ROOT / name in paths for name in required)
    for path in paths:
        verify_formatting(path.read_text(), str(path))
    from parser.Parser import Parser
    first = Parser().parse('fn guarded(x: int) -> int { match x { 1 if false => 9, _ => 0 } }')
    dropped = Parser().parse('fn guarded(x: int) -> int { match x { 1 => 9, _ => 0 } }')
    assert structural_ast(first) != structural_ast(dropped), 'oracle must detect a deleted match guard'


def test_typed_generator_shape_and_independent_model():
    kinds = Counter()
    sources = set()
    def visit(expression):
        kinds[expression.kind] += 1
        for child in expression.args:
            visit(child)
    for seed in range(64):
        source, expected, expressions = generate_typed_properties(seed)
        assert (source, expected, expressions) == generate_typed_properties(seed)
        assert len(source) < 50000 and expected
        sources.add(source)
        for expression in expressions:
            visit(expression)
    assert len(sources) == 64
    assert {'literal', 'variable', 'binary', 'observe', 'if', 'match', 'bind',
            'recover', 'list', 'index', 'not'} <= set(kinds)


def test_typed_composition_across_engines():
    w1 = ensure_selfhost_w1_binary(str(ROOT))
    with tempfile.TemporaryDirectory(prefix='w-typed-composition-') as temporary:
        for seed in SEEDS:
            source, expected, _ = generate_typed_properties(seed)
            formatted = verify_formatting(source, 'typed_properties_' + str(seed) + '.w')
            for variant, code in [('source', source), ('formatted', formatted)]:
                ok, detail = verify(code, f'typed_properties_{seed}_{variant}.w', w1, temporary,
                                    expected=expected, strict=True,
                                    sanitize=os.environ.get('W_SANITIZE') == '1')
                assert ok, f'seed {seed}, {variant}: {detail}\n{code}'


def run_completion_tests():
    test_ascii_allocation_and_lifetime_contract()
    test_formatter_preserves_guards_and_production_sources()
    test_typed_generator_shape_and_independent_model()
    test_typed_composition_across_engines()
    print('Audit completion: ASCII lifetime/allocation, formatter AST preservation and typed composition passed')
    return True


if __name__ == '__main__':
    run_completion_tests()
