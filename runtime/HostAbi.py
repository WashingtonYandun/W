"""Reference implementation of the internal, checked scalar/opaque resource ABI."""
import atexit
import errno
import os
from pathlib import Path
import signal
import subprocess

_entries = {}
_next_id = 1
_error_code = 0
_error_domain = 0
_process_jobs = {}


def failure(error):
    global _error_code, _error_domain
    _error_code = getattr(error, 'winerror', None) or getattr(error, 'errno', None) or errno.EIO
    _error_domain = 2 if getattr(error, 'winerror', None) else 1
    return -1


def allocate(kind, value):
    global _next_id
    handle = _next_id
    _next_id += 1
    _entries[handle] = (kind, value)
    return handle


def find(handle, kind):
    entry = _entries.get(handle)
    return entry[1] if entry and entry[0] == kind else None


def close(handle):
    entry = _entries.pop(handle, None)
    if entry and entry[0] == 'file':
        try:
            entry[1].close()
        except OSError as error:
            return failure(error)
    return 0


def cleanup():
    for handle in list(_entries):
        close(handle)


atexit.register(cleanup)


def path_text(handle):
    data = find(handle, 'buffer')
    if not data or 0 in data:
        return None
    try:
        return data.decode('utf-8')
    except UnicodeError:
        return None


def file_open(handle, mode):
    path = path_text(handle)
    if path is None or mode not in (0, 1, 2):
        failure(OSError(errno.EINVAL, 'invalid path or mode'))
        return 0
    try:
        return allocate('file', open(path, ('rb', 'wb', 'ab')[mode]))
    except OSError as error:
        failure(error)
        return 0


def buffer_get(handle, index):
    data = find(handle, 'buffer')
    return data[index] if data is not None and 0 <= index < len(data) else -1


def buffer_size(handle):
    data = find(handle, 'buffer')
    return len(data) if data is not None else -1


def buffer_append(handle, value):
    data = find(handle, 'buffer')
    if data is None or not 0 <= value <= 255:
        return -1
    data.append(value)
    return 0


def file_read(file_handle, buffer_handle, count):
    file, buffer = find(file_handle, 'file'), find(buffer_handle, 'buffer')
    if file is None or buffer is None:
        return failure(OSError(errno.EBADF, 'closed handle'))
    if not 0 < count <= 16777216:
        return failure(OSError(errno.EINVAL, 'invalid read bound'))
    try:
        buffer[:] = file.read(count)
        return len(buffer)
    except (OSError, ValueError) as error:
        return failure(error)


def file_write(file_handle, buffer_handle):
    file, buffer = find(file_handle, 'file'), find(buffer_handle, 'buffer')
    if file is None or buffer is None:
        return failure(OSError(errno.EBADF, 'closed handle'))
    try:
        written = file.write(buffer)
        if written != len(buffer):
            return failure(OSError(errno.EIO, 'short write'))
        file.flush()
        return 0
    except (OSError, ValueError) as error:
        return failure(error)


def filesystem(first, second, operation):
    text = path_text(first)
    other = path_text(second) if operation == 4 else None
    if text is None or (operation == 4 and other is None):
        return failure(OSError(errno.EINVAL, 'invalid path'))
    path = Path(text)
    try:
        if operation in (0, 1):
            try:
                status = path.stat()
            except FileNotFoundError:
                return 0 if operation == 0 else -1
            return 1 if operation == 0 else status.st_size
        if operation == 2:
            path.mkdir()
        elif operation == 3:
            path.rmdir() if path.is_dir() else path.unlink()
        elif operation == 4:
            path.rename(other)
        else:
            return -1
        return 0
    except (OSError, ValueError) as error:
        return failure(error)


def claim(raw):
    if any(kind == 'claim' and value == raw for kind, value in _entries.values()):
        return 0
    return allocate('claim', raw)


