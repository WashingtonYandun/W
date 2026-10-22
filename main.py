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
from runtime.Values import WysnaUnit
from formatter.Formatter import Formatter
from codegen.CCodeGen import CCodeGen
from hir.HirBuilder import HirBuilder
from hir.HirCCodeGen import HirCCodeGen
from error.Error import WysnaError

from common.Version import WYSNA_VERSION
from common.Platform import cache_lock, compiler_command, executable_name, peak_rss_kb


def get_repo_root() -> str:
    return os.path.dirname(os.path.realpath(__file__))


# Every input that can change the bytes of the stage-2 compiler binary. The hand-written
# runtime header and the selfhost sources are the obvious ones; the Seed frontend, checker
# and C emitter are just as load-bearing because stage 1 is produced by them, and a
# stale binary silently invalidates every `--backend=selfhost` comparison.
SELFHOST_BOOTSTRAP_INPUTS = ("selfhost/compiler.wysna", "runtime/wysna_runtime.h", "runtime/wysna_host.h", "main.py") + tuple(
    os.path.relpath(os.path.join(directory, name), get_repo_root())
    for package in ("lexer", "parser", "node", "checker", "compiler", "codegen", "common", "error", "hir", "mir", "tokens")
    for directory, _, names in os.walk(os.path.join(get_repo_root(), package))
    for name in sorted(names)
    if name.endswith(".py")
)


def _bootstrap_source_mtime(repo_root: str) -> float:
    """Newest modification time across every input to the compiler bootstrap."""
    newest = 0.0
    for relative in SELFHOST_BOOTSTRAP_INPUTS:
        path = os.path.join(repo_root, relative)
        if os.path.exists(path):
            newest = max(newest, os.path.getmtime(path))
    return newest


def ensure_selfhost_compiler_binary(repo_root: str) -> str:
    """Serialize cache rebuilds across independent compiler/test processes."""
    compiler_src_path = os.path.join(repo_root, "selfhost", "compiler.wysna")
    if not os.path.isfile(compiler_src_path):
        from error.Error import TypeError
        raise TypeError("Wysna Compiler bootstrap requires a source checkout", file=compiler_src_path, code="W2013")
    cache_dir = os.path.join(repo_root, ".wysna_cache")
    os.makedirs(cache_dir, exist_ok=True)
    with cache_lock(os.path.join(cache_dir, 'bootstrap.lock')):
        return _ensure_selfhost_compiler_binary_locked(repo_root)


