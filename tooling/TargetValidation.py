"""Preflight checks for capabilities required by a selected project target."""
from pathlib import Path

from error.Error import WysnaError
from project.Targets import target_spec


def validate_checked_target(checked, target):
    """Reject source capabilities unavailable to a target before its toolchain runs."""
    spec = target_spec(target.profile)
    repository_root = Path(__file__).resolve().parents[1]
    standard_library = (repository_root / "stdlib").resolve()
    module_paths = {Path(path).resolve() for path in checked.modules}
    http_module = (standard_library / "http.wysna").resolve()
    if target.profile == "wasi-command" and http_module in module_paths:
        raise WysnaError(
            "the wasi-command profile does not support std/http; use a native-cli target",
            file=checked.source.file, code="W2013", stage="target",
        )
    if target.profile != "wasi-command":
        return spec

    process_module = (standard_library / "process.wysna").resolve()
    file_modules = {
        (standard_library / "files.wysna").resolve(),
        (standard_library / "fs.wysna").resolve(),
    }
    if process_module in module_paths:
        raise WysnaError(
            "the wasi-command profile does not support std/process; use a native-cli target",
            file=checked.source.file, code="W2013", stage="target",
        )
    if module_paths.intersection(file_modules) and not target.preopens:
        raise WysnaError(
            "this program uses filesystem APIs but the wasi-command target declares no preopens",
            file=checked.source.file, code="W2013", stage="target",
        )

    for declaration in checked.declarations.values():
        if declaration.kind != "ExternFnDecl":
            continue
        path = Path(declaration.file).resolve()
        try:
            path.relative_to(standard_library)
        except ValueError:
            raise WysnaError(
                f"native C function '{declaration.name}' has no declared WASI host binding",
                line=declaration.line, col=declaration.col, file=declaration.file,
                code="W2013", stage="target",
            )
    return spec
