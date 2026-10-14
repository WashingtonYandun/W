"""Check opt-in telemetry and native byte accounting without assuming a C ABI."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from runtime.Environment import create_global_environment
from runtime.Interpreter import Interpreter
from runtime.Values import WStr, WInt, WList, WDict, WStructInstance, cow_telemetry


NATIVE_CONTRACT = r'''
#include "runtime/w_runtime.h"
#include <assert.h>
int main(void) {
    WVal args[2] = {w_str("__COW_CHECKPOINT__:ordinary"), w_str("second")};
    w_builtin_eprint(2, args);
    w_builtin_eprint(1, args);
    WVal items[5] = {w_int(1), w_int(2), w_int(3), w_int(4), w_int(5)};
    WVal list = w_make_list(5, items);
    for (int i = 0; i < 4; i++) w_release(w_list_pop(&list));
    WVal alias = w_clone(list);
    w_cow_reset_stats();
    w_list_detach(&list);
    assert(w_g_cow_detach_list == 1 && w_g_cow_copied_slots == 1);
    assert(w_g_cow_copied_bytes == sizeof(WVal));
    assert(w_g_cow_allocated_bytes == sizeof(WListBuf) + 5 * sizeof(WVal));
    assert(w_g_cow_alloc_count == 2);
    w_list_detach(&list);
    assert(w_g_cow_detach_list == 1);
    w_release(alias); w_release(list);
    WVal dict = w_make_dict(0, NULL, NULL);
    for (int i = 0; i < 5; i++) w_assign(w_index_ref(&dict, w_int(i)), w_int(i));
    alias = w_clone(dict);
    w_cow_reset_stats();
    w_dict_detach(&dict);
    assert(w_g_cow_copied_slots == 10 && w_g_cow_detach_dict == 1);
    assert(w_g_cow_copied_bytes == 10 * sizeof(WVal));
    assert(w_g_cow_allocated_bytes == sizeof(WDictBuf) + 16 * sizeof(WVal));
    assert(w_g_cow_alloc_count == 3);
    w_release(alias); w_release(dict);
    WVal record = w_make_struct("Empty", 0, NULL, NULL);
    alias = w_clone(record);
    w_cow_reset_stats();
    w_struct_detach(&record);
    assert(w_g_cow_copied_slots == 0 && w_g_cow_copied_bytes == 0);
    assert(w_g_cow_allocated_bytes == sizeof(WStructBuf) + sizeof(char*) + sizeof(WVal));
    assert(w_g_cow_alloc_count == 3);
    w_release(alias); w_release(record);
    WVal rows[3] = {w_make_list(2, items), w_make_list(2, items), w_make_list(2, items)};
    WVal matrix = w_make_list(3, rows);
    for (int i = 0; i < 3; i++) w_release(rows[i]);
    alias = w_clone(matrix);
    w_cow_reset_stats();
    w_assign(w_index_ref(w_index_ref(&matrix, w_int(0)), w_int(0)), w_int(99));
    assert(w_g_cow_detach_list == 2 && w_g_cow_copied_slots == 5);
    assert(matrix.as.list->data[0].as.list != alias.as.list->data[0].as.list);
    assert(matrix.as.list->data[1].as.list == alias.as.list->data[1].as.list);
    assert(matrix.as.list->data[2].as.list == alias.as.list->data[2].as.list);
    w_assign(w_index_ref(w_index_ref(&matrix, w_int(0)), w_int(1)), w_int(88));
    assert(w_g_cow_detach_list == 2 && w_g_cow_copied_slots == 5);
    w_release(alias); w_release(matrix);
    w_cow_reset_stats();
    assert(w_g_cow_allocated_bytes == 0 && w_g_cow_copied_bytes == 0);
    w_runtime_cleanup();
    return 0;
}
'''


def run_metrics_contract():
    previous = os.environ.get('W_COW_METRICS')
    marker = '__COW_CHECKPOINT__:ordinary'
    try:
        for enabled in [False, True]:
            os.environ['W_COW_METRICS'] = '1' if enabled else '0'
            output = io.StringIO()
            cow_telemetry.reset()
            with contextlib.redirect_stderr(output):
                eprint = create_global_environment().lookup('eprint').call_fn
                eprint([WStr(marker), WStr('second')])
                eprint([WStr(marker)])
            lines = output.getvalue().splitlines()
            assert lines[0] == marker + ' second'
            assert len(lines) == 2
            assert lines[1].startswith('[W_COW_CHECKPOINT:ordinary]') if enabled else lines[1] == marker
        cow_telemetry.detach_list = 7
        Interpreter()
        assert cow_telemetry.detach_list == 7, 'Creating an import interpreter must not reset process counters'
    finally:
        cow_telemetry.reset()
        if previous is None:
            os.environ.pop('W_COW_METRICS', None)
        else:
            os.environ['W_COW_METRICS'] = previous
    for value in [WList(elements=[WInt(1)]), WDict(pairs={"key": WInt(1)}),
                  WStructInstance("Record", fields={"value": WInt(1)})]:
        alias = value.clone_value()
        assert value.storage.refcount == 2
        del alias
        assert value.storage.refcount == 1, "Dead aliases must release their buffer reference"
        cow_telemetry.reset()
        value.ensure_unique()
        assert cow_telemetry.copied_slots == 0
    root = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix='w-cow-contract-') as directory:
        source, binary = Path(directory) / 'contract.c', Path(directory) / 'contract'
        source.write_text(NATIVE_CONTRACT)
        subprocess.run([os.environ.get('CC', 'cc'), '-std=c99', '-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer', '-I' + str(root), str(source), '-o', str(binary)],
                       check=True, capture_output=True, text=True, timeout=60)
        for enabled in [False, True]:
            env = dict(os.environ, W_COW_METRICS='1' if enabled else '0', W_MEM_CHECK='1')
            env['ASAN_OPTIONS'] = 'detect_leaks=1' if sys.platform.startswith('linux') else 'detect_leaks=0'
            result = subprocess.run([str(binary)], env=env, capture_output=True, text=True, timeout=30)
            assert result.returncode == 0, result.stderr
            lines = result.stderr.splitlines()
            assert lines[0] == marker + ' second'
            assert lines[1].startswith('[W_COW_CHECKPOINT:ordinary]') if enabled else lines[1] == marker
            assert len(lines) == (3 if enabled else 2), result.stderr
    print('  [PASS] CoW opt-in output, import lifetime and native ABI/capacity accounting')


if __name__ == '__main__':
    run_metrics_contract()
