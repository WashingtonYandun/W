"""Exercise managed error payloads and cleanup in every engine."""
from pathlib import Path
import tempfile

from tests.engine_harness import ENGINES, compare, run_engine


def run_f03_ownership_tests():
    from main import ensure_selfhost_compiler_binary

    root = Path(__file__).resolve().parents[2]
    fixture = root / 'tests/runtime/error_union_ownership.wysna'
    selfhost_bin = ensure_selfhost_compiler_binary(str(root))
    with tempfile.TemporaryDirectory(prefix='w-f03-ownership-') as directory:
        results = [run_engine(engine, fixture.read_text(), str(fixture), selfhost_bin, directory,
                              sanitize=True) for engine in ENGINES]
        ok, detail = compare(results, fixture.with_suffix('.expected').read_text())
        assert ok, (detail, [vars(result) for result in results])
        assert all(not result.stderr for result in results), [vars(result) for result in results]
    print('F03 ownership: four engines, managed payloads, guards, CoW and cleanup passed')


if __name__ == '__main__':
    run_f03_ownership_tests()
