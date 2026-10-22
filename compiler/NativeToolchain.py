"""Native compiler processes and temporary artifacts, independent of CLI output."""
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import tempfile
import time

from common.Platform import compiler_command, executable_name


@dataclass(frozen=True)
class NativeBuildResult:
    output_path: str
    c_compile_ms: float
    link_ms: float


@dataclass(frozen=True)
class SelfhostEmissionResult:
    source: str
    codegen_ms: float


class NativeCompilationError(Exception):
    """A failed process with the legacy label retained for presentation adapters."""

    def __init__(self, phase, label, stderr, returncode):
        super().__init__(stderr)
        self.phase = phase
        self.label = label
        self.stderr = stderr
        self.returncode = returncode


class NativeToolchain:
    def __init__(self, repo_root):
        self.repo_root = os.fspath(repo_root)

    def build(self, c_source, output, sanitize=False, link_libraries=()):
        """Compile C and explicit adapters, then link without owning caller inputs."""
        sanitizer_flags = (
            ['-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if sanitize else []
        )
        base = compiler_command() + ['-std=c99', '-O2', f'-I{self.repo_root}'] + sanitizer_flags
        output_path = executable_name(os.fspath(output))
        libraries = tuple(os.fspath(library) for library in link_libraries)
        object_suffix = '.obj' if os.name == 'nt' else '.o'
        with tempfile.TemporaryDirectory(prefix='wysna-native-') as temporary:
            source_path = Path(temporary) / 'program.c'
            source_path.write_text(c_source, encoding='utf-8')
            object_path = str(Path(temporary) / ('program' + object_suffix))
            source_objects = {
                library: str(Path(temporary) / ('adapter-' + str(index) + object_suffix))
                for index, library in enumerate(libraries)
                if library.lower().endswith('.c') and os.path.isfile(library)
            }
            started = time.perf_counter()
            for source, compiled in [(str(source_path), object_path)] + list(source_objects.items()):
                result = subprocess.run(
                    base + ['-c', source, '-o', compiled],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode != 0:
                    raise NativeCompilationError(
                        'c_compile', 'C Compiler Error', result.stderr, result.returncode,
                    )
            c_compile_ms = (time.perf_counter() - started) * 1000.0
            linker_inputs = [
                source_objects[library] if library in source_objects else
                library if '/' in library or '\\' in library else '-l' + library
                for library in libraries
            ]
            started = time.perf_counter()
            result = subprocess.run(
                base + [object_path, '-o', output_path] + linker_inputs,
                capture_output=True, text=True, timeout=120,
            )
            link_ms = (time.perf_counter() - started) * 1000.0
            if result.returncode != 0:
                raise NativeCompilationError(
                    'link', 'C Linker Error', result.stderr, result.returncode,
                )
        return NativeBuildResult(output_path, c_compile_ms, link_ms)

    def emit_selfhost(self, compiler_path, file):
        """Use the independent compiler directly, resolving imports beside its input."""
        input_path = os.path.abspath(os.fspath(file))
        input_directory = os.path.dirname(input_path) or os.getcwd()
        with tempfile.TemporaryDirectory(prefix='wysna-selfhost-') as temporary:
            output_path = str(Path(temporary) / 'program.c')
            started = time.perf_counter()
            result = subprocess.run(
                [os.fspath(compiler_path), input_path, output_path],
                capture_output=True, text=True, cwd=input_directory, timeout=120,
            )
            codegen_ms = (time.perf_counter() - started) * 1000.0
            if result.returncode != 0:
                raise NativeCompilationError(
                    'selfhost', 'Wysna Compiler Error', result.stderr, result.returncode,
                )
            source = Path(output_path).read_text(encoding='utf-8')
        return SelfhostEmissionResult(source, codegen_ms)
