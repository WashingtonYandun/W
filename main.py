import json
import os
import subprocess
import sys
import tempfile
from typing import Optional
from lexer.Lexer import Lexer
from parser.Parser import Parser
from checker.TypeChecker import TypeChecker
from runtime.Interpreter import Interpreter
from runtime.Values import WUnit
from formatter.Formatter import Formatter
from codegen.CCodeGen import CCodeGen
from error.Error import WError

W_VERSION = "0.1.3"


def get_repo_root() -> str:
    return os.path.dirname(os.path.realpath(__file__))


def ensure_selfhost_w1_binary(repo_root: str) -> str:
    cache_dir = os.path.join(repo_root, ".w_cache")
    os.makedirs(cache_dir, exist_ok=True)
    w1_bin = os.path.join(cache_dir, "w1_stage2")
    w1_src_path = os.path.join(repo_root, "selfhost", "w1.w")
    rt_hdr_path = os.path.join(repo_root, "runtime", "w_runtime.h")

    needs_rebuild = not os.path.exists(w1_bin)
    if not needs_rebuild:
        bin_mtime = os.path.getmtime(w1_bin)
        src_mtime = max(os.path.getmtime(w1_src_path), os.path.getmtime(rt_hdr_path))
        if src_mtime > bin_mtime:
            needs_rebuild = True

    if needs_rebuild:
        with open(w1_src_path, "r", encoding="utf-8") as wf:
            w1_src = wf.read()
        w1_ast = Parser(file=w1_src_path).parse(w1_src)
        TypeChecker(file=w1_src_path).check(w1_ast)
        c0_code = CCodeGen(file=w1_src_path).generate(w1_ast)

        c0_path = os.path.join(cache_dir, "compiler0.c")
        c1_path = os.path.join(cache_dir, "compiler1.c")
        s1_bin = os.path.join(cache_dir, "w1_stage1")

        with open(c0_path, "w", encoding="utf-8") as cf:
            cf.write(c0_code)

        subprocess.run(
            ["cc", "-std=c99", "-O2", f"-I{repo_root}", c0_path, "-o", s1_bin],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [s1_bin, w1_src_path, c1_path],
            check=True,
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        subprocess.run(
            ["cc", "-std=c99", "-O2", f"-I{repo_root}", c1_path, "-o", w1_bin],
            check=True,
            capture_output=True,
            text=True,
        )

    return w1_bin


def run_pipeline(
    source_code: str,
    file_name: str = "<stdin>",
    check_only: bool = False,
    show_tokens: bool = False,
    show_ast: bool = False,
    json_diagnostics: bool = False,
    fmt_only: bool = False,
    fmt_write: bool = False,
    emit_c_path: Optional[str] = None,
    build_bin_path: Optional[str] = None,
    use_selfhost: bool = False,
) -> int:
    try:
        # 1. Lexing
        lexer = Lexer(source_code, file=file_name)
        tokens = lexer.tokenize()
        if show_tokens:
            for t in tokens:
                print(f"  {t}")
            if not show_ast and not check_only and emit_c_path is None and build_bin_path is None:
                return 0

        # 2. Parsing
        parser = Parser(file=file_name)
        ast = parser.parse(source_code)
        if show_ast:
            print(json.dumps(ast.to_dict(), indent=2))
            if not check_only and emit_c_path is None and build_bin_path is None:
                return 0

        if fmt_only:
            formatted = Formatter().format(ast)
            if fmt_write and file_name != "<stdin>":
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(formatted)
            else:
                print(formatted, end="")
            return 0

        # 3. Static Type Checking
        checker = TypeChecker(file=file_name)
        checker.check(ast)

        if check_only:
            if json_diagnostics:
                print(json.dumps({"status": "ok", "file": file_name, "diagnostics": []}, indent=2))
            else:
                print(f"[OK] Check passed for {file_name}")
            return 0

        # 4. C99 Code Generation / Native Build
        if emit_c_path is not None or build_bin_path is not None:
            repo_root = get_repo_root()
            if use_selfhost and file_name != "<stdin>":
                w1_bin = ensure_selfhost_w1_binary(repo_root)
                abs_input = os.path.abspath(file_name)
                input_dir = os.path.dirname(abs_input) or os.getcwd()
                with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False, encoding="utf-8") as tmp_w1_c:
                    tmp_w1_c_path = tmp_w1_c.name
                try:
                    w1_proc = subprocess.run(
                        [w1_bin, abs_input, tmp_w1_c_path],
                        capture_output=True,
                        text=True,
                        cwd=input_dir,
                    )
                    if w1_proc.returncode != 0:
                        print(f"[W1 Self-Hosted Compiler Error]\n{w1_proc.stderr}", file=sys.stderr)
                        return 1
                    with open(tmp_w1_c_path, "r", encoding="utf-8") as cf:
                        c_code = cf.read()
                finally:
                    if os.path.exists(tmp_w1_c_path):
                        os.remove(tmp_w1_c_path)
            else:
                c_code = CCodeGen(file=file_name).generate(ast)

            if emit_c_path is not None:
                with open(emit_c_path, "w", encoding="utf-8") as f:
                    f.write(c_code)
                if build_bin_path is None:
                    return 0

            if build_bin_path is not None:
                with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False, encoding="utf-8") as tmp_c:
                    tmp_c.write(c_code)
                    tmp_c_path = tmp_c.name
                try:
                    cmd = ["cc", "-std=c99", "-O2", f"-I{repo_root}", tmp_c_path, "-o", build_bin_path]
                    proc = subprocess.run(cmd, capture_output=True, text=True)
                    if proc.returncode != 0:
                        print(f"[C Compiler Error]\n{proc.stderr}", file=sys.stderr)
                        return 1
                finally:
                    if os.path.exists(tmp_c_path):
                        os.remove(tmp_c_path)
                return 0

        # 5. Runtime Interpretation
        interp = Interpreter(file=file_name)
        res = interp.interpret(ast)

        if not isinstance(res, WUnit) and file_name == "<stdin>":
            print(res)

        return 0

    except WError as err:
        if json_diagnostics:
            print(json.dumps(err.to_dict(), indent=2))
        else:
            print(str(err), file=sys.stderr)
        return 1
    except Exception as exc:
        if json_diagnostics:
            err_dict = {
                "code": "W9999",
                "severity": "error",
                "stage": "internal",
                "message": str(exc),
                "file": file_name,
                "line": 1,
                "column": 1,
                "span": {
                    "file": file_name,
                    "line": 1,
                    "column": 1,
                },
            }
            print(json.dumps(err_dict, indent=2))
        else:
            print(f"[Internal Error] {exc}", file=sys.stderr)
        return 1


