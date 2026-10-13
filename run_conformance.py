import glob
import hashlib
import io
import os
import subprocess
import sys
import tempfile
from lexer.Lexer import Lexer
from parser.Parser import Parser
from checker.TypeChecker import TypeChecker
from runtime.Interpreter import Interpreter
from formatter.Formatter import Formatter
from codegen.CCodeGen import CCodeGen
from hir.HirBuilder import HirBuilder
from hir.HirNodes import HirModule
from hir.HirCCodeGen import HirCCodeGen
from test_w1_split_conformance import test_split_conformance
from error.Error import DIAGNOSTIC_CODES, LexerError, ParserError, TypeError, WError
from token.TokenType import TokenType
from node.NodeType import Program


def _check_expected_diag_code(code_text: str, err: WError) -> None:
    assert err.code in DIAGNOSTIC_CODES, f"Invalid diagnostic code {err.code!r}"
    for line in code_text.splitlines():
        s = line.strip()
        if s.startswith("# ERROR:"):
            expected_code = s.split(":", 1)[1].strip()
            assert err.code == expected_code, f"Expected diagnostic code {expected_code}, got {err.code}"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def run_suite() -> None:
    repo_root = os.path.dirname(os.path.realpath(__file__))
    prev_cwd = os.getcwd()
    os.chdir(repo_root)
    try:
        _run_suite_in_repo(repo_root)
    finally:
        os.chdir(prev_cwd)


