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
            c_code = CCodeGen(file=file_name).generate(ast)
            if emit_c_path is not None:
                with open(emit_c_path, "w", encoding="utf-8") as f:
                    f.write(c_code)
                if build_bin_path is None:
                    return 0

            if build_bin_path is not None:
                repo_root = os.path.dirname(os.path.abspath(__file__))
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
                "code": "E999",
                "file": file_name,
                "line": 1,
                "column": 1,
                "message": str(exc)
            }
            print(json.dumps(err_dict, indent=2))
        else:
            print(f"[Internal Error] {exc}", file=sys.stderr)
        return 1


def repl(show_tokens: bool = False, show_ast: bool = False) -> None:
    print("==================================================")
    print("W Language REPL v0.1 (Type 'exit' to quit)")
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
    print("W Language Compiler & Toolchain v0.1")
    print("Usage:")
    print("  ./w                              # Start interactive REPL")
    print("  ./w [run] <file.w>               # Execute W source file")
    print("  ./w check [--json] <file.w>      # Static typecheck without execution")
    print("  ./w fmt [--write] <file.w>       # Canonical deterministic formatter")
    print("  ./w ast [--json] <file.w>        # Emit canonical JSON AST (v0.1)")
    print("  ./w tokens <file.w>              # Emit lexical token stream")
    print("  ./w emit-c <file.w> -o <out.c>   # Transpile W source to C99")
    print("  ./w build <file.w> -o <bin>      # Compile W source to native binary")
    print("  ./w test                         # Run full conformance & bootstrap suite")


def main() -> None:
    args = sys.argv[1:]
    show_tokens = False
    show_ast = False
    check_only = False
    json_diagnostics = False
    fmt_only = False
    fmt_write = False
    emit_c_path: Optional[str] = None
    build_bin_path: Optional[str] = None
    subcmd: Optional[str] = None
    file_to_run: Optional[str] = None

    if args and args[0] in ("run", "check", "fmt", "ast", "tokens", "emit-c", "build", "test"):
        subcmd = args[0]
        args = args[1:]
        if subcmd == "test":
            from run_conformance import run_suite
            run_suite()
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
        )
        sys.exit(code)
    else:
        repl(show_tokens=show_tokens, show_ast=show_ast)


if __name__ == "__main__":
    main()
