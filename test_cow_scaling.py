"""Independent N/M scaling, multiple aliases and repeated writes for B02."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from parser.Parser import Parser
from checker.TypeChecker import TypeChecker
from error.Error import WError
from runtime.Interpreter import Interpreter
from runtime.Values import cow_telemetry
from codegen.CCodeGen import CCodeGen
from hir.HirBuilder import HirBuilder
from hir.HirCCodeGen import HirCCodeGen
from main import ensure_selfhost_w1_binary
from test_cow_telemetry import parse_checkpoints


LOGICAL_KEYS = ('detach_list', 'detach_dict', 'detach_struct', 'copied_slots')


def logical_metrics(checkpoints):
    return {label: {key: values[key] for key in LOGICAL_KEYS}
            for label, values in checkpoints.items()}


def matrix_program():
    functions, calls, expected, dimensions = [], [], [], []
    for rows, columns in [(2, 3), (2, 17), (7, 3), (7, 17)]:
        name = f'matrix_{rows}_{columns}'
        dimensions.append((name, rows, columns))
        row_literals = ['[' + ', '.join(['0'] * columns) + ']' for _ in range(rows)]
        lines = [f'fn {name}() -> unit {{',
                 'let mut matrix = [' + ', '.join(row_literals) + ']',
                 'let snap0 = matrix', 'let snap1 = matrix']
        phases = [('baseline', ''), ('first', 'matrix[0][0] = 1'),
                  ('second', 'matrix[0][1] = 2'), ('third', 'matrix[1][0] = 3'),
                  ('fourth', 'matrix[1][1] = 4'), ('renew', 'let middle = matrix'),
                  ('fifth', 'matrix[0][0] = 5'), ('sixth', 'matrix[0][1] = 6')]
        for phase, statement in phases:
            if statement:
                lines.append(statement)
            lines.append(f'eprint("__COW_CHECKPOINT__:{name}/{phase}")')
        lines += [f'print({rows}, {columns}, matrix[0][0], matrix[0][1], '
                  'matrix[1][0], matrix[1][1], snap0[0][0], snap1[0][0], middle[0][0])', '}']
        functions.append('\n'.join(lines))
        calls.append(name + '()')
        expected.append(f'{rows} {columns} 5 6 3 4 0 0 1\n')
    return '\n'.join(functions + calls), ''.join(expected), dimensions


def validate_scaling(checkpoints, dimensions):
    phases = ['baseline', 'first', 'second', 'third', 'fourth', 'renew', 'fifth', 'sixth']
    assert set(checkpoints) == {f'{name}/{phase}' for name, _, _ in dimensions for phase in phases}
    for name, rows, columns in dimensions:
        previous = checkpoints[f'{name}/baseline']
        for phase, detaches, slots in [('first', 2, rows + columns), ('second', 0, 0),
                                      ('third', 1, columns), ('fourth', 0, 0),
                                      ('renew', 0, 0), ('fifth', 2, rows + columns),
                                      ('sixth', 0, 0)]:
            current = checkpoints[f'{name}/{phase}']
            assert current['detach_list'] - previous['detach_list'] == detaches, (name, phase)
            assert current['copied_slots'] - previous['copied_slots'] == slots, (name, phase)
            assert current['detach_dict'] == previous['detach_dict']
            assert current['detach_struct'] == previous['detach_struct']
            if 'allocs' in current:
                assert current['allocs'] - previous['allocs'] == 2 * detaches, (name, phase)
                for field in ['copied_bytes', 'allocated_bytes']:
                    delta = current[field] - previous[field]
                    assert delta > 0 if detaches else delta == 0, (name, phase, field)
            previous = current


def run_scaling_tests():
    root = Path(__file__).resolve().parent
    source, expected, dimensions = matrix_program()
    ast = Parser().parse(source)
    checker = TypeChecker()
    checker.check(ast)
    for invalid in ['let value = [1]\nvalue[0] = 2',
                    'let mut pair = (1, 2)\npair[0] = 3']:
        try:
            TypeChecker().check(Parser().parse(invalid))
        except WError:
            pass
        else:
            raise AssertionError('Immutable/tuple mutation was accepted')
    output, errors = io.StringIO(), io.StringIO()
    cow_telemetry.reset()
    previous = os.environ.get('W_COW_METRICS')
    os.environ['W_COW_METRICS'] = '1'
    try:
        with contextlib.redirect_stderr(errors):
            Interpreter(stdout=output).interpret(ast)
    finally:
        if previous is None:
            os.environ.pop('W_COW_METRICS', None)
        else:
            os.environ['W_COW_METRICS'] = previous
    assert output.getvalue() == expected
    reference = parse_checkpoints(errors.getvalue())
    validate_scaling(reference, dimensions)
    hir = HirBuilder(checker.interner).lower(ast)
    with tempfile.TemporaryDirectory(prefix='w-cow-scaling-') as directory:
        w_path = Path(directory) / 'scaling.w'
        w_path.write_text(source)
        native_reference = None
        for backend in ['ast', 'hir', 'w1']:
            c_path, binary = Path(directory) / (backend + '.c'), Path(directory) / backend
            if backend == 'w1':
                w1 = ensure_selfhost_w1_binary(str(root))
                subprocess.run([w1, str(w_path), str(c_path)], cwd=root,
                               check=True, capture_output=True, text=True, timeout=60)
            else:
                code = (CCodeGen().generate(ast) if backend == 'ast'
                        else HirCCodeGen(checker.interner).generate(hir))
                c_path.write_text(code)
            subprocess.run([os.environ.get('CC', 'cc'), '-std=c99', '-fsanitize=address,undefined',
                            '-fno-omit-frame-pointer', '-I' + str(root), str(c_path), '-o', str(binary)],
                           check=True, capture_output=True, text=True, timeout=60)
            env = dict(os.environ, W_MEM_CHECK='1', W_COW_METRICS='1')
            env['ASAN_OPTIONS'] = 'detect_leaks=1' if sys.platform.startswith('linux') else 'detect_leaks=0'
            result = subprocess.run([str(binary)], env=env, capture_output=True, text=True, timeout=30)
            assert result.returncode == 0, (backend, result.stderr)
            assert result.stdout == expected, (backend, result.stdout)
            metrics = parse_checkpoints(result.stderr)
            validate_scaling(metrics, dimensions)
            assert logical_metrics(metrics) == reference, backend
            if native_reference is None:
                native_reference = metrics
            assert metrics == native_reference, backend
    print('  [PASS] B02 independent N/M matrix sizes, three aliases and repeated writes on four engines')


if __name__ == '__main__':
    run_scaling_tests()