def _run_suite_in_repo(repo_root: str) -> None:
    print("==================================================")
    print("W Language Conformance Runner (SPEC v0.1)")
    print("==================================================")

    # 1. Lexer Tests
    valid_lexer = "tests/lexer/valid"
    invalid_lexer = "tests/lexer/invalid"

    v_lex_files = sorted([f for f in os.listdir(valid_lexer) if f.endswith(".w")]) if os.path.exists(valid_lexer) else []
    i_lex_files = sorted([f for f in os.listdir(invalid_lexer) if f.endswith(".w")]) if os.path.exists(invalid_lexer) else []

    v_lex_passed = 0
    for f in v_lex_files:
        path = os.path.join(valid_lexer, f)
        with open(path, "r", encoding="utf-8") as stream:
            code = stream.read()
        try:
            tokens = Lexer(code, file=f).tokenize()
            assert len(tokens) > 0 and tokens[-1].type == TokenType.EOF
            v_lex_passed += 1
        except Exception as e:
            print(f"  [LEXER FAIL] {f}: {e}")

    i_lex_passed = 0
    for f in i_lex_files:
        path = os.path.join(invalid_lexer, f)
        with open(path, "r", encoding="utf-8") as stream:
            code = stream.read()
        try:
            Lexer(code, file=f).tokenize()
            print(f"  [LEXER FAIL] {f}: Expected LexerError but succeeded")
        except LexerError as err:
            _check_expected_diag_code(code, err)
            i_lex_passed += 1
        except Exception as e:
            print(f"  [LEXER FAIL] {f}: Unexpected exception {e}")

    print(f"Lexer valid:         {v_lex_passed}/{len(v_lex_files)}")
    print(f"Lexer invalid:       {i_lex_passed}/{len(i_lex_files)}")

    # 2. Parser Tests
    valid_parser = "tests/parser/valid"
    invalid_parser = "tests/parser/invalid"

    v_parse_files = sorted([f for f in os.listdir(valid_parser) if f.endswith(".w")]) if os.path.exists(valid_parser) else []
    i_parse_files = sorted([f for f in os.listdir(invalid_parser) if f.endswith(".w")]) if os.path.exists(invalid_parser) else []

    v_parse_passed = 0
    for f in v_parse_files:
        path = os.path.join(valid_parser, f)
        with open(path, "r", encoding="utf-8") as stream:
            code = stream.read()
        try:
            ast = Parser(file=f).parse(code)
            assert isinstance(ast, Program)
            v_parse_passed += 1
        except Exception as e:
            print(f"  [PARSER FAIL] {f}: {e}")

    i_parse_passed = 0
    for f in i_parse_files:
        path = os.path.join(invalid_parser, f)
        with open(path, "r", encoding="utf-8") as stream:
            code = stream.read()
        try:
            Parser(file=f).parse(code)
            print(f"  [PARSER FAIL] {f}: Expected ParserError but succeeded")
        except ParserError as err:
            _check_expected_diag_code(code, err)
            i_parse_passed += 1
        except Exception as e:
            print(f"  [PARSER FAIL] {f}: Unexpected exception {e}")

    print(f"Parser valid:        {v_parse_passed}/{len(v_parse_files)}")
    print(f"Parser invalid:      {i_parse_passed}/{len(i_parse_files)}")

    # 3. Type Checker Tests
    valid_types = "tests/types/valid"
    invalid_types = "tests/types/invalid"

    v_type_files = sorted([f for f in os.listdir(valid_types) if f.endswith(".w")]) if os.path.exists(valid_types) else []
    i_type_files = sorted([f for f in os.listdir(invalid_types) if f.endswith(".w")]) if os.path.exists(invalid_types) else []

    v_type_passed = 0
    for f in v_type_files:
        path = os.path.join(valid_types, f)
        with open(path, "r", encoding="utf-8") as stream:
            code = stream.read()
        try:
            ast = Parser(file=path).parse(code)
            checker = TypeChecker(file=path)
            checker.check(ast)
            v_type_passed += 1
        except Exception as e:
            print(f"  [TYPE FAIL] {f}: {e}")

    i_type_passed = 0
    for f in i_type_files:
        path = os.path.join(invalid_types, f)
        with open(path, "r", encoding="utf-8") as stream:
            code = stream.read()
        try:
            ast = Parser(file=path).parse(code)
            checker = TypeChecker(file=path)
            checker.check(ast)
            print(f"  [TYPE FAIL] {f}: Expected TypeError but succeeded")
        except TypeError as err:
            _check_expected_diag_code(code, err)
            i_type_passed += 1
        except Exception as e:
            print(f"  [TYPE FAIL] {f}: Unexpected exception {e}")

    print(f"Types valid:         {v_type_passed}/{len(v_type_files)}")
    print(f"Types invalid:       {i_type_passed}/{len(i_type_files)}")

    # 4. Error Handling Tests (tests/errors/)
    err_dir = "tests/errors"
    err_files = sorted([f for f in os.listdir(err_dir) if f.endswith(".w")]) if os.path.exists(err_dir) else []
    err_passed = 0
    for f in err_files:
        path = os.path.join(err_dir, f)
        with open(path, "r", encoding="utf-8") as stream:
            code = stream.read()
        try:
            ast = Parser(file=path).parse(code)
            TypeChecker(file=path).check(ast)
            if f.startswith("valid_"):
                err_passed += 1
            else:
                print(f"  [ERROR SUITE FAIL] {f}: Expected TypeError")
        except TypeError as err:
            if f.startswith("invalid_"):
                _check_expected_diag_code(code, err)
                err_passed += 1
            else:
                print(f"  [ERROR SUITE FAIL] {f}: Unexpected TypeError")
        except Exception as e:
            print(f"  [ERROR SUITE FAIL] {f}: {e}")

    print(f"Error handling:      {err_passed}/{len(err_files)}")

    # 5. Formatter Idempotence Tests
    fmt_files = sorted(glob.glob("tests/formatter/*.w") + glob.glob("tests/runtime/*.w"))
    fmt_passed = 0
    fmt = Formatter()
    for path in fmt_files:
        with open(path, "r", encoding="utf-8") as stream:
            code = stream.read()
        try:
            ast1 = Parser(file=path).parse(code)
            out1 = fmt.format(ast1)
            ast2 = Parser(file=path).parse(out1)
            out2 = fmt.format(ast2)
            assert out1 == out2
            fmt_passed += 1
        except Exception as e:
            print(f"  [FORMATTER FAIL] {path}: {e}")

    print(f"Formatter idempotent:{fmt_passed}/{len(fmt_files)}")

    # 6. Typed HIR Lowering Tests
    hir_files = sorted(glob.glob("tests/runtime/*.w") + glob.glob("examples/*.w"))
    hir_passed = 0
    for path in hir_files:
        with open(path, "r", encoding="utf-8") as stream:
            code = stream.read()
        try:
            ast = Parser(file=path).parse(code)
            checker = TypeChecker(file=path)
            checker.check(ast)
            builder = HirBuilder(checker.interner, file_path=path)
            hir_mod = builder.lower(ast)
            assert isinstance(hir_mod, HirModule)
            hir_passed += 1
        except Exception as e:
            print(f"  [HIR FAIL] {path}: {e}")

    print(f"Typed HIR Lowering:  {hir_passed}/{len(hir_files)}")

    # 7. Runtime Interpreter (W0) Tests
    runtime_dir = "tests/runtime"
    runtime_files = sorted([f for f in os.listdir(runtime_dir) if f.endswith(".w")]) if os.path.exists(runtime_dir) else []
    runtime_passed = 0

    for f in runtime_files:
        path = os.path.join(runtime_dir, f)
        expected_path = os.path.join(runtime_dir, f[:-2] + ".expected")
        with open(path, "r", encoding="utf-8") as stream:
            code = stream.read()

        buf = io.StringIO()
        try:
            ast = Parser(file=path).parse(code)
            checker = TypeChecker(file=path)
            checker.check(ast)
            interp = Interpreter(stdout=buf, file=path)
            interp.interpret(ast)

            actual = buf.getvalue().strip()
            if os.path.exists(expected_path):
                with open(expected_path, "r", encoding="utf-8") as exp_stream:
                    expected = exp_stream.read().strip()
                assert actual == expected, f"Output mismatch: expected {expected!r}, got {actual!r}"

            runtime_passed += 1
        except Exception as e:
            print(f"  [RUNTIME FAIL] {f}: {e}")

    print(f"Runtime execution:   {runtime_passed}/{len(runtime_files)}")

    # 7. Native C99 Backend Tests (W0) & 8. Self-Hosting W1 Stage-2 Suite
    repo_root = os.path.dirname(os.path.abspath(__file__))
    c99_targets = [f for f in runtime_files if os.path.exists(os.path.join(runtime_dir, f[:-2] + ".expected"))]
    c99_passed = 0
    w1_runtime_passed = 0
    bootstrap_ok = False

    use_sanitize = os.environ.get("W_SANITIZE") == "1" or "--sanitize" in sys.argv
    extra_cc_flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"] if use_sanitize else []
    if use_sanitize:
        print("[SANITIZERS ENABLED] Compiling with Clang ASan and UBSan (-fsanitize=address,undefined)")

    with tempfile.TemporaryDirectory() as tmpdir:
        for f in c99_targets:
            path = os.path.join(runtime_dir, f)
            expected_path = os.path.join(runtime_dir, f[:-2] + ".expected")
            with open(path, "r", encoding="utf-8") as stream:
                code = stream.read()
            with open(expected_path, "r", encoding="utf-8") as exp_stream:
                expected = exp_stream.read()

            try:
                ast = Parser(file=path).parse(code)
                c_code = CCodeGen(file=path).generate(ast)
                c_path = os.path.join(tmpdir, f[:-2] + ".c")
                bin_path = os.path.join(tmpdir, f[:-2])
                with open(c_path, "w", encoding="utf-8") as cf:
                    cf.write(c_code)
                comp = subprocess.run(["cc", "-std=c99", f"-I{repo_root}"] + extra_cc_flags + [c_path, "-o", bin_path], capture_output=True, text=True)
                assert comp.returncode == 0, comp.stderr
                run_res = subprocess.run([bin_path], capture_output=True, text=True)
                assert run_res.stdout == expected, f"Expected {expected!r}, got {run_res.stdout!r}"
                c99_passed += 1
            except Exception as e:
                print(f"  [C99 FAIL] {f}: {e}")

        # 8. Self-Hosting Bootstrap Fixed-Point (W0 -> W1 Stage 1 -> W1 Stage 2)
        w1_src_path = os.path.join(repo_root, "selfhost", "w1.w")
        try:
            with open(w1_src_path, "r", encoding="utf-8") as wf:
                w1_src = wf.read()
            w1_ast = Parser(file=w1_src_path).parse(w1_src)
            TypeChecker(file=w1_src_path).check(w1_ast)
            c0_code = CCodeGen(file=w1_src_path).generate(w1_ast)

            c0_path = os.path.join(tmpdir, "compiler0.c")
            c1_path = os.path.join(tmpdir, "compiler1.c")
            c2_path = os.path.join(tmpdir, "compiler2.c")
            s1_bin = os.path.join(tmpdir, "w1_stage1")
            s2_bin = os.path.join(tmpdir, "w1_stage2")

            with open(c0_path, "w", encoding="utf-8") as cf:
                cf.write(c0_code)

            subprocess.run(["cc", "-std=c99", "-O2", f"-I{repo_root}", c0_path, "-o", s1_bin], check=True, capture_output=True)
            subprocess.run([s1_bin, w1_src_path, c1_path], check=True, capture_output=True)
            subprocess.run(["cc", "-std=c99", "-O2", f"-I{repo_root}", c1_path, "-o", s2_bin], check=True, capture_output=True)
            subprocess.run([s2_bin, w1_src_path, c2_path], check=True, capture_output=True)

            h0 = sha256_file(c0_path)
            h1 = sha256_file(c1_path)
            h2 = sha256_file(c2_path)
            assert h0 == h1 == h2, f"Hash mismatch: {h0} vs {h1} vs {h2}"
            bootstrap_ok = True

            # 9. Verify W1 Stage 2 Native Compiler on All Runtime Conformance Programs
            for f in c99_targets:
                path = os.path.join(runtime_dir, f)
                expected_path = os.path.join(runtime_dir, f[:-2] + ".expected")
                with open(expected_path, "r", encoding="utf-8") as exp_stream:
                    expected = exp_stream.read()
                w1_c_path = os.path.join(tmpdir, "w1_" + f[:-2] + ".c")
                w1_bin_path = os.path.join(tmpdir, "w1_" + f[:-2])
                subprocess.run([s2_bin, path, w1_c_path], check=True, capture_output=True, cwd=repo_root)
                subprocess.run(["cc", "-std=c99", f"-I{repo_root}"] + extra_cc_flags + [w1_c_path, "-o", w1_bin_path], check=True, capture_output=True)
                run_res = subprocess.run([w1_bin_path], capture_output=True, text=True, cwd=repo_root)
                assert run_res.stdout == expected
                w1_runtime_passed += 1

            # 10. Verify Showcase Examples (examples/*.w) on W0 Interpreter, W0 C99, and W1 Stage-2 Native
            examples_dir = "examples"
            example_files = sorted([f for f in os.listdir(examples_dir) if f.endswith(".w")]) if os.path.exists(examples_dir) else []
            examples_passed = 0
            for f in example_files:
                ex_path = os.path.join(examples_dir, f)
                exp_path = os.path.join(examples_dir, f[:-2] + ".expected")
                with open(ex_path, "r", encoding="utf-8") as sf:
                    ex_code = sf.read()
                with open(exp_path, "r", encoding="utf-8") as ef:
                    ex_expected = ef.read()

                ex_ast = Parser(file=ex_path).parse(ex_code)
                TypeChecker(file=ex_path).check(ex_ast)
                ex_buf = io.StringIO()
                Interpreter(stdout=ex_buf, file=ex_path).interpret(ex_ast)
                assert ex_buf.getvalue() == ex_expected, f"Interpreter mismatch on {f}"

                ex_c_path = os.path.join(tmpdir, "ex_" + f[:-2] + ".c")
                ex_bin_path = os.path.join(tmpdir, "ex_" + f[:-2])
                subprocess.run([s2_bin, ex_path, ex_c_path], check=True, capture_output=True, cwd=repo_root)
                subprocess.run(["cc", "-std=c99", f"-I{repo_root}", ex_c_path, "-o", ex_bin_path], check=True, capture_output=True)
                ex_res = subprocess.run([ex_bin_path], capture_output=True, text=True, cwd=repo_root)
                assert ex_res.stdout == ex_expected, f"W1 native mismatch on {f}"
                examples_passed += 1
        except Exception as e:
            print(f"  [BOOTSTRAP/W1 FAIL] {e}")
            example_files = []
            examples_passed = 0

    # 11. Typed HIR -> C99 Native Backend (HirCCodeGen)
    hir_c99_passed = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        for f in c99_targets:
            path = os.path.join(runtime_dir, f)
            expected_path = os.path.join(runtime_dir, f[:-2] + ".expected")
            with open(path, "r", encoding="utf-8") as stream:
                code = stream.read()
            with open(expected_path, "r", encoding="utf-8") as exp_stream:
                expected = exp_stream.read()

            try:
                ast = Parser(file=path).parse(code)
                checker = TypeChecker(file=path)
                checker.check(ast)
                builder = HirBuilder(checker.interner, file_path=path)
                hir_mod = builder.lower(ast)
                gen = HirCCodeGen(checker.interner, file_path=path)
                c_code = gen.generate(hir_mod)

                c_path = os.path.join(tmpdir, "hir_" + f[:-2] + ".c")
                bin_path = os.path.join(tmpdir, "hir_" + f[:-2])
                with open(c_path, "w", encoding="utf-8") as cf:
                    cf.write(c_code)
                comp = subprocess.run(["cc", "-std=c99", f"-I{repo_root}"] + extra_cc_flags + [c_path, "-o", bin_path], capture_output=True, text=True)
                assert comp.returncode == 0, comp.stderr
                run_res = subprocess.run([bin_path], capture_output=True, text=True, cwd=repo_root)
                assert run_res.stdout == expected, f"HIR C99 mismatch on {f}: expected {expected!r}, got {run_res.stdout!r}"
                hir_c99_passed += 1
            except Exception as e:
                print(f"  [HIR C99 FAIL] {f}: {e}")

    # 12. Modular W1 Split Conformance
    split_ok = test_split_conformance()

    # Clean temporary files if any
    temp_file = os.path.join(runtime_dir, "temp_file.txt")
    if os.path.exists(temp_file):
        try:
            os.remove(temp_file)
        except OSError:
            pass

    print(f"C99 Native Backend:  {c99_passed}/{len(c99_targets)}")
    print(f"HIR C99 Backend:     {hir_c99_passed}/{len(c99_targets)}")
    print(f"W1 Stage-2 Runtime:  {w1_runtime_passed}/{len(c99_targets)}")
    print(f"W1 Modular Split:    {'1/1 (Loss-less verified)' if split_ok else '0/1'}")
    print(f"Examples E2E Suite:  {examples_passed}/{len(example_files)}")
    print(f"Bootstrap FixedPoint:{'1/1 (SHA256 verified)' if bootstrap_ok else '0/1'}")

    print("==================================================")
    all_ok = (
        v_lex_passed == len(v_lex_files)
        and i_lex_passed == len(i_lex_files)
        and v_parse_passed == len(v_parse_files)
        and i_parse_passed == len(i_parse_files)
        and v_type_passed == len(v_type_files)
        and i_type_passed == len(i_type_files)
        and err_passed == len(err_files)
        and fmt_passed == len(fmt_files)
        and hir_passed == len(hir_files)
        and runtime_passed == len(runtime_files)
        and c99_passed == len(c99_targets)
        and hir_c99_passed == len(c99_targets)
        and w1_runtime_passed == len(c99_targets)
        and split_ok
        and examples_passed == len(example_files)
        and bootstrap_ok
    )

    if all_ok:
        total = (
            v_lex_passed + i_lex_passed + v_parse_passed + i_parse_passed +
            v_type_passed + i_type_passed + err_passed + fmt_passed + hir_passed +
            runtime_passed + c99_passed + hir_c99_passed + w1_runtime_passed +
            examples_passed + 1 + 1
        )
        print(f"ALL {total}/{total} CONFORMANCE, EXAMPLES & SELF-HOSTING TESTS PASSED (100%).")
        sys.exit(0)
    else:
        print("FAILURES DETECTED.")
        sys.exit(1)


if __name__ == "__main__":
    run_suite()
