import os
import subprocess
import tempfile
from pathlib import Path


def test_deep_runtime_operations_are_iterative():
    repository_root = Path(__file__).resolve().parents[2]
    source = repository_root / "tests" / "runtime" / "deep_runtime.c"

    with tempfile.TemporaryDirectory(prefix="wysna-deep-runtime-") as temporary_directory:
        executable = Path(temporary_directory) / "deep-runtime"
        compiler = os.environ.get("CC", "cc")
        compiled = subprocess.run(
            [
                compiler,
                "-std=c99",
                "-fsanitize=address,undefined",
                "-fno-omit-frame-pointer",
                f"-I{repository_root}",
                str(source),
                "-o",
                str(executable),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert compiled.returncode == 0, compiled.stderr

        environment = os.environ.copy()
        environment["WYSNA_MEM_CHECK"] = "1"
        result = subprocess.run(
            [str(executable)],
            capture_output=True,
            text=True,
            timeout=30,
            env=environment,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout == "deep runtime values passed\n"
