import atexit
import os
import sys
from typing import Any, Dict, List, Optional, Set, TextIO
from error.Error import WRuntimeError
from runtime.Values import (
    WValue, WInt, WFloat, WBool, WStr, WUnit, WNone,
    WList, WDict, WTuple, WStructInstance, WEnumValue, WEnumNamespace,
    WOk, WErr, WFunction, WNativeFunction, cow_telemetry
)

# ==========================================
# Control Flow Signals
# ==========================================

class ReturnSignal(Exception):
    def __init__(self, value: WValue):
        self.value = value


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


class PropagationSignal(Exception):
    """Signal used by postfix ? unwrapping for early return/propagation."""
    def __init__(self, value: WValue, is_error: bool = False):
        self.value = value
        self.is_error = is_error


# ==========================================
# Execution Environment
# ==========================================

class Environment:
    def __init__(self, parent: Optional['Environment'] = None, is_function_boundary: bool = False):
        self.parent = parent
        self.is_function_boundary = is_function_boundary
        self.bindings: Dict[str, WValue] = {}
        self.mutables: Set[str] = set()

    def declare(self, name: str, value: WValue, is_mut: bool = False) -> None:
        self.bindings[name] = value.clone_value()
        if is_mut:
            self.mutables.add(name)

    def assign(self, name: str, value: WValue) -> None:
        if name in self.bindings:
            if name not in self.mutables:
                raise WRuntimeError(f"Cannot assign to immutable binding '{name}'")
            self.bindings[name] = value.clone_value()
            return
        if self.parent is not None:
            self.parent.assign(name, value)
            return
        raise WRuntimeError(f"Undefined variable '{name}'")

    def lookup(self, name: str) -> WValue:
        if name in self.bindings:
            return self.bindings[name]
        if self.parent is not None:
            return self.parent.lookup(name)
        raise WRuntimeError(f"Undefined variable '{name}'")

    def exists(self, name: str) -> bool:
        if name in self.bindings:
            return True
        if self.parent is not None:
            return self.parent.exists(name)
        return False

    # Backward compatibility aliases
    def declare_var(self, name: str, value: WValue) -> WValue:
        self.declare(name, value, is_mut=True)
        return value

    def assign_var(self, name: str, value: WValue) -> WValue:
        self.assign(name, value)
        return value

    def lookup_var(self, name: str) -> WValue:
        return self.lookup(name)


