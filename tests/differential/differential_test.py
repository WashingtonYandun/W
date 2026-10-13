import glob
import io
import os
import random
import subprocess
import sys
import tempfile
from typing import List, Optional, Tuple
from lexer.Lexer import Lexer
from parser.Parser import Parser
from checker.TypeChecker import TypeChecker
from runtime.Interpreter import Interpreter
from formatter.Formatter import Formatter
from codegen.CCodeGen import CCodeGen
from error.Error import DIAGNOSTIC_CODES, WError, WRuntimeError


def extract_diag_code(stderr_text: str) -> str:
    s = stderr_text.strip()
    if s.startswith("[") and "]" in s:
        candidate = s[1:s.index("]")]
        if candidate in DIAGNOSTIC_CODES:
            return candidate
    return ""


class EngineResult:
    def __init__(
        self,
        engine: str,
        stdout: str,
        stderr: str,
        exit_code: int,
        compile_ok: bool,
        runtime_ok: bool,
        diag_code: str = "",
    ) -> None:
        self.engine = engine
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.compile_ok = compile_ok
        self.runtime_ok = runtime_ok
        self.diag_code = diag_code or extract_diag_code(stderr)


def run_w0_interpreter(source_code: str, file_name: str) -> EngineResult:
    old_stdout = sys.stdout
    buf_out = io.StringIO()
    sys.stdout = buf_out
    try:
        ast = Parser(file=file_name).parse(source_code)
        TypeChecker(file=file_name).check(ast)
    except WError as err:
        sys.stdout = old_stdout
        return EngineResult(
            engine="W0_Interpreter",
            stdout="",
            stderr=str(err),
            exit_code=1,
            compile_ok=False,
            runtime_ok=False,
            diag_code=err.code,
        )
    try:
        Interpreter(file=file_name).interpret(ast)
        return EngineResult(
            engine="W0_Interpreter",
            stdout=buf_out.getvalue(),
            stderr="",
            exit_code=0,
            compile_ok=True,
            runtime_ok=True,
        )
    except WRuntimeError as rerr:
        return EngineResult(
            engine="W0_Interpreter",
            stdout=buf_out.getvalue(),
            stderr=str(rerr),
            exit_code=1,
            compile_ok=True,
            runtime_ok=False,
            diag_code=rerr.code,
        )
    except WError as err:
        return EngineResult(
            engine="W0_Interpreter",
            stdout=buf_out.getvalue(),
            stderr=str(err),
            exit_code=1,
            compile_ok=False,
            runtime_ok=False,
            diag_code=err.code,
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
            compile_ok=False,
            runtime_ok=False,
            diag_code=err.code,
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
            compile_ok=False,
            runtime_ok=False,
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
        compile_ok=True,
        runtime_ok=(exec_proc.returncode == 0),
        diag_code=extract_diag_code(exec_proc.stderr),
    )


def run_w1_c99_native(source_code: str, file_name: str, w1_bin: str, repo_root: str, work_dir: str) -> EngineResult:
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
            compile_ok=False,
            runtime_ok=False,
            diag_code=extract_diag_code(w1_comp.stderr),
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
            compile_ok=False,
            runtime_ok=False,
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
        compile_ok=True,
        runtime_ok=(exec_proc.returncode == 0),
        diag_code=extract_diag_code(exec_proc.stderr),
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
    res_w1_c = run_w1_c99_native(source_code, label, w1_bin, repo_root, work_dir)

    if (
        res_interp.compile_ok != res_w0_c.compile_ok
        or res_interp.compile_ok != res_w1_c.compile_ok
    ):
        msg = (
            f"compile_ok mismatch on {label}:\n"
            f"  W0 Interp: compile_ok={res_interp.compile_ok} ({res_interp.stderr.strip()})\n"
            f"  W0 C99:    compile_ok={res_w0_c.compile_ok} ({res_w0_c.stderr.strip()})\n"
            f"  W1 C99:    compile_ok={res_w1_c.compile_ok} ({res_w1_c.stderr.strip()})"
        )
        return False, msg

    if (
        res_interp.runtime_ok != res_w0_c.runtime_ok
        or res_interp.runtime_ok != res_w1_c.runtime_ok
    ):
        msg = (
            f"runtime_ok mismatch on {label}:\n"
            f"  W0 Interp: runtime_ok={res_interp.runtime_ok} ({res_interp.stderr.strip()})\n"
            f"  W0 C99:    runtime_ok={res_w0_c.runtime_ok} ({res_w0_c.stderr.strip()})\n"
            f"  W1 C99:    runtime_ok={res_w1_c.runtime_ok} ({res_w1_c.stderr.strip()})"
        )
        return False, msg

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

    if not res_interp.compile_ok or not res_interp.runtime_ok:
        if (
            not res_interp.diag_code
            or res_interp.diag_code != res_w0_c.diag_code
            or res_interp.diag_code != res_w1_c.diag_code
        ):
            msg = (
                f"Diagnostic code mismatch on {label}:\n"
                f"  W0 Interp: {res_interp.diag_code!r} ({res_interp.stderr.strip()})\n"
                f"  W0 C99:    {res_w0_c.diag_code!r} ({res_w0_c.stderr.strip()})\n"
                f"  W1 C99:    {res_w1_c.diag_code!r} ({res_w1_c.stderr.strip()})"
            )
            return False, msg

    return True, "OK"