def attach_process_tree(process):
    """Place a Windows child in a kill-on-close job when the host permits it."""
    if os.name != 'nt':
        return
    import ctypes
    from ctypes import wintypes

    class BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ('PerProcessUserTimeLimit', ctypes.c_longlong),
            ('PerJobUserTimeLimit', ctypes.c_longlong),
            ('LimitFlags', wintypes.DWORD),
            ('MinimumWorkingSetSize', ctypes.c_size_t),
            ('MaximumWorkingSetSize', ctypes.c_size_t),
            ('ActiveProcessLimit', wintypes.DWORD),
            ('Affinity', ctypes.c_size_t),
            ('PriorityClass', wintypes.DWORD),
            ('SchedulingClass', wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            'ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
            'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

    class ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ('BasicLimitInformation', BasicLimitInformation),
            ('IoInfo', IoCounters),
            ('ProcessMemoryLimit', ctypes.c_size_t),
            ('JobMemoryLimit', ctypes.c_size_t),
            ('PeakProcessMemoryUsed', ctypes.c_size_t),
            ('PeakJobMemoryUsed', ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return
    limits = ExtendedLimitInformation()
    limits.BasicLimitInformation.LimitFlags = 0x00002000
    if not kernel32.SetInformationJobObject(
            job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        kernel32.CloseHandle(job)
        return
    if not kernel32.AssignProcessToJobObject(job, wintypes.HANDLE(process._handle)):
        kernel32.CloseHandle(job)
        return
    _process_jobs[process.pid] = (job, kernel32)


def release_process_tree(process):
    """Close the child job so any remaining descendants are stopped."""
    record = _process_jobs.pop(process.pid, None)
    if record is not None:
        job, kernel32 = record
        kernel32.CloseHandle(job)


def terminate_process_tree(process, *, force_group=False):
    """Stop a child and its descendants after a timeout or capture limit."""
    if process.poll() is not None and not force_group:
        return
    record = _process_jobs.get(process.pid)
    if record is not None:
        job, kernel32 = record
        kernel32.TerminateJobObject(job, 1)
    if os.name == 'nt':
        system_root = os.environ.get('SystemRoot', r'C:\Windows')
        taskkill = Path(system_root) / 'System32' / 'taskkill.exe'
        if taskkill.is_file():
            try:
                subprocess.run([str(taskkill), '/PID', str(process.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               check=False, timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
    try:
        process.kill()
    except OSError:
        pass


def process_run(executable_handle, arguments_handle, timeout_ms, *, cwd=None, env=None):
    global _error_code, _error_domain
    _error_code = 0
    _error_domain = 0
    executable_bytes = find(executable_handle, 'buffer')
    encoded_arguments = find(arguments_handle, 'buffer')
    if executable_bytes is None or encoded_arguments is None or not 1 <= timeout_ms <= 600000:
        return failure(OSError(errno.EINVAL, 'invalid process request'))
    if not executable_bytes or b'\x00' in executable_bytes:
        return failure(OSError(errno.EINVAL, 'invalid executable path'))
    try:
        executable = executable_bytes.decode('utf-8')
        arguments = []
        offset = 0
        while offset < len(encoded_arguments):
            if len(arguments) >= 256 or offset + 4 > len(encoded_arguments):
                return failure(OSError(errno.E2BIG, 'invalid argument block'))
            length = int.from_bytes(encoded_arguments[offset:offset + 4], 'big')
            offset += 4
            if length > 1048576 or offset + length > len(encoded_arguments):
                return failure(OSError(errno.E2BIG, 'argument exceeds its limit'))
            raw_argument = encoded_arguments[offset:offset + length]
            offset += length
            if b'\x00' in raw_argument:
                return failure(OSError(errno.EINVAL, 'argument contains NUL'))
            arguments.append(raw_argument.decode('utf-8'))
            if offset > 16777216:
                return failure(OSError(errno.E2BIG, 'argument block exceeds its limit'))
        process = subprocess.Popen(
            [executable, *arguments], cwd=cwd,
            env=dict(env) if env is not None else None,
            start_new_session=(os.name != 'nt'),
            creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0),
        )
        attach_process_tree(process)
        try:
            try:
                exit_code = int(process.wait(timeout=timeout_ms / 1000))
                return 128 + abs(exit_code) if exit_code < 0 else exit_code
            except subprocess.TimeoutExpired:
                terminate_process_tree(process, force_group=True)
                process.wait()
                return failure(TimeoutError(errno.ETIMEDOUT, 'process timed out'))
        finally:
            release_process_tree(process)
    except (OSError, UnicodeError, ValueError) as error:
        return failure(error)


FUNCTIONS = {
    'wysna_host_last_error': lambda: _error_code,
    'wysna_host_last_error_domain': lambda: _error_domain,
    'wysna_host_borrow': lambda handle: handle,
    'wysna_host_active_handles': lambda: len(_entries),
    'wysna_host_active_bytes': lambda: sum(len(value) for kind, value in _entries.values() if kind == 'buffer'),
    'wysna_host_claim': claim,
    'wysna_host_claim_valid': lambda handle: int(find(handle, 'claim') is not None),
    'wysna_host_buffer_new': lambda: allocate('buffer', bytearray()),
    'wysna_host_buffer_size': buffer_size,
    'wysna_host_buffer_get': buffer_get,
    'wysna_host_buffer_append': buffer_append,
    'wysna_host_close': close,
    'wysna_host_file_open': file_open,
    'wysna_host_file_read': file_read,
    'wysna_host_file_write': file_write,
    'wysna_host_is_open': lambda handle: int(find(handle, 'file') is not None),
    'wysna_host_fs': filesystem,
    'wysna_host_process_run': process_run,
}
