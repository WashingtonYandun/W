#!/usr/bin/env python3
"""Measure exactly one child; isolate ru_maxrss from previous child executions."""
import json
import resource
import subprocess
import sys
import time


def main():
    command = sys.argv[1:]
    if command[:1] == ['--']:
        command = command[1:]
    if not command:
        raise SystemExit('usage: measure_process.py -- program [arguments]')
    started = time.perf_counter()
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    elapsed = time.perf_counter() - started
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    peak_bytes = usage.ru_maxrss if sys.platform == 'darwin' else usage.ru_maxrss * 1024
    print(json.dumps({'command': command, 'exit_code': result.returncode,
                      'stdout': result.stdout, 'stderr': result.stderr,
                      'elapsed_seconds': elapsed, 'user_seconds': usage.ru_utime,
                      'system_seconds': usage.ru_stime, 'peak_memory_bytes': peak_bytes}))


if __name__ == '__main__':
    main()
