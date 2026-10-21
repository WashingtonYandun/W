"""Execute explicitly declared scalar/opaque C functions in the reference engine."""
import ctypes
import ctypes.util
import os
from error.Error import WRuntimeError
from runtime.Values import WInt, WFloat, WBool, WUnit, WPointer

C_TYPES = {'int': ctypes.c_int64, 'int64': ctypes.c_int64, 'int32': ctypes.c_int32,
           'float': ctypes.c_double, 'double': ctypes.c_double, 'bool': ctypes.c_bool,
           'opaque': ctypes.c_void_p, 'unit': None}


def bind_foreign(declaration, libraries=()):
    signature = [p.type_ann.name for p in declaration.params]
    returned = declaration.return_type.name
    name = getattr(declaration, 'source_name', declaration.name)
    from runtime.HostAbi import FUNCTIONS
    internal = FUNCTIONS.get(name)
    handles = [] if internal else ([ctypes.CDLL(None)] if os.name != 'nt' else [])
    for library in ([] if internal else list(libraries) + ([] if os.name == 'nt' else ['m'])):
        path = library if os.path.isfile(library) else ctypes.util.find_library(library)
        if path:
            try:
                kwargs = {'winmode': 0} if (os.name == 'nt' and sys.version_info >= (3, 8)) else {}
                handles.append(ctypes.CDLL(path, **kwargs))
            except Exception:
                pass
    function = internal or next((getattr(handle, name) for handle in handles if hasattr(handle, name)), None)
    if function is None:
        raise WRuntimeError("Unresolved C symbol: " + name, code='W4003')
    if not internal:
        function.argtypes = [C_TYPES[t] for t in signature]
        function.restype = C_TYPES[returned]

    def invoke(arguments):
        raw = []
        for argument, type_ in zip(arguments, signature):
            value = argument.address if type_ == 'opaque' else argument.value
            if type_ == 'int32' and not -2147483648 <= value <= 2147483647:
                raise WRuntimeError('int32 FFI argument out of range', code='W4003')
            raw.append(value)
        result = function(*raw)
        if returned == 'unit':
            return WUnit()
        constructor = {'int': WInt, 'int32': WInt, 'int64': WInt, 'float': WFloat,
                       'double': WFloat, 'bool': WBool, 'opaque': WPointer}[returned]
        return constructor(result)
    return invoke
