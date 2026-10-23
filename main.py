import json
import os
import subprocess
import sys
from typing import Optional
from lexer.Lexer import Lexer
from parser.Parser import Parser
from checker.TypeChecker import TypeChecker
from runtime.Interpreter import Interpreter
from runtime.ExecutionContext import ExecutionContext
from runtime.Values import WysnaUnit
from formatter.Formatter import Formatter
from compiler.CompilerService import CompilerService
from compiler.NativeToolchain import NativeCompilationError, NativeToolchain
from error.Error import WysnaError
from tooling.ToolResult import (
    artifact_file,
    artifact_inline,
    diagnostic_from_error,
    diagnostic_record,
    tool_result,
    write_tool_result,
    write_tool_result_atomic,
)

from common.Version import WYSNA_VERSION
from common.Platform import cache_lock, compiler_command, executable_name, peak_rss_kb


class _ApplicationExit(Exception):
    """Carry an interpreted application's requested exit code to the run reporter."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _capture_application_exit(code):
    raise _ApplicationExit(code)


def _set_run_report(report_state, status, tool_exit_code, process_exit_code,
                    *, execution=None, diagnostics=()):
    if report_state is None:
        return
    report_state.update({
        "status": status,
        "tool_exit_code": tool_exit_code,
        "process_exit_code": process_exit_code,
        "execution": execution,
        "diagnostics": list(diagnostics),
    })


def _write_run_report(path, invocation_id, report_state):
    result = tool_result(
        "run",
        report_state["status"],
        report_state["tool_exit_code"],
        process_exit_code=report_state["process_exit_code"],
        execution=report_state["execution"],
        diagnostics=report_state["diagnostics"],
        invocation_id=invocation_id,
    )
    write_tool_result_atomic(result, path)


def _same_file_path(first, second):
    first = os.path.normcase(os.path.realpath(os.path.abspath(os.fspath(first))))
    second = os.path.normcase(os.path.realpath(os.path.abspath(os.fspath(second))))
    if first == second:
        return True
    try:
        return os.path.samefile(first, second)
    except OSError:
        return False


def get_repo_root() -> str:
    return os.path.dirname(os.path.realpath(__file__))


def _bounded_tool_output(value: str, limit: int = 8192) -> str:
    """Keep subprocess diagnostics useful without embedding unbounded output."""
    if len(value) <= limit:
        return value
    suffix = "\n[tool output truncated]"
    return value[:limit - len(suffix)] + suffix


def _write_json_v1(command, status, exit_code, *, errors=(), source_by_file=None,
                   extra_diagnostics=(), artifacts=(), target=None):
    diagnostics = list(extra_diagnostics)
    span_cache = {}
    for error in errors:
        nested = getattr(error, "diagnostics", (error,))
        diagnostics.extend(diagnostic_from_error(item, source_by_file, span_cache=span_cache)
                           for item in nested)
    write_tool_result(
        tool_result(command, status, exit_code, diagnostics=diagnostics,
                    artifacts=artifacts, target=target),
        sys.stdout,
    )


def _sources_for_diagnostics(file_name, source_code, service=None):
    sources = {
        file_name: source_code,
        os.path.abspath(file_name): source_code,
    }
    if service is not None:
        sources.update(service.source_texts())
    return sources


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
        service = CompilerService()
        checked = service.check(compiler_src, compiler_src_path)
        c0_code = service.emit_c(checked, backend="ast").source

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
    execution_context: Optional[ExecutionContext] = None,
    json_v1: bool = False,
    tool_command: Optional[str] = None,
    report_state=None,
    project_root=None,
    project_resolver=None,
) -> int:
    if tool_command is None:
        if check_only:
            tool_command = "check"
        elif fmt_only:
            tool_command = "fmt"
        elif emit_c_path is not None:
            tool_command = "emit-c"
        elif build_bin_path is not None:
            tool_command = "build"
        else:
            tool_command = "run"
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
        checked = None
        selfhost_direct = (
            backend == "selfhost"
            and (emit_c_path is not None or build_bin_path is not None)
            and file_name != "<stdin>"
            and not show_tokens
            and not show_ast
            and not fmt_only
            and not check_only
        )

        if show_tokens:
            tokens = Lexer(source_code, file=file_name).tokenize()
            for t in tokens:
                print(f"  {t}")
            if not show_ast and not check_only and emit_c_path is None and build_bin_path is None:
                return 0

        if not selfhost_direct:
            service = CompilerService(project_root=project_root,
                                      project_resolver=project_resolver)
            parsed = service.parse(source_code, file_name, recover=check_only)
            ast = parsed.program if show_ast or fmt_only else None
            lex_ms, parse_ms = parsed.timing_ms['lex'], parsed.timing_ms['parse']
        if show_ast:
            print(json.dumps(ast.to_dict(), indent=2))
            if not check_only and emit_c_path is None and build_bin_path is None:
                return 0

        if fmt_only:
            formatted = Formatter().format(ast)
            if fmt_write and file_name != "<stdin>":
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(formatted)
                if json_v1:
                    artifact = artifact_file("formatted_source", "text/x-wysna", file_name)
            else:
                if json_v1:
                    artifact = artifact_inline("formatted_source", "text/x-wysna", formatted)
                else:
                    print(formatted, end="")
            if json_v1:
                _write_json_v1(
                    tool_command,
                    "ok",
                    0,
                    artifacts=[artifact],
                    target={"profile": "wysna-source", "triple": None},
                )
            return 0

        if not selfhost_direct:
            # 3. Static Type Checking
            t_check0 = time.perf_counter()
            checked = service.check_parsed(parsed)
            check_ms = (time.perf_counter() - t_check0) * 1000.0

        if show_mir:
            from mir.Nodes import dump
            print(dump(service.lower_mir(checked)), end="")
            return 0

        if check_only:
            if json_v1:
                _write_json_v1(tool_command, "ok", 0)
                return 0
            if show_stats:
                stat_obj = {
                    "status": "ok",
                    "file": file_name,
                    "telemetry": {
                        "monomorphization": dict(checked.telemetry),
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
            toolchain = NativeToolchain(repo_root)
            codegen_telemetry = None
            phase_ms = {}
            hir_ms = None
            if backend == "selfhost" and file_name != "<stdin>":
                selfhost_bin = ensure_selfhost_compiler_binary(repo_root)
                emission = toolchain.emit_selfhost(selfhost_bin, file_name)
                c_code, codegen_ms = emission.source, emission.codegen_ms
            else:
                emission = service.emit_c(checked, backend="ast" if backend == "ast" else "hir")
                c_code = emission.source
                codegen_telemetry = dict(emission.telemetry)
                phase_ms = emission.timing_ms if backend != "ast" else {}
                hir_ms = phase_ms.get("hir")
                codegen_ms = emission.timing_ms["codegen"]

            c_compile_ms = link_ms = 0.0
            def report_codegen_stats():
                if not show_stats:
                    return
                stat_obj = {
                    "status": "ok",
                    "file": file_name,
                    "telemetry": {
                        "monomorphization": dict(checked.telemetry) if checked is not None else None,
                        "codegen": codegen_telemetry,
                        "timing_ms": {
                            "lex": round(lex_ms, 2),
                            "parse": round(parse_ms, 2),
                            "check": round(check_ms, 2),
                            "hir": round(hir_ms, 2) if hir_ms is not None else None,
                            "codegen": round(codegen_ms, 2),
                            "mir": round(phase_ms.get('mir', 0), 2),
                            "c_emit": round(phase_ms.get('c_emit', 0), 2),
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
                    if json_v1:
                        artifact = artifact_file("c_source", "text/x-c", emit_c_path)
                        _write_json_v1(
                            tool_command,
                            "ok",
                            0,
                            artifacts=[artifact],
                            target={"profile": "c99-source", "triple": None},
                        )
                    report_codegen_stats()
                    return 0

            if build_bin_path is not None:
                built = toolchain.build(c_code, build_bin_path, sanitize=sanitize,
                                        link_libraries=link_libraries)
                c_compile_ms, link_ms = built.c_compile_ms, built.link_ms
                if json_v1:
                    artifact = artifact_file(
                        "native_executable", "application/octet-stream", built.output_path,
                    )
                    _write_json_v1(
                        tool_command,
                        "ok",
                        0,
                        artifacts=[artifact],
                        target={"profile": "native-cli", "triple": None},
                    )
                report_codegen_stats()
                return 0

        # 5. Runtime Interpretation
        if show_stats:
            print(json.dumps({
                "status": "ok",
                "file": file_name,
                "telemetry": {
                    "monomorphization": dict(checked.telemetry),
                    "timing_ms": {
                        "lex": round(lex_ms, 2),
                        "parse": round(parse_ms, 2),
                        "check": round(check_ms, 2),
                        "total": round((time.perf_counter() - t_start) * 1000.0, 2),
                    },
                    "peak_rss_kb": peak_rss_kb(),
                }
            }, indent=2), file=sys.stderr)
        res = service.interpret(checked, foreign_libraries=link_libraries,
                                execution_context=execution_context)

        if not isinstance(res, WysnaUnit) and file_name == "<stdin>":
            print(res)

        if report_state is not None:
            _set_run_report(
                report_state,
                "ok",
                0,
                0,
                execution={"kind": "application_exit", "exit_code": 0, "signal": None},
            )

        return 0

    except _ApplicationExit as termination:
        code = termination.code
        if report_state is None:
            raise SystemExit(code)
        if not 0 <= code <= 255:
            diagnostic = diagnostic_record(
                "W5002", "execution",
                "Application exit code is outside the portable range 0..255.",
                filename=file_name,
            )
            _set_run_report(
                report_state,
                "execution_error",
                5,
                5,
                execution={
                    "kind": "application_exit",
                    "exit_code": code,
                    "signal": None,
                    "data": {"portable_range": [0, 255]},
                },
                diagnostics=[diagnostic],
            )
            return 5
        _set_run_report(
            report_state,
            "ok",
            0,
            code,
            execution={"kind": "application_exit", "exit_code": code, "signal": None},
        )
        return code

    except NativeCompilationError as err:
        if report_state is not None:
            diagnostic = diagnostic_record(
                "W5001", "toolchain",
                _bounded_tool_output(f"{err.phase} failed: {err.stderr}"),
                filename=file_name,
            )
            _set_run_report(report_state, "toolchain_error", 3, 3,
                            diagnostics=[diagnostic])
            print(f"[{err.label}]\n{err.stderr}", file=sys.stderr)
            return 3
        if json_v1:
            diagnostic = diagnostic_record(
                "W5001", "toolchain",
                _bounded_tool_output(f"{err.phase} failed: {err.stderr}"),
                filename=file_name,
            )
            _write_json_v1(tool_command, "toolchain_error", 3,
                           extra_diagnostics=[diagnostic])
            return 3
        print(f"[{err.label}]\n{err.stderr}", file=sys.stderr)
        return 1
    except WysnaError as err:
        if report_state is not None:
            span_cache = {}
            source_by_file = _sources_for_diagnostics(
                file_name, source_code, locals().get("service"))
            diagnostics = [
                diagnostic_from_error(item, source_by_file, span_cache=span_cache)
                for item in getattr(err, "diagnostics", (err,))
            ]
            _set_run_report(report_state, "diagnostic_error", 1, 1,
                            diagnostics=diagnostics)
            for diagnostic in getattr(err, "diagnostics", (err,)):
                print(str(diagnostic), file=sys.stderr)
            return 1
        if json_v1:
            _write_json_v1(
                tool_command, "diagnostic_error", 1, errors=[err],
                source_by_file=_sources_for_diagnostics(
                    file_name, source_code, locals().get("service")),
            )
            return 1
        if json_diagnostics:
            print(json.dumps(err.to_dict(), indent=2))
        else:
            for diagnostic in getattr(err, 'diagnostics', (err,)):
                print(str(diagnostic), file=sys.stderr)
        return 1
    except Exception as exc:
        if report_state is not None:
            if isinstance(exc, OSError):
                diagnostic = diagnostic_record(
                    "W5004", "filesystem", f"Unable to access a requested file: {exc}",
                    filename=file_name,
                )
                _set_run_report(report_state, "toolchain_error", 3, 3,
                                diagnostics=[diagnostic])
                print(f"[Filesystem Error] {exc}", file=sys.stderr)
                return 3
            diagnostic = diagnostic_record(
                "W9999", "internal", str(exc), filename=file_name,
            )
            _set_run_report(report_state, "internal_error", 4, 4,
                            diagnostics=[diagnostic])
            print(f"[Internal Error] {exc}", file=sys.stderr)
            return 4
        if json_v1:
            if isinstance(exc, OSError):
                diagnostic = diagnostic_record(
                    "W5004", "filesystem", f"Unable to write requested output: {exc}",
                    filename=file_name,
                )
                _write_json_v1(tool_command, "toolchain_error", 3,
                               extra_diagnostics=[diagnostic])
                return 3
            diagnostic = diagnostic_record(
                "W9999", "internal", str(exc), filename=file_name,
            )
            _write_json_v1(tool_command, "internal_error", 4,
                           extra_diagnostics=[diagnostic])
            return 4
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
    print(f"  {prog} service serve --worker <bin> --database <db> # Local bounded HTTP/JSON pilot")
    print(f"  {prog} repl                                    # Start interactive REPL")
    print(f"  {prog} [run] [--stats] [--report-json <path>] [--invocation-id <id>] <file.wysna> [-- args...] # Execute Wysna source file")
    print(f"  {prog} check [--json|--output-format=json-v1] [--stats] <file.wysna>   # Static typecheck without execution")
    print(f"  {prog} fmt [--write] [--output-format=json-v1] <file.wysna> # Canonical deterministic formatter")
    print(f"  {prog} ast [--json] <file.wysna>               # Emit canonical JSON AST (v0.1)")
    print(f"  {prog} mir <file.wysna>                        # Emit verified MIR as JSON")
    print(f"  {prog} emit-mir [--implementation=seed|compiler] <file.wysna> [-o <out.json>] # Emit portable MIR")
    print(f"  {prog} tokens <file.wysna>                     # Emit lexical token stream")
    print(f"  {prog} emit-c [--backend=hir|ast|selfhost] [--output-format=json-v1] <file.wysna> [-o <out.c>] # Transpile to C99")
    print(f"  {prog} build [--backend=hir|ast|selfhost] [--output-format=json-v1] <file.wysna> [-o <bin>] # Compile native binary")
    print(f"  {prog} test [--differential [N]] [--fuzz [N]]            # Run conformance, differential, or fuzz suite")
    print(f"  {prog} bench [--update-baseline]                         # Run Seed/Compiler performance benchmark harness")
    print(f"  {prog} version                                           # Show compiler version")


def main(argv=None) -> None:
    prog = "wysna"
    args = list(sys.argv[1:] if argv is None else argv)
    cli_args = args[:args.index("--")] if "--" in args else args
    json_v1 = "--output-format=json-v1" in cli_args
    report_json_path = None
    requested_invocation_id = None
    command_for_output = args[0] if args and args[0] in (
        "run", "check", "fmt", "ast", "mir", "tokens", "emit-c", "build",
        "test", "bench", "version", "repl",
    ) else "run"

    def usage_error(message: str) -> None:
        if json_v1 and report_json_path is None:
            diagnostic = diagnostic_record("W5002", "usage", message)
            write_tool_result(
                tool_result(command_for_output, "usage_error", 2,
                            diagnostics=[diagnostic]),
                sys.stdout,
            )
            raise SystemExit(2)
        print(f"{prog}: {message}", file=sys.stderr)
        print(f"Try '{prog} --help' for usage.", file=sys.stderr)
        raise SystemExit(2)

    if args and args[0] == "project":
        from tooling.ProjectCLI import run_project_command
        raise SystemExit(run_project_command(args[1:]))
    if args and args[0] == "emit-mir":
        from tooling.MirCLI import run_mir_command
        raise SystemExit(run_mir_command(args[1:]))
    if args and args[0] == "service":
        from tooling.ServiceCLI import run_service_command
        raise SystemExit(run_service_command(args[1:]))
    if args and args[0] == "api":
        from tooling.ApiIndex import run_api_command
        raise SystemExit(run_api_command(args[1:]))
    if args and args[0] == "capabilities":
        from tooling.ApiIndex import run_capabilities_command
        raise SystemExit(run_capabilities_command(args[1:]))
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
        command_for_output = subcmd
        args = args[1:]
        if subcmd == "bench":
            if any(arg not in ("--update-baseline", "--help", "-h") for arg in args):
                usage_error("bench accepts only --update-baseline")
            if args in (["--help"], ["-h"]):
                print_help()
                return
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
                count_seen = False
                seed_seen = False
                while idx < len(args):
                    if args[idx] == "--seed" and not seed_seen and idx + 1 < len(args) and args[idx + 1].isdigit():
                        base_seed = int(args[idx + 1])
                        seed_seen = True
                        idx += 2
                    elif args[idx].isdigit() and not count_seen:
                        gen_count = int(args[idx])
                        count_seen = True
                        idx += 1
                    else:
                        usage_error(f"invalid test option '{args[idx]}'")
                repo_root = get_repo_root()
                selfhost_bin = ensure_selfhost_compiler_binary(repo_root)
                from tests.differential.differential_test import run_differential_suite
                ok = run_differential_suite(repo_root, selfhost_bin, generated_count=gen_count, base_seed=base_seed)
                sys.exit(0 if ok else 1)
            elif args and args[0] == "--fuzz":
                fuzz_count = 200
                base_seed = 9000
                idx = 1
                count_seen = False
                seed_seen = False
                while idx < len(args):
                    if args[idx] == "--seed" and not seed_seen and idx + 1 < len(args) and args[idx + 1].isdigit():
                        base_seed = int(args[idx + 1])
                        seed_seen = True
                        idx += 2
                    elif args[idx].isdigit() and not count_seen:
                        fuzz_count = int(args[idx])
                        count_seen = True
                        idx += 1
                    else:
                        usage_error(f"invalid test option '{args[idx]}'")
                repo_root = get_repo_root()
                from tests.differential.differential_test import run_fuzz_suite
                ok = run_fuzz_suite(fuzz_count=fuzz_count, base_seed=base_seed, repo_root=repo_root)
                sys.exit(0 if ok else 1)
            else:
                if any(arg not in ("--sanitize", "-s") for arg in args):
                    usage_error(f"invalid test option '{next(arg for arg in args if arg not in ('--sanitize', '-s'))}'")
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

    program_args = []
    if "--" in args:
        separator = args.index("--")
        if subcmd not in (None, "run"):
            usage_error("program arguments after -- are supported only by run")
        if separator == 0:
            usage_error("a source file must appear before --")
        program_args = args[separator + 1:]
        args = args[:separator]

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
        elif arg == "--output-format=json-v1":
            json_v1 = True
        elif arg == "--report-json":
            if report_json_path is not None:
                usage_error("--report-json may be specified only once")
            i += 1
            if i >= len(args) or not args[i] or args[i].startswith("-"):
                usage_error("--report-json requires a file path")
            report_json_path = args[i]
        elif arg == "--invocation-id":
            if requested_invocation_id is not None:
                usage_error("--invocation-id may be specified only once")
            i += 1
            if i >= len(args) or args[i].startswith("-"):
                usage_error("--invocation-id requires a value")
            requested_invocation_id = args[i]
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
                usage_error(f"Unknown backend '{b_val}'. Valid backends: hir, ast, selfhost")
        elif arg in ("--version", "-v"):
            print(f"Wysna Language Compiler v{WYSNA_VERSION} (Wysna Seed + Wysna Compiler Self-Hosted C99)")
            sys.exit(0)
        elif arg == "--emit-c":
            i += 1
            if i >= len(args) or args[i].startswith("-"):
                usage_error("--emit-c requires an output path")
            emit_c_path = args[i]
        elif arg == "--build":
            i += 1
            if i >= len(args) or args[i].startswith("-"):
                usage_error("--build requires an output path")
            build_bin_path = args[i]
        elif arg == "-o":
            i += 1
            if i >= len(args) or args[i].startswith("-"):
                usage_error("-o requires an output path")
            if subcmd == "emit-c":
                emit_c_path = args[i]
            elif subcmd == "build":
                build_bin_path = args[i]
            else:
                build_bin_path = args[i]
        elif arg == "--link-lib":
            i += 1
            if i >= len(args) or args[i].startswith("-"):
                usage_error("--link-lib requires a library name or path")
            link_libraries.append(args[i])
        elif arg in ("--sanitize", "-s"):
            sanitize = True
        elif arg in ("--help", "-h"):
            if json_v1:
                usage_error("--help cannot be combined with --output-format=json-v1")
            print_help()
            sys.exit(0)
        elif arg.startswith("-"):
            usage_error(f"unrecognized option '{arg}'")
        else:
            if file_to_run is not None:
                usage_error("only one source file may be specified")
            file_to_run = arg
        i += 1

    prog_cmd = "wysna"

    if requested_invocation_id is not None and report_json_path is None:
        usage_error("--invocation-id requires --report-json")

    if report_json_path is not None:
        if subcmd not in (None, "run"):
            usage_error("--report-json is supported only by run")
        if json_v1 or json_diagnostics:
            usage_error("run --report-json cannot be combined with JSON output modes")
        if (show_tokens or show_ast or check_only or fmt_only or fmt_write
                or emit_c_path is not None or build_bin_path is not None or show_mir):
            usage_error("run --report-json supports program execution only")
        if requested_invocation_id == "":
            usage_error("--invocation-id must not be empty")

    if json_v1:
        supported_commands = ("check", "fmt", "emit-c", "build")
        if subcmd not in supported_commands:
            usage_error("--output-format=json-v1 is supported only by check, fmt, emit-c, and build")
        if json_diagnostics or show_stats or show_ast or show_tokens or show_mir:
            usage_error("--output-format=json-v1 cannot be combined with legacy JSON, stats, or diagnostic output modes")
        if subcmd == "check":
            if (not check_only or fmt_only or fmt_write or emit_c_path is not None
                    or build_bin_path is not None):
                usage_error("check --output-format=json-v1 supports type checking only")
            if sanitize or link_libraries:
                usage_error("check --output-format=json-v1 does not accept build options")
        elif subcmd == "fmt":
            if not fmt_only or check_only or emit_c_path is not None or build_bin_path is not None:
                usage_error("fmt --output-format=json-v1 supports formatting only")
            if sanitize or link_libraries or backend != "hir":
                usage_error("fmt --output-format=json-v1 does not accept backend or build options")
        elif subcmd == "emit-c":
            if check_only or fmt_only or fmt_write or build_bin_path is not None:
                usage_error("emit-c --output-format=json-v1 supports C generation only")
            if sanitize or link_libraries:
                usage_error("emit-c --output-format=json-v1 does not accept build options")
        elif subcmd == "build":
            if check_only or fmt_only or fmt_write or emit_c_path is not None:
                usage_error("build --output-format=json-v1 supports native compilation only")

    if file_to_run:
        if file_to_run.endswith(".w"):
            if json_v1:
                usage_error("'.w' files are no longer supported; rename the source to use the .wysna extension")
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

        report_state = None
        invocation_id = requested_invocation_id
        if report_json_path is not None:
            if _same_file_path(report_json_path, file_to_run):
                usage_error("the report path must not overwrite the source file")
            pending = tool_result(
                "run",
                "pending",
                None,
                process_exit_code=None,
                invocation_id=invocation_id,
            )
            invocation_id = pending["invocation_id"]
            try:
                write_tool_result_atomic(pending, report_json_path)
            except OSError as error:
                print(
                    f"{prog}: unable to initialize JSON report '{report_json_path}': {error}",
                    file=sys.stderr,
                )
                raise SystemExit(3)
            report_state = {
                "status": "pending",
                "tool_exit_code": None,
                "process_exit_code": None,
                "execution": None,
                "diagnostics": [],
            }

        if json_v1 and subcmd in ("emit-c", "build"):
            output_path = emit_c_path if subcmd == "emit-c" else build_bin_path
            canonical_output = os.path.normcase(os.path.realpath(output_path))
            canonical_source = os.path.normcase(os.path.realpath(file_to_run))
            try:
                same_file = os.path.samefile(output_path, file_to_run)
            except OSError:
                same_file = False
            if canonical_output == canonical_source or same_file:
                usage_error("the output path must not overwrite the source file")

        try:
            with open(file_to_run, "r", encoding="utf-8",
                      newline="" if json_v1 or report_state is not None else None) as f:
                source = f.read()
        except (OSError, UnicodeError) as e:
            if report_state is not None:
                diagnostic = diagnostic_record(
                    "W5003", "filesystem",
                    f"Unable to read source file '{file_to_run}': {e}",
                    filename=file_to_run,
                )
                _set_run_report(report_state, "toolchain_error", 3, 3,
                                diagnostics=[diagnostic])
                print(f"Error reading file '{file_to_run}': {e}", file=sys.stderr)
                try:
                    _write_run_report(report_json_path, invocation_id, report_state)
                except OSError as report_error:
                    print(f"{prog}: unable to finalize JSON report: {report_error}", file=sys.stderr)
                raise SystemExit(3)
            if json_v1:
                diagnostic = diagnostic_record(
                    "W5003", "filesystem", f"Unable to read source file '{file_to_run}': {e}",
                    filename=file_to_run,
                )
                write_tool_result(
                    tool_result(command_for_output, "toolchain_error", 3,
                                diagnostics=[diagnostic]),
                    sys.stdout,
                )
                sys.exit(3)
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
            execution_context=ExecutionContext.for_program(
                prog_cmd,
                program_args,
                **({"terminate": _capture_application_exit} if report_state is not None else {}),
            ),
            json_v1=json_v1,
            tool_command=command_for_output,
            report_state=report_state,
        )
        if report_state is not None:
            if report_state["status"] == "pending":
                _set_run_report(
                    report_state,
                    "ok",
                    0,
                    0,
                    execution={"kind": "application_exit", "exit_code": 0, "signal": None},
                )
            try:
                _write_run_report(report_json_path, invocation_id, report_state)
            except OSError as report_error:
                print(f"{prog}: unable to finalize JSON report: {report_error}", file=sys.stderr)
                raise SystemExit(3)
            sys.exit(report_state["process_exit_code"])
        sys.exit(code)

    # No file argument. Dropping into the REPL silently made `w check` in a Makefile exit
    # 0 without checking anything, so the REPL now needs to be asked for explicitly and
    # every other subcommand is a usage error.
    if report_json_path is not None:
        usage_error("--report-json requires a source file")
    if program_args:
        usage_error("program arguments require a source file")
    if subcmd is None or subcmd == "repl":
        if json_v1:
            usage_error("--output-format=json-v1 requires a supported command and a source file")
        repl(show_tokens=show_tokens, show_ast=show_ast)
        return
    if json_v1:
        usage_error(f"{subcmd} requires a source file")
    print(f"{prog_cmd} {subcmd}: no input file given", file=sys.stderr)
    print(f"usage: {prog_cmd} {subcmd} <file.wysna> [options]", file=sys.stderr)
    print(f"       {prog_cmd} repl        # start the interactive REPL", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