def _ensure_selfhost_compiler_binary_locked(repo_root: str) -> str:
    cache_dir = os.path.join(repo_root, ".wysna_cache")
    os.makedirs(cache_dir, exist_ok=True)
    stage2_bin = os.path.join(cache_dir, executable_name("stage2"))
    compiler_src_path = os.path.join(repo_root, "selfhost", "compiler.wysna")

    needs_rebuild = not os.path.exists(stage2_bin)
    if not needs_rebuild and _bootstrap_source_mtime(repo_root) > os.path.getmtime(stage2_bin):
        needs_rebuild = True

    if not os.path.isfile(compiler_src_path):
        from error.Error import TypeError
        raise TypeError("Wysna Compiler bootstrap requires a source checkout", file=compiler_src_path, code="W2013")
    if needs_rebuild:
        with open(compiler_src_path, "r", encoding="utf-8") as wf:
            compiler_src = wf.read()
        ast = Parser(file=compiler_src_path).parse(compiler_src)
        TypeChecker(file=compiler_src_path).check(ast)
        c0_code = CCodeGen(file=compiler_src_path).generate(ast)

        c0_path = os.path.join(cache_dir, "compiler0.c")
        c1_path = os.path.join(cache_dir, "compiler1.c")
        s1_bin = os.path.join(cache_dir, executable_name("stage1"))

        with open(c0_path, "w", encoding="utf-8") as cf:
            cf.write(c0_code)

        subprocess.run(
            compiler_command() + ["-std=c99", "-O2", f"-I{repo_root}", c0_path, "-o", s1_bin],
            check=True,
            timeout=120,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [s1_bin, compiler_src_path, c1_path],
            check=True,
            timeout=120,
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        subprocess.run(
            compiler_command() + ["-std=c99", "-O2", f"-I{repo_root}", c1_path, "-o", stage2_bin],
            check=True,
            timeout=120,
            capture_output=True,
            text=True,
        )

    return stage2_bin


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
    backend: str = "hir",
    use_selfhost: bool = False,
    use_hir: Optional[bool] = None,
    sanitize: bool = False,
    show_stats: bool = False,
    link_libraries=(),
    show_mir: bool = False,
) -> int:
    try:
        # Resolve legacy flags if passed explicitly
        if use_selfhost:
            backend = "selfhost"
        elif use_hir is False:
            backend = "ast"
        elif use_hir is True:
            backend = "hir"

        import time

        t_start = time.perf_counter()
        lex_ms = parse_ms = check_ms = 0.0
        ast = None
        checker = None
        selfhost_direct = (
            backend == "selfhost"
            and (emit_c_path is not None or build_bin_path is not None)
            and file_name != "<stdin>"
            and not show_tokens
            and not show_ast
            and not fmt_only
            and not check_only
        )

        if selfhost_direct:
            lexer = None
            tokens = []
        else:
            # 1. Lexing
            t_lex0 = time.perf_counter()
            lexer = Lexer(source_code, file=file_name)
            tokens = lexer.tokenize()
            lex_ms = (time.perf_counter() - t_lex0) * 1000.0
        if show_tokens:
            for t in tokens:
                print(f"  {t}")
            if not show_ast and not check_only and emit_c_path is None and build_bin_path is None:
                return 0

        if not selfhost_direct:
            # 2. Parsing
            t_parse0 = time.perf_counter()
            parser = Parser(file=file_name)
            ast = parser.parse(source_code, tokens=tokens, recover=check_only)
            parse_ms = (time.perf_counter() - t_parse0) * 1000.0
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

        if not selfhost_direct:
            # 3. Static Type Checking
            t_check0 = time.perf_counter()
            checker = TypeChecker(file=file_name)
            checker.check(ast)
            check_ms = (time.perf_counter() - t_check0) * 1000.0

        if show_mir:
            from mir.Lowering import Lowering
            from mir.Nodes import dump
            module = HirBuilder(checker.interner, file_path=file_name).lower(ast)
            print(dump(Lowering(checker.interner, file_name).lower(module)), end="")
            return 0

        if check_only:
            if show_stats:
                stat_obj = {
                    "status": "ok",
                    "file": file_name,
                    "telemetry": {
                        "monomorphization": checker.telemetry.to_dict(),
                        "timing_ms": {
                            "lex": round(lex_ms, 2),
                            "parse": round(parse_ms, 2),
                            "check": round(check_ms, 2),
                            "total": round((time.perf_counter() - t_start) * 1000.0, 2),
                        },
                        "peak_rss_kb": peak_rss_kb(),
                    }
                }
                print(json.dumps(stat_obj, indent=2))
            elif json_diagnostics:
                print(json.dumps({"status": "ok", "file": file_name, "diagnostics": []}, indent=2))
            else:
                print(f"[OK] Check passed for {file_name}")
            return 0

        # 4. C99 Code Generation / Native Build
        if emit_c_path is not None or build_bin_path is not None:
            repo_root = get_repo_root()
            codegen_inst = None
            hir_ms = None
            if backend == "selfhost" and file_name != "<stdin>":
                selfhost_bin = ensure_selfhost_compiler_binary(repo_root)
                abs_input = os.path.abspath(file_name)
                input_dir = os.path.dirname(abs_input) or os.getcwd()
                with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False, encoding="utf-8") as tmp_selfhost_c:
                    tmp_selfhost_c_path = tmp_selfhost_c.name
                try:
                    t_selfhost0 = time.perf_counter()
                    selfhost_proc = subprocess.run(
                        [selfhost_bin, abs_input, tmp_selfhost_c_path],
                        capture_output=True,
                        text=True,
                        cwd=input_dir,
                        timeout=120,
                    )
                    codegen_ms = (time.perf_counter() - t_selfhost0) * 1000.0
                    if selfhost_proc.returncode != 0:
                        print(f"[Wysna Compiler Error]\n{selfhost_proc.stderr}", file=sys.stderr)
                        return 1
                    with open(tmp_selfhost_c_path, "r", encoding="utf-8") as cf:
                        c_code = cf.read()
                finally:
                    if os.path.exists(tmp_selfhost_c_path):
                        os.remove(tmp_selfhost_c_path)
            elif backend == "ast":
                t_ast0 = time.perf_counter()
                codegen_inst = CCodeGen(file=file_name)
                c_code = codegen_inst.generate(ast)
                codegen_ms = (time.perf_counter() - t_ast0) * 1000.0
            else:
                # Default C06 backend: Typed HIR -> HirCCodeGen -> C99
                t_hir0 = time.perf_counter()
                builder = HirBuilder(checker.interner, file_path=file_name)
                hir_mod = builder.lower(ast)
                hir_ms = (time.perf_counter() - t_hir0) * 1000.0

                t_cg0 = time.perf_counter()
                codegen_inst = HirCCodeGen(checker.interner, file_path=file_name)
                c_code = codegen_inst.generate(hir_mod)
                codegen_ms = (time.perf_counter() - t_cg0) * 1000.0

            c_compile_ms = link_ms = 0.0
            def report_codegen_stats():
                if not show_stats:
                    return
                stat_obj = {
                    "status": "ok",
                    "file": file_name,
                    "telemetry": {
                        "monomorphization": checker.telemetry.to_dict() if checker is not None else None,
                        "codegen": codegen_inst.telemetry.to_dict() if codegen_inst else None,
                        "timing_ms": {
                            "lex": round(lex_ms, 2),
                            "parse": round(parse_ms, 2),
                            "check": round(check_ms, 2),
                            "hir": round(hir_ms, 2) if hir_ms is not None else None,
                            "codegen": round(codegen_ms, 2),
                            "mir": round(getattr(codegen_inst, 'phase_ms', {}).get('mir', 0), 2),
                            "c_emit": round(getattr(codegen_inst, 'phase_ms', {}).get('c_emit', 0), 2),
                            "c_compile": round(c_compile_ms, 2),
                            "link": round(link_ms, 2),
                            "total": round((time.perf_counter() - t_start) * 1000.0, 2),
                        },
                        "peak_rss_kb": peak_rss_kb(),
                    }
                }
                print(json.dumps(stat_obj, indent=2), file=sys.stderr)

            if emit_c_path is not None:
                with open(emit_c_path, "w", encoding="utf-8") as f:
                    f.write(c_code)
                if build_bin_path is None:
                    report_codegen_stats()
                    return 0

            if build_bin_path is not None:
                with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False, encoding="utf-8") as tmp_c:
                    tmp_c.write(c_code)
                    tmp_c_path = tmp_c.name
                try:
                    san_flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"] if sanitize else []
                    build_bin_path = executable_name(build_bin_path)
                    object_path = tmp_c_path + ('.obj' if os.name == 'nt' else '.o')
                    source_objects = {library: object_path + '.' + str(index) + ('.obj' if os.name == 'nt' else '.o')
                                      for index, library in enumerate(link_libraries)
                                      if library.lower().endswith('.c') and os.path.isfile(library)}
                    base = compiler_command() + ["-std=c99", "-O2", f"-I{repo_root}"] + san_flags
                    started = time.perf_counter()
                    for c_source, c_object in [(tmp_c_path, object_path)] + list(source_objects.items()):
                        proc = subprocess.run(base + ['-c', c_source, '-o', c_object],
                                              capture_output=True, text=True, timeout=120)
                        if proc.returncode != 0:
                            print(f"[C Compiler Error]\n{proc.stderr}", file=sys.stderr)
                            return 1
                    c_compile_ms = (time.perf_counter() - started) * 1000
                    libraries = [flag for library in link_libraries for flag in
                                 [source_objects[library] if library in source_objects else
                                  library if '/' in library or '\\' in library else '-l' + library]]
                    started = time.perf_counter()
                    proc = subprocess.run(base + [object_path, '-o', build_bin_path] + libraries,
                                          capture_output=True, text=True, timeout=120)
                    link_ms = (time.perf_counter() - started) * 1000
                    if proc.returncode != 0:
                        print(f"[C Linker Error]\n{proc.stderr}", file=sys.stderr)
                        return 1
                finally:
                    if os.path.exists(tmp_c_path):
                        os.remove(tmp_c_path)
                    if 'object_path' in locals() and os.path.exists(object_path):
                        os.remove(object_path)
                    for c_object in locals().get('source_objects', {}).values():
                        if os.path.exists(c_object):
                            os.remove(c_object)
                report_codegen_stats()
                return 0

        # 5. Runtime Interpretation
        if show_stats:
            print(json.dumps({
                "status": "ok",
                "file": file_name,
                "telemetry": {
                    "monomorphization": checker.telemetry.to_dict(),
                    "timing_ms": {
                        "lex": round(lex_ms, 2),
                        "parse": round(parse_ms, 2),
                        "check": round(check_ms, 2),
                        "total": round((time.perf_counter() - t_start) * 1000.0, 2),
                    },
                    "peak_rss_kb": peak_rss_kb(),
                }
            }, indent=2), file=sys.stderr)
        interp = Interpreter(file=file_name)
        interp.foreign_libraries = link_libraries
        res = interp.interpret(ast)

        if not isinstance(res, WysnaUnit) and file_name == "<stdin>":
            print(res)

        return 0

    except WysnaError as err:
        if json_diagnostics:
            print(json.dumps(err.to_dict(), indent=2))
        else:
            for diagnostic in getattr(err, 'diagnostics', (err,)):
                print(str(diagnostic), file=sys.stderr)
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
    print(f"Wysna REPL v{WYSNA_VERSION} (Type 'exit' to quit)")
    print("==================================================")

    parser = Parser(file="<repl>")
    checker = TypeChecker(file="<repl>")
    interp = Interpreter(file="<repl>")

    while True:
        try:
            line = input("wysna> ")
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
            if not isinstance(res, WysnaUnit):
                print(res)
        except WysnaError as err:
            print(str(err))
        except Exception as exc:
            print(f"Error: {exc}")


