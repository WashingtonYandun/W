"""Public standard toolkit, bounded binary resources and cross-engine semantics."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from main import ensure_selfhost_compiler_binary
from common.Platform import compiler_command, executable_name
from tests.engine_harness import run_engine, compare
from runtime import HostAbi

ROOT = Path(__file__).resolve().parents[2]


def test_toolkit_semantics_across_four_engines():
    selfhost_bin = ensure_selfhost_compiler_binary(str(ROOT))
    source = (ROOT / 'tests/stdlib/toolkit.wysna').read_text(encoding='utf-8')
    expected = (ROOT / 'tests/stdlib/toolkit.expected').read_text(encoding='utf-8')
    with tempfile.TemporaryDirectory() as directory:
        results = [run_engine(engine, source, 'toolkit', selfhost_bin, directory,
                   sanitize=os.environ.get('WYSNA_SANITIZE') == '1') for engine in ('interpreter', 'ast', 'hir', 'selfhost')]
        ok, detail = compare(results, expected)
        assert ok, detail


def test_streaming_files_and_filesystem_across_four_engines():
    selfhost_bin = ensure_selfhost_compiler_binary(str(ROOT))
    with tempfile.TemporaryDirectory(prefix='w toolkit é ') as temporary:
        directory = Path(temporary)
        path = directory / 'data é.bin'
        moved = directory / 'renamed é.bin'
        text = '''import "std/buffer"
import "std/files"
import "std/fs"
import "std/path"
fn main() -> unit ! files.FileError | fs.FsError | buffer.BufferError {
    let name = PATH
    let data = buffer.from_text("a\\0é\\r\\n")
    let output = files.open(name, 1)?
    output.write(data)?
    data.close()
    let c1 = output.close()
    let c2 = output.close()
    let sz = fs.size(name)?
    print(c1, c2, sz)
    let input = files.open(name, 0)?
    let mut total = 0
    while true {
        let chunk = input.read(2)?
        let count = chunk.size()
        total = total + count
        chunk.close()
        if count == 0 { break }
    }
    print(total, input.close())
    input.read(2) else error { print(error.operation, error.code > 0, error.domain > 0) return }
    return
}
main()
fs.rename(PATH, MOVED) else error { exit(1) }
print(fs.exists(PATH) else error { false }, fs.exists(MOVED) else error { false })
fs.remove(MOVED) else error { exit(1) }
print(path.join("root", "child"), path.basename("C:/é/file.wysna"), path.dirname("C:/file.wysna"))
'''.replace('PATH', json.dumps(str(path), ensure_ascii=False)).replace('MOVED', json.dumps(str(moved), ensure_ascii=False))
        expected = '0 0 6\n6 0\nread true true\nfalse true\nroot/child file.wysna C:/\n'
        for engine in ('interpreter', 'ast', 'hir', 'selfhost'):
            result = run_engine(engine, text, 'streaming', selfhost_bin, directory / engine,
                                sanitize=os.environ.get('WYSNA_SANITIZE') == '1')
            assert (result.exit_code, result.stdout, result.stderr) == (0, expected, ''), (
                f"Engine {engine} failed: exit={result.exit_code}, stdout={repr(result.stdout)}, stderr={repr(result.stderr)}"
            )
            assert not path.exists() and not moved.exists()


def test_host_handles_reject_stale_wrong_kind_and_oversized_requests():
    buffer = HostAbi.FUNCTIONS['wysna_host_buffer_new']()
    assert HostAbi.buffer_append(buffer, 256) == -1
    assert HostAbi.file_read(buffer, buffer, 1) == -1
    assert HostAbi.file_read(0, buffer, 16777217) == -1
    assert HostAbi.close(buffer) == 0
    fresh = HostAbi.FUNCTIONS['wysna_host_buffer_new']()
    assert fresh != buffer
    assert HostAbi.buffer_append(buffer, 1) == -1
    assert HostAbi.buffer_size(fresh) == 0
    HostAbi.close(fresh)
    code = '''#include "runtime/wysna_runtime.h"
#include <assert.h>
int main(void) {
    void* buffer = wysna_host_buffer_new();
    assert(wysna_host_buffer_append(buffer, 256) == -1);
    assert(wysna_host_file_read(buffer, buffer, 1) == -1);
    assert(wysna_host_file_read(NULL, buffer, 16777217) == -1);
    assert(wysna_host_close(buffer) == 0);
    void* fresh = wysna_host_buffer_new();
    assert(fresh != buffer && wysna_host_buffer_append(buffer, 1) == -1);
    assert(wysna_host_buffer_size(fresh) == 0);
    assert(wysna_host_close(fresh) == 0 && wysna_host_entries == NULL);
    assert(sizeof(WVal) == 32);
    return 0;
}
'''
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary) / 'handles.c'
        binary = Path(temporary) / executable_name('handles')
        source.write_text(code, encoding='utf-8')
        subprocess.run(compiler_command() + ['-std=c99'] + ([] if os.name == 'nt' else ['-fsanitize=address,undefined']) + ['-I' + str(ROOT),
                       str(source), '-o', str(binary)], check=True, capture_output=True, timeout=120)
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0 and not result.stderr, result


def test_large_file_processing_keeps_buffer_bounded():
    # The input is 2 MiB; both implementations reuse a 4 KiB compact buffer.
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        data_path = directory / 'input.bin'
        data_path.write_bytes(bytes(range(256)) * 8192)
        handle = HostAbi.allocate('buffer', bytearray(str(data_path).encode()))
        file = HostAbi.file_open(handle, 0)
        buffer = HostAbi.FUNCTIONS['wysna_host_buffer_new']()
        total = 0
        while True:
            count = HostAbi.file_read(file, buffer, 4096)
            assert 0 <= count <= 4096
            assert len(HostAbi.find(buffer, 'buffer')) <= 4096
            total += count
            if not count:
                break
        assert total == data_path.stat().st_size
        for value in (file, buffer, handle):
            HostAbi.close(value)
        source = directory / 'bounded.c'
        binary = directory / executable_name('bounded')
        source.write_text('''#include "runtime/wysna_runtime.h"
#include <assert.h>
int main(int argc, char** argv) {
    (void)argc;
    void* path = wysna_host_buffer_new();
    for (const unsigned char* p = (const unsigned char*)argv[1]; *p; p++) assert(wysna_host_buffer_append(path, *p) == 0);
    void* file = wysna_host_file_open(path, 0);
    void* buffer = wysna_host_buffer_new();
    int64_t total = 0, count;
    do {
        count = wysna_host_file_read(file, buffer, 4096);
        assert(count >= 0 && count <= 4096);
        assert(wysna_host_find(buffer, 1)->capacity == 4096);
        total += count;
    } while (count);
    assert(total == 2097152);
    wysna_host_close(file); wysna_host_close(buffer); wysna_host_close(path);
    assert(wysna_host_entries == NULL);
    return 0;
}
''', encoding='utf-8')
        subprocess.run(compiler_command() + ['-std=c99', '-O2', '-I' + str(ROOT), str(source), '-o', str(binary)],
                       check=True, capture_output=True, timeout=120)
        subprocess.run([str(binary), str(data_path)], check=True, capture_output=True, timeout=30)


def run_toolkit_tests():
    test_toolkit_semantics_across_four_engines()
    test_streaming_files_and_filesystem_across_four_engines()
    test_host_handles_reject_stale_wrong_kind_and_oversized_requests()
    test_large_file_processing_keeps_buffer_bounded()
    test_standard_file_cleanup_runs_on_runtime_panic()
    test_resource_duplicate_owner_is_rejected_without_disposal()
    return True




def test_standard_file_cleanup_runs_on_runtime_panic():
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        for backend in ('interpreter', 'ast', 'hir', 'selfhost'):
            output = directory / (backend + '.bin')
            source = directory / (backend + '.wysna')
            source.write_text('import "std/buffer"\nimport "std/files"\nfn main() {\n'
                f'let file = files.open({json.dumps(str(output))}, 1) else error {{ exit(2) return }}\n'
                'let data = buffer.from_text("flushed")\n'
                'file.write(data) else error { exit(2) }\nprint(1 / 0)\n}\n', encoding='utf-8')
            if backend == 'interpreter':
                command = [sys.executable, str(ROOT / 'main.py'), 'run', str(source)]
            else:
                binary = directory / executable_name(backend)
                built = subprocess.run([sys.executable, str(ROOT / 'main.py'), 'build', '--backend=' + backend,
                                        str(source), '-o', str(binary)], capture_output=True, text=True, timeout=120)
                assert built.returncode == 0, built.stderr
                command = [str(binary)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            assert result.returncode == 1 and 'W4001' in result.stderr, result
            assert output.read_bytes() == b'flushed'


def test_resource_duplicate_owner_is_rejected_without_disposal():
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        source = directory / 'owners.wysna'
        source.write_text('''import "std/resources"
extern "C" fn audit_open() -> opaque
extern "C" fn audit_dispose(handle: opaque) -> int32
extern "C" fn audit_live() -> int32
fn main() {
let handle = audit_open()
let first = resources.acquire(handle, |value: opaque| -> int { audit_dispose(value) }) else error { exit(2) return }
let second = new resources.Resource(handle, |value: opaque| -> int { audit_dispose(value) })
second.borrow() else error { print(error.message) }
print(second.close(), audit_live(), first.close(), audit_live(), first.close())
}
'''.replace('second.borrow() else error { print(error.message) }',
            'let rejected = resources.acquire(handle, |value: opaque| -> int { audit_dispose(value) }) else error { print(error.message)\nfirst }'), encoding='utf-8')
        adapter = ROOT / 'tests/ffi/resource_adapter.c'
        shared = directory / ('adapter.dll' if os.name == 'nt' else 'adapter.dylib' if sys.platform == 'darwin' else 'adapter.so')
        subprocess.run(compiler_command() + ['-std=c99', '-dynamiclib' if sys.platform == 'darwin' else '-shared',
                       str(adapter), '-o', str(shared)], check=True, capture_output=True, timeout=120)
        expected = 'resource already owned or released\n-1 1 0 0 0\n'
        for backend in ('interpreter', 'ast', 'hir', 'selfhost'):
            if backend == 'interpreter':
                command = [sys.executable, str(ROOT / 'main.py'), 'run', str(source), '--link-lib', str(shared)]
            else:
                binary = directory / executable_name(backend)
                built = subprocess.run([sys.executable, str(ROOT / 'main.py'), 'build', '--backend=' + backend,
                                        str(source), '--link-lib', str(adapter), '-o', str(binary)],
                                        capture_output=True, text=True, timeout=120)
                assert built.returncode == 0, built.stderr
                command = [str(binary)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=30, env=dict(os.environ, WYSNA_MEM_CHECK='1'))
            assert (result.returncode, result.stdout, result.stderr) == (0, expected, ''), result


if __name__ == '__main__':
    run_toolkit_tests()
