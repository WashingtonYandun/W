"""Bounded, observable execution of the four compiler engines."""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ENGINES = ('interpreter', 'ast', 'hir', 'w1')
PROFILES = json.loads((ROOT / 'tests/engine_profiles.json').read_text())


def feature_for(label):
    return PROFILES['fixtures'].get(label.replace(os.sep, '/'), 'core')


def unsupported_reason(label, engine):
    return PROFILES['features'][feature_for(label)].get(engine, '')


class EngineResult:
    def __init__(self, engine, stdout='', stderr='', exit_code=0, compile_ok=True,
                 runtime_ok=True, diag_code='', infrastructure_error=''):
        self.engine = engine
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.compile_ok = compile_ok
        self.runtime_ok = runtime_ok
        self.diag_code = diag_code
        self.infrastructure_error = infrastructure_error


def asdict(result):
    return vars(result).copy()


def diagnostic(stderr):
    match = re.search(r'^\[(W\d+)\]', stderr, re.MULTILINE)
    return match.group(1) if match else ''


def execute(command, directory, phase, timeout, env=None):
    """Persist commands and output, including timeout and signal failures."""
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                timeout=timeout, env=env)
        record = {'command': command, 'returncode': result.returncode,
                  'stdout': result.stdout, 'stderr': result.stderr}
    except subprocess.TimeoutExpired as error:
        record = {'command': command, 'returncode': 124, 'timeout': timeout,
                  'stdout': (error.stdout or b'').decode(errors='replace'),
                  'stderr': (error.stderr or b'').decode(errors='replace')}
    except OSError as error:
        record = {'command': command, 'returncode': 127, 'stdout': '', 'stderr': str(error),
                  'launch_error': True}
    (directory / (phase + '.json')).write_text(json.dumps(record, indent=2))
    return record


def run_engine(engine, source, label, w1_bin, directory, sanitize=False):
    directory = Path(directory) / engine
    directory.mkdir(parents=True, exist_ok=True)
    source_path = directory / 'source.w'
    source_path.write_text(source)
    c_path, binary = directory / 'program.c', directory / 'program'
    driver = [sys.executable, str(ROOT / 'main.py')]
    if engine == 'interpreter':
        command = driver + ['run', str(source_path)]
    elif engine == 'w1':
        # Direct invocation: no W0 parser/checker runs on the input first.
        command = [str(w1_bin), str(source_path), str(c_path)]
    else:
        command = driver + ['emit-c'] + (['--hir'] if engine == 'hir' else [])
        command += [str(source_path), '-o', str(c_path)]
    front = execute(command, directory, 'frontend', 120)
    result = EngineResult(engine)
    failure = ('timeout' in front or 'launch_error' in front or front['returncode'] < 0)
    if engine == 'interpreter' or front['returncode'] != 0:
        result.stdout, result.stderr, result.exit_code = front['stdout'], front['stderr'], front['returncode']
        result.diag_code = diagnostic(result.stderr)
        result.compile_ok = result.exit_code == 0 or (engine == 'interpreter' and result.diag_code.startswith('W4'))
        result.runtime_ok = result.exit_code == 0
        if failure or result.diag_code == 'W9999' or (result.exit_code and not result.diag_code):
            result.infrastructure_error = 'frontend failed without a structured diagnostic'
        return result
    flags = ['-std=c99', '-O1', '-g', '-I' + str(ROOT)]
    if sanitize:
        flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    compiled = execute(shlex.split(os.environ.get('CC', 'cc')) + flags +
                       [str(c_path), '-o', str(binary)], directory, 'compile', 120)
    if compiled['returncode'] != 0:
        return EngineResult(engine, stderr=compiled['stderr'], exit_code=compiled['returncode'],
                            compile_ok=False, runtime_ok=False, infrastructure_error='C compilation failed')
    env = dict(os.environ, W_MEM_CHECK='1')
    if sanitize:
        env['ASAN_OPTIONS'] = 'detect_leaks=' + ('1' if sys.platform.startswith('linux') else '0')
        env['UBSAN_OPTIONS'] = 'halt_on_error=1:print_stacktrace=1'
    ran = execute([str(binary)], directory, 'run', 30, env)
    result.stdout, result.stderr, result.exit_code = ran['stdout'], ran['stderr'], ran['returncode']
    result.diag_code = diagnostic(result.stderr)
    result.runtime_ok = result.exit_code == 0
    if result.exit_code and (not result.diag_code or result.exit_code < 0 or 'timeout' in ran):
        result.infrastructure_error = 'native execution failed without a structured diagnostic'
    if any(marker in result.stderr for marker in ('AddressSanitizer', 'LeakSanitizer', 'runtime error:', 'Memory leak detected')):
        result.infrastructure_error = 'memory or sanitizer failure'
    return result


def compare(results, expected=None):
    for result in results:
        if result.infrastructure_error:
            return False, f'{result.engine}: {result.infrastructure_error}: {result.stderr}'
        if expected is not None and (result.exit_code != 0 or result.stdout != expected):
            return False, f'{result.engine}: expected successful execution and exact fixture output, got {asdict(result)}'
    if not results:
        return False, 'no supported engines executed'
    reference = results[0]
    for result in results[1:]:
        for field in ('compile_ok', 'runtime_ok', 'exit_code', 'stdout', 'diag_code'):
            if getattr(reference, field) != getattr(result, field):
                return False, f'{field} mismatch: {asdict(reference)} versus {asdict(result)}'
    if reference.exit_code == 0 and any(result.stderr != reference.stderr for result in results[1:]):
        return False, 'stderr mismatch on successful execution'
    return True, 'OK'


def verify_case(source, label, w1_bin, work_dir, expected=None, sanitize=False, strict=False, expect_rejection=False):
    artifacts = Path(os.environ.get('W_CI_ARTIFACTS', ROOT / '.w_cache/ci-artifacts'))
    case_id = hashlib.sha256(label.encode()).hexdigest()[:12]
    directory = Path(work_dir) / case_id
    directory.mkdir(parents=True, exist_ok=True)
    results, unsupported = [], {}
    for engine in ENGINES:
        reason = unsupported_reason(label, engine)
        if reason:
            unsupported[engine] = reason
        else:
            results.append(run_engine(engine, source, label, w1_bin, directory, sanitize))
    ok, detail = compare(results, expected)
    if expect_rejection:
        for result in results:
            if result.compile_ok or result.exit_code != 1 or not result.diag_code:
                ok, detail = False, f'{result.engine}: invalid fixture was not rejected by the frontend: {asdict(result)}'
    if strict and unsupported:
        ok, detail = False, 'release profile requires all engines: ' + str(unsupported)
    rows = []
    for result in results:
        row_ok, _ = compare([results[0], result], expected)
        if expect_rejection and (result.compile_ok or result.exit_code != 1 or not result.diag_code):
            row_ok = False
        rows.append(dict(asdict(result), status='passed' if row_ok else 'failed'))
    report = {'label': label, 'feature': feature_for(label), 'sanitize': sanitize, 'status': 'passed' if ok else 'failed',
              'unsupported': unsupported, 'results': rows}
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / (case_id + '.json')).write_text(json.dumps(report, indent=2))
    if unsupported:
        print(f'  [UNSUPPORTED] {label}: {unsupported}')
    if not ok:
        import shutil
        shutil.copytree(directory, artifacts / case_id, dirs_exist_ok=True)
    return ok, detail, report


def verify(*args, **kwargs):
    ok, detail, _ = verify_case(*args, **kwargs)
    return ok, detail