def repl(show_tokens: bool = False, show_ast: bool = False) -> None:
    print("==================================================")
    print(f"W Language REPL v{W_VERSION} (Type 'exit' to quit)")
    print("==================================================")

    parser = Parser(file="<repl>")
    checker = TypeChecker(file="<repl>")
    interp = Interpreter(file="<repl>")

    while True:
        try:
            line = input("w> ")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        line = line.strip()
        if not line:
            continue
        if line == "exit":
            break

        try:
            ast = parser.parse(line)
            if show_ast:
                print(json.dumps(ast.to_dict(), indent=2))

            checker.check(ast)
            res = interp.interpret(ast)
            if not isinstance(res, WUnit):
                print(res)
        except WError as err:
            print(str(err))
        except Exception as exc:
            print(f"Error: {exc}")


def print_help() -> None:
    print(f"W Language Compiler & Toolchain v{W_VERSION}")
    print("Usage:")
    print("  w                                           # Start interactive REPL")
    print("  w [run] <file.w>                            # Execute W source file (W0 interpreter)")
    print("  w check [--json] <file.w>                   # Static typecheck without execution")
    print("  w fmt [--write] <file.w>                    # Canonical deterministic formatter")
    print("  w ast [--json] <file.w>                     # Emit canonical JSON AST (v0.1)")
    print("  w tokens <file.w>                           # Emit lexical token stream")
    print("  w emit-c [--selfhost] <file.w> [-o <out.c>] # Transpile W source to C99")
    print("  w build [--selfhost] <file.w> [-o <bin>]    # Compile W source to native binary")
    print("  w test [--differential [N]] [--fuzz [N]]    # Run conformance, differential, or fuzz suite")
    print("  w bench [--update-baseline]                 # Run W0/W1 performance benchmark harness")
    print("  w version                                   # Show compiler version")


