import io
import os
import random
import subprocess
import sys
import tempfile
from typing import List, Tuple
from lexer.Lexer import Lexer
from parser.Parser import Parser
from checker.TypeChecker import TypeChecker
from runtime.Interpreter import Interpreter
from formatter.Formatter import Formatter
from codegen.CCodeGen import CCodeGen
from error.Error import WError


class EngineResult:
    def __init__(self, engine: str, stdout: str, stderr: str, exit_code: int) -> None:
        self.engine = engine
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code


def run_w0_interpreter(source_code: str, file_name: str) -> EngineResult:
    old_stdout = sys.stdout
    buf_out = io.StringIO()
    sys.stdout = buf_out
    try:
        ast = Parser(file=file_name).parse(source_code)
        TypeChecker(file=file_name).check(ast)
        Interpreter(file=file_name).interpret(ast)
        return EngineResult(
            engine="W0_Interpreter",
            stdout=buf_out.getvalue(),
            stderr="",
            exit_code=0,
        )
    except WError as err:
        return EngineResult(
            engine="W0_Interpreter",
            stdout=buf_out.getvalue(),
            stderr=str(err),
            exit_code=1,
        )
    finally:
        sys.stdout = old_stdout


def run_w0_c99_native(source_code: str, file_name: str, repo_root: str, work_dir: str) -> EngineResult:
    try:
        ast = Parser(file=file_name).parse(source_code)
        TypeChecker(file=file_name).check(ast)
        c_code = CCodeGen(file=file_name).generate(ast)
    except WError as err:
        return EngineResult(
            engine="W0_C99_Native",
            stdout="",
            stderr=str(err),
            exit_code=1,
        )

    c_path = os.path.join(work_dir, "w0_prog.c")
    bin_path = os.path.join(work_dir, "w0_prog_bin")
    with open(c_path, "w", encoding="utf-8") as cf:
        cf.write(c_code)

    comp = subprocess.run(
        ["cc", "-std=c99", "-O1", f"-I{repo_root}", c_path, "-o", bin_path],
        capture_output=True,
        text=True,
    )
    if comp.returncode != 0:
        return EngineResult(
            engine="W0_C99_Native",
            stdout="",
            stderr=comp.stderr,
            exit_code=comp.returncode,
        )

    exec_proc = subprocess.run(
        [bin_path],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    return EngineResult(
        engine="W0_C99_Native",
        stdout=exec_proc.stdout,
        stderr=exec_proc.stderr,
        exit_code=exec_proc.returncode,
    )


def run_w1_c99_native(source_code: str, w1_bin: str, repo_root: str, work_dir: str) -> EngineResult:
    src_path = os.path.join(work_dir, "w1_input.w")
    c_path = os.path.join(work_dir, "w1_prog.c")
    bin_path = os.path.join(work_dir, "w1_prog_bin")

    with open(src_path, "w", encoding="utf-8") as sf:
        sf.write(source_code)

    w1_comp = subprocess.run(
        [w1_bin, src_path, c_path],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    if w1_comp.returncode != 0:
        return EngineResult(
            engine="W1_C99_Native",
            stdout="",
            stderr=w1_comp.stderr,
            exit_code=w1_comp.returncode,
        )

    cc_comp = subprocess.run(
        ["cc", "-std=c99", "-O1", f"-I{repo_root}", c_path, "-o", bin_path],
        capture_output=True,
        text=True,
    )
    if cc_comp.returncode != 0:
        return EngineResult(
            engine="W1_C99_Native",
            stdout="",
            stderr=cc_comp.stderr,
            exit_code=cc_comp.returncode,
        )

    exec_proc = subprocess.run(
        [bin_path],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    return EngineResult(
        engine="W1_C99_Native",
        stdout=exec_proc.stdout,
        stderr=exec_proc.stderr,
        exit_code=exec_proc.returncode,
    )


def verify_three_way_equivalence(
    source_code: str,
    label: str,
    w1_bin: str,
    repo_root: str,
    work_dir: str,
) -> Tuple[bool, str]:
    res_interp = run_w0_interpreter(source_code, label)
    res_w0_c = run_w0_c99_native(source_code, label, repo_root, work_dir)
    res_w1_c = run_w1_c99_native(source_code, w1_bin, repo_root, work_dir)

    if res_interp.exit_code != res_w0_c.exit_code or res_interp.exit_code != res_w1_c.exit_code:
        msg = (
            f"Exit code mismatch on {label}:\n"
            f"  W0 Interp: {res_interp.exit_code} ({res_interp.stderr.strip()})\n"
            f"  W0 C99:    {res_w0_c.exit_code} ({res_w0_c.stderr.strip()})\n"
            f"  W1 C99:    {res_w1_c.exit_code} ({res_w1_c.stderr.strip()})"
        )
        return False, msg

    if res_interp.stdout != res_w0_c.stdout or res_interp.stdout != res_w1_c.stdout:
        msg = (
            f"Stdout mismatch on {label}:\n"
            f"  --- W0 Interp ---\n{res_interp.stdout}"
            f"  --- W0 C99 ---\n{res_w0_c.stdout}"
            f"  --- W1 C99 ---\n{res_w1_c.stdout}"
        )
        return False, msg

    return True, "OK"


def generate_valid_program(seed: int) -> str:
    rng = random.Random(seed)
    a_val = rng.randint(-50, 50)
    b_val = rng.randint(1, 25)
    c_val = rng.randint(-20, 20)
    loop_limit = rng.randint(2, 6)
    list_elems: List[str] = []
    for _ in range(rng.randint(2, 5)):
        list_elems.append(str(rng.randint(-15, 30)))
    list_literal = "[" + ", ".join(list_elems) + "]"

    lines: List[str] = [
        f"# Generated differential program (seed = {seed})",
        "struct Pair {",
        "    left: int",
        "    right: int",
        "}",
        "",
        "class Counter {",
        "    public value: int",
        "    fn init(v: int) {",
        "        this.value = v",
        "    }",
        "    public fn add(delta: int) -> int {",
        "        this.value = this.value + delta",
        "        return this.value",
        "    }",
        "}",
        "",
        "fn compute(x: int, y: int) -> int {",
        "    if x > y {",
        "        return x * 2 - y",
        "    } elif x == y {",
        "        return x + y",
        "    } else {",
        "        return y * 3 + x",
        "    }",
        "}",
        "",
        "fn main() -> unit {",
        f"    let a: int = {a_val}",
        f"    let b: int = {b_val}",
        f"    let c: int = {c_val}",
        "    let p1 = Pair { left: a, right: b }",
        "    let mut p2 = p1",
        "    p2.left = p2.left + c",
        '    print("pair:", p1.left, p1.right, p2.left, p2.right)',
        f"    let items: list[int] = {list_literal}",
        "    let mut copy_items = items",
        "    copy_items.append(a + b)",
        "    let mut total = 0",
        f"    for i in 1..={loop_limit} {{",
        "        total = total + compute(a + i, b)",
        "    }",
        "    for x in copy_items {",
        "        total = total + x",
        "    }",
        "    let ctr = new Counter(total)",
        "    let alias = ctr",
        "    let after = alias.add(b)",
        '    print("res:", len(items), len(copy_items), ctr.value, after, ctr == alias)',
        "}",
    ]
    return "\n".join(lines) + "\n"


def run_differential_suite(repo_root: str, w1_bin: str, generated_count: int = 25, base_seed: int = 1000) -> bool:
    cases_dir = os.path.join(repo_root, "tests", "differential", "cases")
    failures_dir = os.path.join(repo_root, "tests", "differential", "failures")
    os.makedirs(failures_dir, exist_ok=True)

    case_files: List[str] = []
    if os.path.exists(cases_dir):
        for fname in sorted(os.listdir(cases_dir)):
            if fname.endswith(".w"):
                case_files.append(os.path.join(cases_dir, fname))

    passed_cases = 0
    total_cases = len(case_files) + generated_count

    with tempfile.TemporaryDirectory() as work_dir:
        for path in case_files:
            label = os.path.basename(path)
            with open(path, "r", encoding="utf-8") as f:
                code = f.read()
            ok, detail = verify_three_way_equivalence(code, label, w1_bin, repo_root, work_dir)
            if ok:
                passed_cases += 1
            else:
                print(f"  [DIFF FAIL] {label}: {detail}")

        for offset in range(generated_count):
            seed = base_seed + offset
            code = generate_valid_program(seed)
            label = f"seed_{seed}.w"
            ok, detail = verify_three_way_equivalence(code, label, w1_bin, repo_root, work_dir)
            if ok:
                passed_cases += 1
            else:
                fail_path = os.path.join(failures_dir, label)
                with open(fail_path, "w", encoding="utf-8") as ff:
                    ff.write(code)
                print(f"  [DIFF FAIL] Generated program failed (saved to {fail_path}):\n{detail}")

    print(f"Differential Oracle: {passed_cases}/{total_cases} (W0 Interp == W0 C99 == W1 C99)")
    return passed_cases == total_cases


def generate_fuzz_input(seed: int) -> str:
    rng = random.Random(seed)
    fragments = [
        "fn", "let", "mut", "struct", "enum", "class", "interface", "extends", "implements",
        "new", "this", "super", "public", "private", "if", "elif", "else", "for", "while",
        "in", "match", "return", "break", "continue", "true", "false", "none", "and", "or", "not",
        "int", "float", "bool", "str", "unit", "list", "dict", "tuple",
        "x", "y", "Foo", "Bar", "init", "main",
        "0", "42", "-1", "3.14", '"hello"', '"José"',
        "{", "}", "(", ")", "[", "]", ":", ",", ".", "->", "=>", "?", "??", "!", "==", "!=",
        "+", "-", "*", "/", "%", "..", "..=", "=", "\n", " ",
    ]
    length = rng.randint(5, 45)
    chosen: List[str] = []
    for _ in range(length):
        chosen.append(rng.choice(fragments))
    return " ".join(chosen)


def run_fuzz_suite(fuzz_count: int = 200, base_seed: int = 9000) -> bool:
    crashes = 0
    for offset in range(fuzz_count):
        seed = base_seed + offset
        fuzz_code = generate_fuzz_input(seed)
        label = f"<fuzz_seed_{seed}>"
        try:
            tokens = Lexer(fuzz_code, file=label).tokenize()
            if tokens:
                ast = Parser(file=label).parse(fuzz_code)
                Formatter().format(ast)
                TypeChecker(file=label).check(ast)
        except WError:
            # Expected diagnostic rejection on invalid fuzz inputs
            pass
        except Exception as exc:
            crashes += 1
            print(f"  [FUZZ CRASH] seed={seed} raised unhandled {type(exc).__name__}: {exc}")
            print(f"  Input: {fuzz_code!r}")

    passed = fuzz_count - crashes
    print(f"Compiler Fuzz Suite: {passed}/{fuzz_count} (0 internal tracebacks invariant)")
    return crashes == 0
