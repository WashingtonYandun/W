"""Direct Wysna Compiler coverage for generic function inference and constraints."""

import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_generic_function_inference_and_explicit_arguments():
    from main import ensure_selfhost_compiler_binary

    compiler = ensure_selfhost_compiler_binary(str(ROOT))
    with tempfile.TemporaryDirectory(prefix="selfhost-generic-function-") as directory:
        output_c = Path(directory) / "generic_function.c"
        built = subprocess.run(
            [compiler, str(ROOT / "tests/runtime/generic_function.wysna"), str(output_c)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert built.returncode == 0, built.stderr

        binary = Path(directory) / "generic_function"
        compiled = subprocess.run(
            [os.environ.get("CC", "cc"), "-std=c99", f"-I{ROOT}", str(output_c), "-o", str(binary)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert compiled.returncode == 0, compiled.stderr

        executed = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
        assert executed.returncode == 0, executed.stderr
        assert executed.stdout == "42\ngeneric inference\ntrue\n"


def test_generic_interface_constraints_reject_non_implementations():
    from main import ensure_selfhost_compiler_binary

    compiler = ensure_selfhost_compiler_binary(str(ROOT))
    fixtures = (
        ROOT / "tests/types/invalid/generic_constraint_failure.wysna",
        ROOT / "tests/types/invalid/generic_nominal_constraint_violation.wysna",
    )
    with tempfile.TemporaryDirectory(prefix="selfhost-generic-constraint-") as directory:
        for index, fixture in enumerate(fixtures):
            output_c = Path(directory) / f"invalid_{index}.c"
            result = subprocess.run(
                [compiler, str(fixture), str(output_c)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert result.returncode != 0, f"Wysna Compiler accepted invalid generic constraint fixture {fixture}"
            assert "[W2001]" in result.stderr, result.stderr
            assert not output_c.exists(), "Wysna Compiler must reject invalid source before emitting C"


def test_generic_runtime_and_checked_module_fixtures():
    from main import ensure_selfhost_compiler_binary

    compiler = ensure_selfhost_compiler_binary(str(ROOT))
    fixtures = [
        *sorted((ROOT / "tests/runtime").glob("generic_*.wysna")),
        ROOT / "tests/runtime/recursive_tree_adt.wysna",
        ROOT / "tests/modules/checked_session/main.wysna",
    ]
    environment = dict(os.environ, W_MEM_CHECK="1")
    with tempfile.TemporaryDirectory(prefix="selfhost-generic-runtime-") as directory:
        for index, fixture in enumerate(fixtures):
            output_c = Path(directory) / f"fixture_{index}.c"
            built = subprocess.run(
                [compiler, str(fixture), str(output_c)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=120,
            )
            assert built.returncode == 0, f"Wysna Compiler failed to compile {fixture}: {built.stderr}"

            binary = Path(directory) / f"fixture_{index}"
            compiled = subprocess.run(
                [os.environ.get("CC", "cc"), "-std=c99", "-O1", f"-I{ROOT}", str(output_c), "-o", str(binary)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=60,
            )
            assert compiled.returncode == 0, f"C99 compilation failed for {fixture}: {compiled.stderr}"

            executed = subprocess.run(
                [str(binary)],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=20,
            )
            expected = fixture.with_suffix(".expected").read_text()
            assert executed.returncode == 0, f"Wysna Compiler runtime failed for {fixture}: {executed.stderr}"
            assert executed.stdout == expected, f"Unexpected Wysna Compiler output for {fixture}: {executed.stdout!r}"


def test_generic_cycle_diagnostics():
    from main import ensure_selfhost_compiler_binary

    compiler = ensure_selfhost_compiler_binary(str(ROOT))
    fixtures = (
        ROOT / "tests/types/invalid/generic_recursive_infinite_layout.wysna",
        ROOT / "tests/types/invalid/generic_struct_recursive_cycle.wysna",
        ROOT / "tests/types/invalid/generic_structural_growth_cycle.wysna",
    )
    with tempfile.TemporaryDirectory(prefix="selfhost-generic-cycle-") as directory:
        for index, fixture in enumerate(fixtures):
            output_c = Path(directory) / f"invalid_{index}.c"
            result = subprocess.run(
                [compiler, str(fixture), str(output_c)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert result.returncode != 0, f"Wysna Compiler accepted invalid generic cycle fixture {fixture}"
            assert "[W2011]" in result.stderr, result.stderr
            assert not output_c.exists(), "Wysna Compiler must reject invalid source before emitting C"


if __name__ == "__main__":
    test_generic_function_inference_and_explicit_arguments()
    test_generic_interface_constraints_reject_non_implementations()
    test_generic_runtime_and_checked_module_fixtures()
    test_generic_cycle_diagnostics()
    print("Wysna Compiler generic specialization and module fixtures passed")
