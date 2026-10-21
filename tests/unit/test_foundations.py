"""Executable public contracts and bounded standard-resource lifetime gates."""
import os
from pathlib import Path
import re
import tempfile

from main import ensure_selfhost_w1_binary
from tests.engine_harness import verify, run_engine

ROOT = Path(__file__).resolve().parents[2]


def test_readme_examples_execute_in_all_engines():
    text = (ROOT / 'README.md').read_text(encoding='utf-8')
    blocks = re.findall(r'```w\n(.*?)```', text, re.S)
    assert len(blocks) == 5
    w1 = ensure_selfhost_w1_binary(str(ROOT))
    with tempfile.TemporaryDirectory(prefix='w-doc-contract-') as temporary:
        for index, source in enumerate(blocks):
            ok, detail = verify(source, f'readme_{index}.w', w1, temporary, strict=True,
                                sanitize=os.environ.get('W_SANITIZE') == '1')
            assert ok, detail


def test_standard_resources_are_bounded_in_a_persistent_process():
    source = '''import "std/buffer"
import "std/files"
extern "C" fn w_host_active_handles() -> int
extern "C" fn w_host_active_bytes() -> int
extern "C" fn w_host_buffer_size(handle: opaque) -> int
fn request() -> unit ! files.FileError {
    let data = buffer.from_text("request")
    let alias = data
    let copied = buffer.clone(alias) else error { exit(21) return }
    let file = files.open("README.md", 0)?
    let chunk = file.read(32)?
    if chunk.size() != 32 { exit(22) }
    let missing = files.open("w-missing-resource-contract/file", 0) else error {
        if error.code <= 0 or error.domain <= 0 { exit(23) }
        return
    }
}
fn closed_alias() {
    let first = buffer.from_text("alias")
    let second = first
    let borrowed = first.borrow()
    first.close()
    if second.size() != -1 { exit(24) }
    if second.close() != 0 { exit(25) }
}
fn escaped() -> buffer.Bytes { return buffer.from_text("retained") }
fn borrowed() -> opaque {
    let value = escaped()
    return value.borrow()
}
fn containers_and_closures() {
    let values = [escaped()]
    let callback = || -> int { values[0].size() }
    if callback() != 8 { exit(28) }
}
let baseline = w_host_active_handles()
containers_and_closures()
if w_host_buffer_size(borrowed()) != -1 { exit(29) }
for count in [10000, 100000] {
    for index in 0..count {
        request() else error { exit(26) }
        if w_host_active_handles() != baseline or w_host_active_bytes() != 0 { exit(27) }
    }
    print(count, w_host_active_handles() - baseline, w_host_active_bytes())
}
closed_alias()
print(w_host_active_handles() - baseline)
'''
    w1 = ensure_selfhost_w1_binary(str(ROOT))
    with tempfile.TemporaryDirectory(prefix='w-persistent-resource-') as temporary:
        ok, detail = verify(source, 'persistent_resources.w', w1, temporary, strict=True,
                            expected='10000 0 0\n100000 0 0\n0\n', run_timeout=300,
                            sanitize=os.environ.get('W_SANITIZE') == '1')
        assert ok, detail


def test_fallible_unit_tail_parity():
    source = ROOT / 'tests/runtime/fallible_unit_tails.w'
    w1 = ensure_selfhost_w1_binary(str(ROOT))
    with tempfile.TemporaryDirectory(prefix='w-unit-result-') as temporary:
        ok, detail = verify(source.read_text(), str(source), w1, temporary, strict=True,
                            expected=source.with_suffix('.expected').read_text(),
                            sanitize=os.environ.get('W_SANITIZE') == '1')
        assert ok, detail


def test_unit_tail_rejects_incompatible_error_channels():
    sources = ['fn failure() -> int ! int { Err(7) }\nfn action() -> unit ! str { failure() }',
               'fn action() -> unit ! str { Err(42) }',
               'fn action() -> unit ! str { let problem = Err(42)\nproblem }',
               'fn failure() -> int ! int { Err(7) }\nfn action() -> unit ! str { if true { failure() } else { 42 } }']
    w1 = ensure_selfhost_w1_binary(str(ROOT))
    with tempfile.TemporaryDirectory(prefix='w-unit-error-channel-') as temporary:
        for index, source in enumerate(sources):
            for engine in ('interpreter', 'ast', 'hir', 'w1'):
                result = run_engine(engine, source, 'unit_error_channel.w', w1, Path(temporary) / str(index) / engine)
                assert result.exit_code == 1 and result.diag_code == 'W2004', vars(result)
                assert not result.infrastructure_error, vars(result)


def test_flush_failure_is_recoverable():
    if not Path('/dev/full').exists():
        return
    source = '''import "std/buffer"
import "std/files"
fn write_failure() -> unit ! files.FileError {
    let file = files.open("/dev/full", 1)?
    let bytes = buffer.from_text("write must fail")
    file.write(bytes)?
}
write_failure() else error { print(error.operation == "write", error.code > 0, error.domain > 0) }
'''
    w1 = ensure_selfhost_w1_binary(str(ROOT))
    with tempfile.TemporaryDirectory(prefix='w-flush-failure-') as temporary:
        ok, detail = verify(source, 'flush_failure.w', w1, temporary, strict=True,
                            expected='true true true\n', sanitize=os.environ.get('W_SANITIZE') == '1')
        assert ok, detail


def run_foundations_tests():
    test_fallible_unit_tail_parity()
    test_unit_tail_rejects_incompatible_error_channels()
    test_flush_failure_is_recoverable()
    test_readme_examples_execute_in_all_engines()
    test_standard_resources_are_bounded_in_a_persistent_process()
    return True


if __name__ == '__main__':
    run_foundations_tests()
