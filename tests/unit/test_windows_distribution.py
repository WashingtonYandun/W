"""Windows bundles must be independent of host installations and reject unsafe inputs."""
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
import zipfile

from common.Platform import compiler_command
from tools.package_windows import assemble, download, extract


def test_windows_bundle_compiler_and_explicit_override():
    with tempfile.TemporaryDirectory(prefix='w installation with spaces ') as temporary:
        root = Path(temporary).resolve()
        (root / 'common').mkdir()
        compiler = root / 'toolchain/zig/zig.exe'
        compiler.parent.mkdir(parents=True)
        compiler.write_bytes(b'')
        compiler.chmod(0o755)
        with patch('common.Platform.__file__', str(root / 'common/Platform.py')):
            with patch('common.Platform.os.name', 'nt'), patch.dict(os.environ, {'CC': ''}):
                assert compiler_command() == [str(compiler), 'cc', '-target', 'x86_64-windows-gnu', '-mcpu=baseline']
            with patch('common.Platform.os.name', 'nt'), patch.dict(os.environ, CC='custom-compiler'):
                with patch('common.Platform.shutil.which', return_value='custom-compiler'):
                    assert compiler_command() == ['custom-compiler']
            compiler.unlink()
            with patch('common.Platform.os.name', 'nt'), patch.dict(os.environ, {'CC': ''}):
                with patch('common.Platform.shutil.which', return_value='clang'):
                    assert compiler_command() == ['clang']


def test_bundle_extraction_rejects_cross_platform_path_traversal():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for name in ('../outside.py', '/absolute.py', 'C:/absolute.py', 'C:relative.py', '..\\outside.py'):
            archive = root / 'unsafe.zip'
            with zipfile.ZipFile(archive, 'w') as zipped:
                zipped.writestr(name, 'unsafe')
            try:
                extract(archive, root / 'output')
            except ValueError:
                pass
            else:
                raise AssertionError('Unsafe Windows path accepted: ' + name)
            assert not (root / 'output').exists()


def test_component_checksum_failure_precedes_network_and_extraction():
    with tempfile.TemporaryDirectory() as temporary:
        cache = Path(temporary)
        (cache / 'python.zip').write_bytes(b'corrupted')
        with patch('tools.package_windows.urllib.request.urlopen', side_effect=AssertionError('No download expected')):
            try:
                download({'url': 'https://www.python.org/python.zip', 'sha256': '0' * 64}, cache)
            except ValueError as error:
                assert 'checksum mismatch' in str(error)
            else:
                raise AssertionError('Corrupted cached archive accepted')


def test_bundle_never_replaces_existing_installation():
    with tempfile.TemporaryDirectory() as temporary:
        existing = Path(temporary)
        marker = existing / 'project.w'
        marker.write_text('print(7)')
        try:
            assemble(existing / 'missing.whl', existing, existing / 'cache')
        except ValueError:
            pass
        else:
            raise AssertionError('Existing installation accepted as build output')
        assert marker.read_text() == 'print(7)'
        assert not (existing / 'cache').exists()


if __name__ == '__main__':
    test_windows_bundle_compiler_and_explicit_override()
    test_bundle_extraction_rejects_cross_platform_path_traversal()
    test_component_checksum_failure_precedes_network_and_extraction()
    test_bundle_never_replaces_existing_installation()
    print('Windows distribution: private toolchain, overrides, checksums and safe extraction passed')