def main() -> None:
    args = sys.argv[1:]
    show_tokens = False
    show_ast = False
    check_only = False
    json_diagnostics = False
    fmt_only = False
    fmt_write = False
    use_selfhost = False
    emit_c_path: Optional[str] = None
    build_bin_path: Optional[str] = None
    subcmd: Optional[str] = None
    file_to_run: Optional[str] = None

    if args and args[0] in ("run", "check", "fmt", "ast", "tokens", "emit-c", "build", "test", "bench", "version"):
        subcmd = args[0]
        args = args[1:]
        if subcmd == "bench":
            update_baseline = "--update-baseline" in args
            repo_root = get_repo_root()
            w1_bin = ensure_selfhost_w1_binary(repo_root)
            from bench.run_bench import run_benchmark_suite
            ok = run_benchmark_suite(repo_root, w1_bin, update_baseline=update_baseline)
            sys.exit(0 if ok else 1)
        elif subcmd == "test":
            if args and args[0] == "--differential":
                gen_count = 25
                base_seed = 1000
                idx = 1
                while idx < len(args):
                    if args[idx] == "--seed" and idx + 1 < len(args) and args[idx + 1].isdigit():
                        base_seed = int(args[idx + 1])
                        idx += 2
                    elif args[idx].isdigit():
                        gen_count = int(args[idx])
                        idx += 1
                    else:
                        idx += 1
                repo_root = get_repo_root()
                w1_bin = ensure_selfhost_w1_binary(repo_root)
                from tests.differential.differential_test import run_differential_suite
                ok = run_differential_suite(repo_root, w1_bin, generated_count=gen_count, base_seed=base_seed)
                sys.exit(0 if ok else 1)
            elif args and args[0] == "--fuzz":
                fuzz_count = 200
                base_seed = 9000
                idx = 1
                while idx < len(args):
                    if args[idx] == "--seed" and idx + 1 < len(args) and args[idx + 1].isdigit():
                        base_seed = int(args[idx + 1])
                        idx += 2
                    elif args[idx].isdigit():
                        fuzz_count = int(args[idx])
                        idx += 1
                    else:
                        idx += 1
                repo_root = get_repo_root()
                from tests.differential.differential_test import run_fuzz_suite
                ok = run_fuzz_suite(fuzz_count=fuzz_count, base_seed=base_seed, repo_root=repo_root)
                sys.exit(0 if ok else 1)
            else:
                from run_conformance import run_suite
                run_suite()
                return
        elif subcmd == "version":
            print(f"W Language Compiler v{W_VERSION} (W0 + W1 Self-Hosted C99)")
            return
        elif subcmd == "check":
            check_only = True
        elif subcmd == "fmt":
            fmt_only = True
        elif subcmd == "ast":
            show_ast = True
        elif subcmd == "tokens":
            show_tokens = True

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--tokens", "-t"):
            show_tokens = True
        elif arg == "--ast":
            show_ast = True
        elif arg in ("--check", "-c"):
            check_only = True
        elif arg == "--json":
            json_diagnostics = True
        elif arg == "--fmt":
            fmt_only = True
        elif arg in ("--write", "-w"):
            fmt_write = True
        elif arg == "--selfhost":
            use_selfhost = True
        elif arg in ("--version", "-v"):
            print(f"W Language Compiler v{W_VERSION} (W0 + W1 Self-Hosted C99)")
            sys.exit(0)
        elif arg == "--emit-c":
            i += 1
            if i < len(args):
                emit_c_path = args[i]
        elif arg == "--build":
            i += 1
            if i < len(args):
                build_bin_path = args[i]
        elif arg == "-o":
            i += 1
            if i < len(args):
                if subcmd == "emit-c":
                    emit_c_path = args[i]
                elif subcmd == "build":
                    build_bin_path = args[i]
                else:
                    build_bin_path = args[i]
        elif arg in ("--help", "-h"):
            print_help()
            sys.exit(0)
        elif not arg.startswith("-"):
            file_to_run = arg
        i += 1

    if file_to_run:
        if subcmd == "emit-c" and emit_c_path is None:
            emit_c_path = file_to_run[:-2] + ".c" if file_to_run.endswith(".w") else file_to_run + ".c"
        elif subcmd == "build" and build_bin_path is None:
            build_bin_path = file_to_run[:-2] if file_to_run.endswith(".w") else file_to_run + ".bin"

        try:
            with open(file_to_run, "r", encoding="utf-8") as f:
                source = f.read()
        except OSError as e:
            print(f"Error reading file '{file_to_run}': {e}", file=sys.stderr)
            sys.exit(1)

        code = run_pipeline(
            source_code=source,
            file_name=file_to_run,
            check_only=check_only,
            show_tokens=show_tokens,
            show_ast=show_ast,
            json_diagnostics=json_diagnostics,
            fmt_only=fmt_only,
            fmt_write=fmt_write,
            emit_c_path=emit_c_path,
            build_bin_path=build_bin_path,
            use_selfhost=use_selfhost,
        )
        sys.exit(code)
    else:
        repl(show_tokens=show_tokens, show_ast=show_ast)


if __name__ == "__main__":
    main()