def generate_valid_program(seed: int) -> str:
    rng = random.Random(seed)
    a_val = rng.randint(-40, 40)
    b_val = rng.randint(1, 20)
    c_val = rng.randint(-15, 15)
    while_steps = rng.randint(2, 5)
    mode_choice = rng.choice(["Mode.Fast", "Mode.Safe", "Mode.Hybrid"])
    flag_val = "true" if rng.randint(0, 1) == 1 else "false"

    list_elems: List[str] = []
    for _ in range(rng.randint(2, 4)):
        list_elems.append(str(rng.randint(-12, 25)))
    list_literal = "[" + ", ".join(list_elems) + "]"

    lines: List[str] = [
        f"# Generated full-behavior differential program (seed = {seed})",
        "enum Mode {",
        "    Fast",
        "    Safe",
        "    Hybrid",
        "}",
        "",
        "struct Bucket {",
        "    label: str",
        "    nums: list[int]",
        "}",
        "",
        "interface Scorer {",
        "    fn score(x: int) -> int",
        "}",
        "",
        "class BaseScorer implements Scorer {",
        "    public weight: int",
        "    fn init(w: int) {",
        "        this.weight = w",
        "    }",
        "    public fn score(x: int) -> int {",
        "        return x * this.weight",
        "    }",
        "}",
        "",
        "class BonusScorer extends BaseScorer implements Scorer {",
        "    public bonus: int",
        "    fn init(w: int, b: int) {",
        "        super.init(w)",
        "        this.bonus = b",
        "    }",
        "    public fn score(x: int) -> int {",
        "        return x * this.weight + this.bonus",
        "    }",
        "}",
        "",
        "fn maybe_scale(x: int, active: bool) -> int? {",
        "    if active {",
        "        return x * 2",
        "    }",
        "    return none",
        "}",
        "",
        "fn checked_div(n: int, d: int) -> int? {",
        "    if d == 0 {",
        "        return none",
        "    }",
        "    return n / d",
        "}",
        "",
        "fn mode_offset(m: Mode, x: int) -> int {",
        "    match m {",
        "        Mode.Fast => x + 10,",
        "        Mode.Safe => x - 5,",
        "        Mode.Hybrid => x * 2,",
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
        f"    let flag: bool = {flag_val}",
        f"    let mode: Mode = {mode_choice}",
        "    let b1 = Bucket { label: \"orig\", nums: " + list_literal + " }",
        "    let mut b2 = b1",
        "    b2.label = \"mutated\"",
        "    b2.nums.append(a + b)",
        '    print("bucket:", b1.label, len(b1.nums), b2.label, len(b2.nums))',
        "    let matrix = [[1, 2], [3, 4]]",
        "    let mut matrix_copy = matrix",
        "    matrix_copy[0].append(99)",
        '    print("matrix:", len(matrix[0]), len(matrix_copy[0]), matrix_copy[0][2])',
        '    let mut table: dict[str, int] = {"a": a, "b": b}',
        '    let mut table_copy = table',
        '    table_copy["c"] = c',
        '    let got_a = table.get("a") ?? 0',
        '    let got_z = table.get("z") ?? -1',
        '    print("dict:", len(table), len(table_copy), got_a, got_z)',
        "    let mut acc = mode_offset(mode, a)",
        "    let mut step = 0",
        f"    while step < {while_steps} {{",
        "        acc = acc + compute(a + step, b)",
        "        step = step + 1",
        "    }",
        "    for x in b2.nums {",
        "        acc = acc + x",
        "    }",
        "    let opt_v = maybe_scale(b, flag) ?? 7",
        "    let div_v = checked_div(acc, b) ?? 0",
        "    let s1: Scorer = BaseScorer(2)",
        "    let s2: Scorer = BonusScorer(3, c)",
        "    let obj = BonusScorer(2, 5)",
        "    let alias = obj",
        "    alias.bonus = alias.bonus + b",
        '    print("final:", acc, opt_v, div_v, s1.score(b), s2.score(b), obj.bonus, obj == alias)',
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

    invalid_files: List[str] = sorted(
        glob.glob(os.path.join(repo_root, "tests", "*", "invalid", "*.w"))
        + glob.glob(os.path.join(repo_root, "tests", "errors", "invalid_*.w"))
    )

    runtime_panic_cases: List[Tuple[str, str]] = [
        (
            "panic_div_zero.w",
            "fn main() -> unit {\n    let z = 0\n    print(10 / z)\n}\n",
        ),
        (
            "panic_float_div_zero.w",
            "fn main() -> unit {\n    let z = 0.0\n    print(10.0 / z)\n}\n",
        ),
        (
            "panic_index_oob.w",
            "fn main() -> unit {\n    let xs = [1, 2, 3]\n    print(xs[9])\n}\n",
        ),
    ]

    passed_cases = 0
    total_cases = len(case_files) + len(runtime_panic_cases) + len(invalid_files) + generated_count

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

        for label, code in runtime_panic_cases:
            ok, detail = verify_three_way_equivalence(code, label, w1_bin, repo_root, work_dir)
            if ok:
                passed_cases += 1
            else:
                print(f"  [DIFF PANIC FAIL] {label}: {detail}")

        for path in invalid_files:
            rel_label = os.path.relpath(path, repo_root)
            with open(path, "r", encoding="utf-8") as f:
                code = f.read()
            ok, detail = verify_three_way_equivalence(code, rel_label, w1_bin, repo_root, work_dir)
            if ok:
                passed_cases += 1
            else:
                print(f"  [DIFF INVALID FAIL] {rel_label}: {detail}")

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

    print(
        f"Differential Oracle: {passed_cases}/{total_cases} "
        f"(cases={len(case_files)}, panics={len(runtime_panic_cases)}, "
        f"invalid={len(invalid_files)}, generated={generated_count})"
    )
    return passed_cases == total_cases


def generate_fuzz_input(seed: int) -> str:
    rng = random.Random(seed)
    mode = seed % 5
    if mode == 0:
        # Token soup
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
        return " ".join(rng.choice(fragments) for _ in range(length))
    elif mode == 1:
        # Malformed strings, escapes, and numbers
        pieces = [
            'let s = "\\u{110000}"',
            'let s = "\\u{}"',
            'let s = "\\u{ZZZZ}"',
            'let s = "unterminated',
            "let n = 1__000",
            "let n = .5",
            "let n = 12.",
            "let n = 1_.",
            'let c = @',
            'let u = "🚀\\n\\t\\"\\\\"',
        ]
        return "\n".join(rng.choice(pieces) for _ in range(rng.randint(1, 6)))
    elif mode == 2:
        # Deeply nested expressions / parentheses / brackets
        depth = rng.randint(10, 45)
        inner = "1"
        for _ in range(depth):
            wrap = rng.choice(["paren", "list", "unary"])
            if wrap == "paren":
                inner = f"({inner} + 1)"
            elif wrap == "list":
                inner = f"[{inner}]"
            else:
                inner = f"-{inner}"
        return f"fn main() {{\n    let x = {inner}\n}}\n"
    elif mode == 3:
        # Near-valid declarations with subtle semantic/type errors
        snippets = [
            "struct S { a: int, a: str }",
            "enum E { A, A }",
            "class A extends B {} class B extends A {}",
            "interface I { fn f() -> int } class C implements I {}",
            "fn f() -> int { let x = 1 }",
            "fn main() { break }",
            "fn main() { continue }",
            "return 42",
            "fn main() { let x = this }",
            "fn main() { let d = {1.5: 2} }",
            "fn main() { let a = [1, 2]\n a.append(3) }",
            "fn main() { let x: int = \"bad\" }",
        ]
        return "\n".join(rng.sample(snippets, k=rng.randint(1, 3)))
    else:
        # Mutated valid program
        base = generate_valid_program(seed)
        if len(base) > 20:
            pos = rng.randint(0, len(base) - 1)
            inject = rng.choice(["{", "}", "(", ")", "[", "]", "?", "!", "=", ":", ";", "@", '"'])
            return base[:pos] + inject + base[pos:]
        return base


def run_fuzz_suite(
    fuzz_count: int = 200,
    base_seed: int = 9000,
    repo_root: Optional[str] = None,
) -> bool:
    if repo_root is None:
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    failures_dir = os.path.join(repo_root, "tests", "fuzz", "failures")
    os.makedirs(failures_dir, exist_ok=True)

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
                CCodeGen(file=label).generate(ast)
        except WError:
            # Expected structured diagnostic rejection on invalid fuzz inputs
            pass
        except Exception as exc:
            crashes += 1
            fail_path = os.path.join(failures_dir, f"{seed}.w")
            with open(fail_path, "w", encoding="utf-8") as ff:
                ff.write(fuzz_code)
            print(
                f"  [FUZZ CRASH] seed={seed} raised unhandled {type(exc).__name__}: {exc} "
                f"(saved to {fail_path})"
            )

    passed = fuzz_count - crashes
    print(f"Compiler Fuzz Suite: {passed}/{fuzz_count} (base_seed={base_seed}, 0 internal tracebacks invariant)")
    return crashes == 0
