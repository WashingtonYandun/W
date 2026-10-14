"""Native B03 control-block lifetime assertions under sanitizers."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

CONTRACT = r'''
#include "runtime/w_runtime.h"
#include <assert.h>
int main(void) {
    WVal object = w_make_object("Node", 0, NULL, NULL);
    WVal weak = w_builtin_weak(object);
    WVal copy = w_clone(weak);
    WWeakControl* control = weak.as.weak;
    assert(control->strong == 1 && control->weak == 3);
    WVal upgraded = w_builtin_upgrade(weak);
    assert(control->strong == 2 && w_eq(object, upgraded));
    w_release(object);
    assert(control->strong == 1);
    w_release(upgraded);
    assert(control->object == NULL && control->strong == 0 && control->weak == 2);
    assert(w_builtin_upgrade(weak).tag == W_NONE);
    assert(w_eq(weak, copy));
    w_release(copy);
    assert(control->weak == 1);
    WVal other = w_make_object("Node", 0, NULL, NULL);
    WVal other_weak = w_builtin_weak(other);
    w_release(other);
    assert(!w_eq(weak, other_weak));
    w_release(weak); w_release(other_weak);
    assert(w_g_live_objects == 0);
    const char* fields[1] = {"link"};
    WVal empty[1] = {w_none()};
    object = w_make_object("Self", 1, fields, empty);
    weak = w_builtin_weak(object);
    w_assign(w_member_ref(&object, "link"), w_clone(weak));
    w_release(weak);
    w_release(object);
    assert(w_g_live_objects == 0);
    WVal parent = w_make_object("Parent", 1, fields, empty);
    weak = w_builtin_weak(parent);
    WVal values[1] = {weak};
    WVal child = w_make_object("Child", 1, fields, values);
    w_assign(w_member_ref(&parent, "link"), w_clone(child));
    w_release(child);
    w_release(parent);
    assert(weak.as.weak->object == NULL);
    w_release(weak);
    assert(w_g_live_objects == 0);
    w_runtime_cleanup();
    return 0;
}
'''


def run_control_block_tests():
    root = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix='w-weak-control-') as directory:
        source, binary = Path(directory) / 'test.c', Path(directory) / 'test'
        source.write_text(CONTRACT)
        built = subprocess.run([os.environ.get('CC', 'cc'), '-std=c99', '-g',
                                '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                                '-I' + str(root), str(source), '-o', str(binary)],
                               capture_output=True, text=True, timeout=60)
        assert built.returncode == 0, built.stderr
        env = dict(os.environ, W_MEM_CHECK='1')
        env['ASAN_OPTIONS'] = 'detect_leaks=1' if sys.platform.startswith('linux') else 'detect_leaks=0'
        result = subprocess.run([str(binary)], env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
    print('  [PASS] Weak strong/weak counts, upgrade, expiration, identity and destruction order')


if __name__ == '__main__':
    run_control_block_tests()