def print_help(prog: Optional[str] = None) -> None:
    if prog is None:
        prog = "wysna"
    print(f"Wysna Language Compiler & Toolchain v{WYSNA_VERSION}")
    print("Usage:")
    print(f"  {prog} lsp                                       # LSP over stdio")
    print(f"  {prog} repl                                    # Start interactive REPL")
    print(f"  {prog} [run] [--stats] <file.wysna>            # Execute Wysna source file (Seed interpreter)")
    print(f"  {prog} check [--json] [--stats] <file.wysna>   # Static typecheck without execution")
    print(f"  {prog} fmt [--write] <file.wysna>              # Canonical deterministic formatter")
    print(f"  {prog} ast [--json] <file.wysna>               # Emit canonical JSON AST (v0.1)")
    print(f"  {prog} mir <file.wysna>                        # Emit verified MIR as JSON")
    print(f"  {prog} tokens <file.wysna>                     # Emit lexical token stream")
    print(f"  {prog} emit-c [--backend=hir|ast|selfhost] [--stats] <file.wysna> [-o <out.c>] # Transpile Wysna source to C99 (default: hir)")
    print(f"  {prog} build [--backend=hir|ast|selfhost] [--stats] <file.wysna> [-o <bin>]    # Compile Wysna source to native binary (default: hir)")
    print(f"  {prog} test [--differential [N]] [--fuzz [N]]            # Run conformance, differential, or fuzz suite")
    print(f"  {prog} bench [--update-baseline]                         # Run Seed/Compiler performance benchmark harness")
    print(f"  {prog} version                                           # Show compiler version")


