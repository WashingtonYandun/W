"""Reference implementation of the internal, checked scalar/opaque resource ABI."""
import atexit
from pathlib import Path

_entries = {}
_next_id = 1


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
        except OSError:
            return -1
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
        return 0
    try:
        return allocate('file', open(path, ('rb', 'wb', 'ab')[mode]))
    except OSError:
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
    if file is None or buffer is None or not 0 < count <= 16777216:
        return -1
    try:
        buffer[:] = file.read(count)
        return len(buffer)
    except (OSError, ValueError):
        return -1


def file_write(file_handle, buffer_handle):
    file, buffer = find(file_handle, 'file'), find(buffer_handle, 'buffer')
    if file is None or buffer is None:
        return -1
    try:
        written = file.write(buffer)
        if written != len(buffer):
            return -1
        file.flush()
        return 0
    except (OSError, ValueError):
        return -1


def filesystem(first, second, operation):
    text = path_text(first)
    other = path_text(second) if operation == 4 else None
    if text is None or (operation == 4 and other is None):
        return -1
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
    except (OSError, ValueError):
        return -1


def claim(raw):
    if any(kind == 'claim' and value == raw for kind, value in _entries.values()):
        return 0
    return allocate('claim', raw)


FUNCTIONS = {
    'w_host_claim': claim,
    'w_host_claim_valid': lambda handle: int(find(handle, 'claim') is not None),
    'w_host_buffer_new': lambda: allocate('buffer', bytearray()),
    'w_host_buffer_size': buffer_size,
    'w_host_buffer_get': buffer_get,
    'w_host_buffer_append': buffer_append,
    'w_host_close': close,
    'w_host_file_open': file_open,
    'w_host_file_read': file_read,
    'w_host_file_write': file_write,
    'w_host_is_open': lambda handle: int(find(handle, 'file') is not None),
    'w_host_fs': filesystem,
}