def create_global_environment(stdout: Optional[TextIO] = None) -> Environment:
    """Pre-populates the top-level execution environment with W standard built-ins."""
    env = Environment()
    out = stdout if stdout is not None else sys.stdout

    # 1. I/O: print
    def print_fn(args: List[WValue]) -> WValue:
        rendered: List[str] = []
        for arg in args:
            if isinstance(arg, WStr):
                rendered.append(arg.value)
            else:
                rendered.append(str(arg))
        out.write(" ".join(rendered) + "\n")
        out.flush()
        return WUnit()

    def eprint_fn(args: List[WValue]) -> WValue:
        rendered: List[str] = []
        for arg in args:
            if isinstance(arg, WStr):
                rendered.append(arg.value)
            else:
                rendered.append(str(arg))
        msg = " ".join(rendered)
        if (os.environ.get("W_COW_METRICS") == "1" and len(args) == 1
                and isinstance(args[0], WStr) and msg.startswith("__COW_CHECKPOINT__:")):
            label = msg[19:]
            sys.stderr.write(
                f"[W_COW_CHECKPOINT:{label}] detach_list={cow_telemetry.detach_list} "
                f"detach_dict={cow_telemetry.detach_dict} detach_struct={cow_telemetry.detach_struct} "
                f"copied_slots={cow_telemetry.copied_slots}\n"
            )
        else:
            sys.stderr.write(msg + "\n")
        sys.stderr.flush()
        return WUnit()

    def exit_fn(args: List[WValue]) -> WValue:
        code = int(args[0].value) if args and isinstance(args[0], WInt) else 0
        sys.exit(code)

    env.declare("print", WNativeFunction("print", print_fn))
    env.declare("eprint", WNativeFunction("eprint", eprint_fn))
    env.declare("exit", WNativeFunction("exit", exit_fn))

    # 2. Collections: len
    def len_fn(args: List[WValue]) -> WValue:
        if len(args) != 1:
            raise WRuntimeError("len() takes exactly 1 argument")
        arg = args[0]
        if isinstance(arg, WList):
            return WInt(len(arg))
        if isinstance(arg, WDict):
            return WInt(len(arg))
        if isinstance(arg, WStr):
            return WInt(len(arg.value))
        raise WRuntimeError(f"len() not supported for '{type(arg).__name__}'")

    # 3. enumerate: list -> list of (int, T)
    def enumerate_fn(args: List[WValue]) -> WValue:
        if len(args) != 1:
            raise WRuntimeError("enumerate() takes exactly 1 argument")
        arg = args[0]
        if not isinstance(arg, WList):
            raise WRuntimeError("enumerate() expects list argument")
        tuples = [WTuple([WInt(i), elem]) for i, elem in enumerate(arg.storage.data)]
        return WList(elements=tuples)

    # 4. dict_items: dict -> list of (K, V)
    def dict_items_fn(args: List[WValue]) -> WValue:
        if len(args) != 1:
            raise WRuntimeError("dict_items() takes exactly 1 argument")
        arg = args[0]
        if not isinstance(arg, WDict):
            raise WRuntimeError("dict_items() expects dict argument")
        tuples = []
        for k, v in arg.storage.data.items():
            k_val = WStr(k) if isinstance(k, str) else WInt(k)
            tuples.append(WTuple([k_val, v]))
        return WList(elements=tuples)

    # 5. Type conversions
    def int_fn(args: List[WValue]) -> WValue:
        if len(args) != 1:
            raise WRuntimeError("int() takes exactly 1 argument")
        arg = args[0]
        if isinstance(arg, WInt):
            return arg
        if isinstance(arg, WFloat):
            return WInt(int(arg.value))
        if isinstance(arg, WStr):
            return WInt(int(arg.value))
        raise WRuntimeError(f"Cannot convert '{type(arg).__name__}' to int")

    def float_fn(args: List[WValue]) -> WValue:
        if len(args) != 1:
            raise WRuntimeError("float() takes exactly 1 argument")
        arg = args[0]
        if isinstance(arg, WFloat):
            return arg
        if isinstance(arg, WInt):
            return WFloat(float(arg.value))
        if isinstance(arg, WStr):
            return WFloat(float(arg.value))
        raise WRuntimeError(f"Cannot convert '{type(arg).__name__}' to float")

    def str_fn(args: List[WValue]) -> WValue:
        if len(args) != 1:
            raise WRuntimeError("str() takes exactly 1 argument")
        arg = args[0]
        if isinstance(arg, WStr):
            return arg
        return WStr(str(arg))

    def ord_fn(args: List[WValue]) -> WValue:
        if len(args) != 1:
            raise WRuntimeError("ord() takes exactly 1 argument")
        arg = args[0]
        if not isinstance(arg, WStr) or len(arg.value) == 0:
            raise WRuntimeError("ord() expects non-empty str argument")
        return WInt(ord(arg.value[0]))

    def chr_fn(args: List[WValue]) -> WValue:
        if len(args) != 1:
            raise WRuntimeError("chr() takes exactly 1 argument")
        arg = args[0]
        if not isinstance(arg, WInt):
            raise WRuntimeError("chr() expects int argument")
        return WStr(chr(arg.value))

    def slice_fn(args: List[WValue]) -> WValue:
        if len(args) != 3:
            raise WRuntimeError("slice() takes exactly 3 arguments (str, start, end)")
        s_arg, start_arg, end_arg = args[0], args[1], args[2]
        if not isinstance(s_arg, WStr) or not isinstance(start_arg, WInt) or not isinstance(end_arg, WInt):
            raise WRuntimeError("slice() expects (str, int, int)")
        return WStr(s_arg.value[start_arg.value:end_arg.value])

    def bytes_fn(args: List[WValue]) -> WValue:
        if len(args) != 1:
            raise WRuntimeError("bytes() takes exactly 1 argument")
        arg = args[0]
        if not isinstance(arg, WStr):
            raise WRuntimeError("bytes() expects str argument")
        return WList(elements=[WInt(b) for b in arg.value.encode('utf-8')])

    # 6. File I/O
    def read_file_fn(args: List[WValue]) -> WValue:
        if len(args) != 1:
            raise WRuntimeError("read_file() takes exactly 1 argument")
        arg = args[0]
        if not isinstance(arg, WStr):
            raise WRuntimeError("read_file() expects str path")
        try:
            with open(arg.value, 'r', encoding='utf-8') as f:
                content = f.read()
            return WOk(WStr(content))
        except Exception as e:
            return WErr(WStructInstance("IoError", fields={"message": WStr(str(e))}))

    def write_file_fn(args: List[WValue]) -> WValue:
        if len(args) != 2:
            raise WRuntimeError("write_file() takes exactly 2 arguments (path, content)")
        p_arg, c_arg = args[0], args[1]
        if not isinstance(p_arg, WStr) or not isinstance(c_arg, WStr):
            raise WRuntimeError("write_file() expects str path and str content")
        try:
            with open(p_arg.value, 'w', encoding='utf-8') as f:
                f.write(c_arg.value)
            return WOk(WUnit())
        except Exception as e:
            return WErr(WStructInstance("IoError", fields={"message": WStr(str(e))}))

    def args_fn(args_list: List[WValue]) -> WValue:
        return WList(elements=[WStr(a) for a in sys.argv])

    def some_fn(args: List[WValue]) -> WValue:
        if len(args) != 1:
            raise WRuntimeError("Some() takes exactly 1 argument")
        return WEnumValue("Option", "Some", [args[0]])

    def ok_fn(args: List[WValue]) -> WValue:
        if len(args) != 1:
            raise WRuntimeError("Ok() takes exactly 1 argument")
        return WOk(args[0])

    def err_fn(args: List[WValue]) -> WValue:
        if len(args) != 1:
            raise WRuntimeError("Err() takes exactly 1 argument")
        return WErr(args[0])

    # Register builtins
    env.declare("print", WNativeFunction("print", print_fn), is_mut=False)
    env.declare("len", WNativeFunction("len", len_fn), is_mut=False)
    env.declare("enumerate", WNativeFunction("enumerate", enumerate_fn), is_mut=False)
    env.declare("dict_items", WNativeFunction("dict_items", dict_items_fn), is_mut=False)
    env.declare("int", WNativeFunction("int", int_fn), is_mut=False)
    env.declare("float", WNativeFunction("float", float_fn), is_mut=False)
    env.declare("str", WNativeFunction("str", str_fn), is_mut=False)
    env.declare("ord", WNativeFunction("ord", ord_fn), is_mut=False)
    env.declare("chr", WNativeFunction("chr", chr_fn), is_mut=False)
    env.declare("slice", WNativeFunction("slice", slice_fn), is_mut=False)
    env.declare("bytes", WNativeFunction("bytes", bytes_fn), is_mut=False)
    env.declare("read_file", WNativeFunction("read_file", read_file_fn), is_mut=False)
    env.declare("write_file", WNativeFunction("write_file", write_file_fn), is_mut=False)
    env.declare("args", WNativeFunction("args", args_fn), is_mut=False)

    env.declare("Some", WNativeFunction("Some", some_fn), is_mut=False)
    env.declare("Ok", WNativeFunction("Ok", ok_fn), is_mut=False)
    env.declare("Err", WNativeFunction("Err", err_fn), is_mut=False)
    env.declare("None", WEnumValue("Option", "None"), is_mut=False)
    env.declare("Option", WEnumNamespace("Option", ["Some", "None"]), is_mut=False)
    env.declare("Result", WEnumNamespace("Result", ["Ok", "Err"]), is_mut=False)

    return env


def _dump_cow_metrics():
    if os.environ.get("W_COW_METRICS") == "1":
        sys.stderr.write(
            f"[W_COW_METRICS] detach_list={cow_telemetry.detach_list} "
            f"detach_dict={cow_telemetry.detach_dict} detach_struct={cow_telemetry.detach_struct} "
            f"copied_slots={cow_telemetry.copied_slots}\n"
        )
        sys.stderr.flush()

atexit.register(_dump_cow_metrics)

