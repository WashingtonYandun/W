"""Regression contracts for CI failures, coverage and bounded processes."""
import json
import os
from pathlib import Path
import sys
import tempfile
from tests import engine_harness as harness


def run_ci_harness_tests():
    reference = harness.EngineResult('interpreter', stdout='expected\n')
    assert harness.compare([reference, harness.EngineResult('hir', stdout='different\n')])[0] is False
    assert harness.compare([reference, harness.EngineResult('ast', stdout='expected\n', exit_code=1)], 'expected\n')[0] is False
    assert harness.compare([reference, harness.EngineResult('w1', stdout='expected\n', infrastructure_error='sanitizer failure')])[0] is False
    assert not harness.unsupported_reason('new_generic_named_core_fixture.w', 'w1')
    assert harness.unsupported_reason('tests/runtime/generic_function.w', 'w1')
    assert not harness.unsupported_reason('tests/runtime/generic_function.w', 'hir')
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        timed = harness.execute([sys.executable, '-c', 'while True: pass'], directory, 'timeout', 0.1)
        assert timed['returncode'] == 124 and timed['timeout'] == 0.1
        signaled = harness.execute([sys.executable, '-c', 'import os, signal; os.kill(os.getpid(), signal.SIGTERM)'], directory, 'signal', 10)
        assert signaled['returncode'] == -15
        assert json.loads((directory / 'signal.json').read_text())['command']
        original = harness.run_engine
        previous = os.environ.get('W_CI_ARTIFACTS')
        os.environ['W_CI_ARTIFACTS'] = str(directory / 'artifacts')
        try:
            harness.run_engine = lambda engine, *args: harness.EngineResult(engine, stdout='ok\n')
            assert harness.verify('', 'tests/runtime/generic_function.w', '', directory, 'ok\n')[0]
            assert not harness.verify('', 'tests/runtime/generic_function.w', '', directory, 'ok\n', strict=True)[0]
            assert not harness.verify('', 'invalid.w', '', directory, expect_rejection=True)[0]
        finally:
            harness.run_engine = original
            if previous is None:
                os.environ.pop('W_CI_ARTIFACTS')
            else:
                os.environ['W_CI_ARTIFACTS'] = previous
    with tempfile.TemporaryDirectory() as temporary:
        original_execute = harness.execute
        commands = []
        def simulate(command, directory, phase, timeout, env=None):
            commands.append(command)
            return {'returncode': 0, 'stdout': '',
                    'stderr': 'ERROR: AddressSanitizer: heap-use-after-free' if phase == 'run' else ''}
        try:
            harness.execute = simulate
            result = harness.run_engine('w1', '', 'probe.w', '/standalone-w1', temporary, True)
            assert commands[0][0] == '/standalone-w1'
            assert result.infrastructure_error == 'memory or sanitizer failure'
            assert not harness.compare([result], '')[0]
        finally:
            harness.execute = original_execute
    print('CI harness: output, exit status, sanitizer failure, timeout, signal, direct rejection and release coverage contracts passed')


if __name__ == '__main__':
    run_ci_harness_tests()
