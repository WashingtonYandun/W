"""Tests for Wysna branding, CLI aliases, .wysna extension and runtime shims."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_wysna_cli_help_and_version():
    wysna_bin = ROOT / "wysna"
    assert wysna_bin.is_file() and os.access(wysna_bin, os.X_OK)

    # wysna version
    res = subprocess.run([sys.executable, str(wysna_bin), "version"],
                         capture_output=True, text=True, check=True)
    assert "Wysna Language Compiler" in res.stdout
    assert "Wysna Seed + Wysna Compiler" in res.stdout

    # wysna --help
    res = subprocess.run([sys.executable, str(wysna_bin), "--help"],
                         capture_output=True, text=True, check=True)
    assert "Wysna Language Compiler" in res.stdout
    assert "wysna [run]" in res.stdout
    assert "<file.wysna>" in res.stdout


def test_legacy_w_cli_removed():
    legacy_w_bin = ROOT / "w"
    assert not legacy_w_bin.exists()


def test_wysna_file_execution_interpreter_and_native():
    wysna_bin = ROOT / "wysna"
    with tempfile.TemporaryDirectory(prefix="wysna_test_") as tmpdir:
        tmp = Path(tmpdir)
        source = tmp / "hello.wysna"
        source.write_text('print("hello from wysna")\n', encoding="utf-8")

        # 1. Interpreter: wysna run
        run_res = subprocess.run([sys.executable, str(wysna_bin), "run", str(source)],
                                capture_output=True, text=True)
        assert run_res.returncode == 0, run_res.stderr
        assert run_res.stdout == "hello from wysna\n"

        # 2. Typechecker: wysna check
        chk_res = subprocess.run([sys.executable, str(wysna_bin), "check", str(source)],
                                capture_output=True, text=True)
        assert chk_res.returncode == 0, chk_res.stderr

        # 3. Native build: wysna build
        out_bin = tmp / "hello_bin"
        build_res = subprocess.run([sys.executable, str(wysna_bin), "build", str(source), "-o", str(out_bin)],
                                  capture_output=True, text=True)
        assert build_res.returncode == 0, build_res.stderr
        assert out_bin.is_file()

        exec_res = subprocess.run([str(out_bin)], capture_output=True, text=True)
        assert exec_res.returncode == 0
        assert exec_res.stdout == "hello from wysna\n"


def test_wysna_module_import():
    wysna_bin = ROOT / "wysna"
    with tempfile.TemporaryDirectory(prefix="wysna_mod_") as tmpdir:
        tmp = Path(tmpdir)
        helper = tmp / "helper.wysna"
        helper.write_text('pub fn greet(name: str) -> str {\n    return "Salutations, " + name\n}\n', encoding="utf-8")

        main_src = tmp / "main.wysna"
        main_src.write_text('import "helper.wysna" as h\nprint(h.greet("Washo"))\n', encoding="utf-8")

        run_res = subprocess.run([sys.executable, str(wysna_bin), "run", str(main_src)],
                                capture_output=True, text=True)
        assert run_res.returncode == 0, run_res.stderr
        assert run_res.stdout == "Salutations, Washo\n"


def test_wysna_legacy_w_file_rejected():
    wysna_bin = ROOT / "wysna"
    with tempfile.TemporaryDirectory(prefix="wysna_legacy_") as tmpdir:
        tmp = Path(tmpdir)
        source_w = tmp / "legacy.w"
        source_w.write_text('print("legacy w file")\n', encoding="utf-8")

        res = subprocess.run([sys.executable, str(wysna_bin), "run", str(source_w)],
                             capture_output=True, text=True)
        assert res.returncode == 1
        assert "error: '.w' files are no longer supported. Rename" in res.stderr
        assert "legacy.wysna" in res.stderr


def test_wysna_runtime_headers_exist_and_include():
    wysna_host = ROOT / "runtime" / "wysna_host.h"
    wysna_runtime = ROOT / "runtime" / "wysna_runtime.h"
    assert wysna_host.is_file()
    assert wysna_runtime.is_file()

    # Compile a trivial C probe that includes both
    with tempfile.TemporaryDirectory(prefix="wysna_c_") as tmpdir:
        c_file = Path(tmpdir) / "probe.c"
        c_file.write_text(f'#include "{wysna_runtime}"\n#include "{wysna_host}"\nint main(void) {{ return 0; }}\n', encoding="utf-8")
        out_bin = Path(tmpdir) / "probe"
        cc = os.environ.get("CC", "cc")
        res = subprocess.run([cc, "-I", str(ROOT / "runtime"), str(c_file), "-o", str(out_bin)],
                             capture_output=True, text=True)
        assert res.returncode == 0, res.stderr