def main() -> None:
    prog = "wysna"
    args = sys.argv[1:]
    if args == ["lsp"]:
        from tooling.LanguageServer import serve
        serve()
        return
    show_tokens = False
    show_ast = False
    check_only = False
    json_diagnostics = False
    show_stats = False
    fmt_only = False
    fmt_write = False
    backend = "hir"
    use_selfhost = False
    use_hir = None
    emit_c_path: Optional[str] = None
    build_bin_path: Optional[str] = None
    show_mir = False
    subcmd: Optional[str] = None
    file_to_run: Optional[str] = None
    sanitize = False
    link_libraries = []

    if args and args[0] in ("run", "check", "fmt", "ast", "mir", "tokens", "emit-c", "build", "test", "bench", "version", "repl"):
        subcmd = args[0]
        args = args[1:]
        if subcmd == "bench":
            if not os.path.isfile(os.path.join(get_repo_root(), "bench", "run_bench.py")):
                print(f"{prog} bench requires a source checkout", file=sys.stderr)
                sys.exit(1)
            update_baseline = "--update-baseline" in args
            repo_root = get_repo_root()
            selfhost_bin = ensure_selfhost_compiler_binary(repo_root)
            from bench.run_bench import run_benchmark_suite
            ok = run_benchmark_suite(repo_root, selfhost_bin, update_baseline=update_baseline)
            sys.exit(0 if ok else 1)
        elif subcmd == "test":
            if args in (["--help"], ["-h"]):
                print_help()
                return
            if not os.path.isdir(os.path.join(get_repo_root(), "tests", "unit")):
                print(f"{prog} test requires a source checkout", file=sys.stderr)
                sys.exit(1)
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
                selfhost_bin = ensure_selfhost_compiler_binary(repo_root)
                from tests.differential.differential_test import run_differential_suite
                ok = run_differential_suite(repo_root, selfhost_bin, generated_count=gen_count, base_seed=base_seed)
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
                if args and ("--sanitize" in args or "-s" in args):
                    os.environ["WYSNA_SANITIZE"] = "1"
                from run_conformance import run_suite
                run_suite()
                return
        elif subcmd == "version":
            print(f"Wysna Language Compiler v{WYSNA_VERSION} (Wysna Seed + Wysna Compiler Self-Hosted C99)")
            return
        elif subcmd == "check":
            check_only = True
        elif subcmd == "fmt":
            fmt_only = True
        elif subcmd == "ast":
            show_ast = True
        elif subcmd == "mir":
            show_mir = True
        elif subcmd == "tokens":
            show_tokens = True

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--tokens", "-t"):
            show_tokens = True
        elif arg == "--ast":
            if subcmd == "ast":
                show_ast = True
            else:
                backend = "ast"
                use_hir = False
        elif arg in ("--check", "-c"):
            check_only = True
        elif arg == "--json":
            json_diagnostics = True
        elif arg in ("--stats", "--metrics"):
            show_stats = True
        elif arg == "--fmt":
            fmt_only = True
        elif arg in ("--write", "-w"):
            fmt_write = True
        elif arg in ("--selfhost", "--backend=selfhost"):
            backend = "selfhost"
            use_selfhost = True
        elif arg in ("--hir", "--backend=hir"):
            backend = "hir"
            use_hir = True
        elif arg in ("--backend=ast",):
            backend = "ast"
            use_hir = False
        elif arg.startswith("--backend="):
            b_val = arg.split("=", 1)[1]
            if b_val in ("hir", "ast", "selfhost"):
                backend = b_val
            else:
                print(f"Error: Unknown backend '{b_val}'. Valid backends: hir, ast, selfhost", file=sys.stderr)
                sys.exit(1)
        elif arg in ("--version", "-v"):
            print(f"Wysna Language Compiler v{WYSNA_VERSION} (Wysna Seed + Wysna Compiler Self-Hosted C99)")
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
        elif arg == "--link-lib":
            i += 1
            if i >= len(args):
                print("--link-lib requires a library name or path", file=sys.stderr)
                sys.exit(1)
            link_libraries.append(args[i])
        elif arg in ("--sanitize", "-s"):
            sanitize = True
        elif arg in ("--help", "-h"):
            print_help()
            sys.exit(0)
        elif not arg.startswith("-"):
            file_to_run = arg
        i += 1

    prog_cmd = "wysna"

    if file_to_run:
        if file_to_run.endswith(".w"):
            print(f"error: '.w' files are no longer supported. Rename '{file_to_run}' to '{file_to_run[:-2]}.wysna'", file=sys.stderr)
            sys.exit(1)

        # Resolve file with extension fallback if omitted
        if not os.path.isfile(file_to_run) and os.path.isfile(file_to_run + ".wysna"):
            file_to_run = file_to_run + ".wysna"

        def _strip_src_ext(p: str) -> str:
            if p.endswith(".wysna"):
                return p[:-6]
            return p

        if subcmd == "emit-c" and emit_c_path is None:
            emit_c_path = _strip_src_ext(file_to_run) + ".c"
        elif subcmd == "build" and build_bin_path is None:
            build_bin_path = _strip_src_ext(file_to_run) if file_to_run.endswith(".wysna") else file_to_run + ".bin"

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
            show_mir=show_mir,
            json_diagnostics=json_diagnostics,
            fmt_only=fmt_only,
            fmt_write=fmt_write,
            emit_c_path=emit_c_path,
            build_bin_path=build_bin_path,
            backend=backend,
            use_selfhost=use_selfhost,
            use_hir=use_hir,
            sanitize=sanitize,
            show_stats=show_stats,
            link_libraries=link_libraries,
        )
        sys.exit(code)

    # No file argument. Dropping into the REPL silently made `w check` in a Makefile exit
    # 0 without checking anything, so the REPL now needs to be asked for explicitly and
    # every other subcommand is a usage error.
    if subcmd is None or subcmd == "repl":
        repl(show_tokens=show_tokens, show_ast=show_ast)
        return
    print(f"{prog_cmd} {subcmd}: no input file given", file=sys.stderr)
    print(f"usage: {prog_cmd} {subcmd} <file.wysna> [options]", file=sys.stderr)
    print(f"       {prog_cmd} repl        # start the interactive REPL", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
