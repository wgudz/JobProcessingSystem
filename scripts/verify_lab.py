"""Run real Python agent tests and existing CMake/CTest; verify RED or GREEN."""
from __future__ import annotations
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RED_TESTS = {'thread_safe_queue_test', 'statistics_test'}


def run(argv, timeout=180):
    print('\n>', ' '.join(map(str, argv)), flush=True)
    try:
        p = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                           errors='replace', timeout=timeout)
    except subprocess.TimeoutExpired:
        print('FAIL: command timed out')
        raise SystemExit(124)
    except FileNotFoundError as exc:
        print('FAIL: missing', exc.filename)
        raise SystemExit(127)
    print(p.stdout[-10000:])
    print(p.stderr[-3000:])
    return p


def main():
    p = argparse.ArgumentParser(description='End-to-end RED/GREEN acceptance test')
    p.add_argument('--expect', choices=('green', 'red'), default='green')
    args = p.parse_args()
    if not (ROOT / 'CMakeLists.txt').exists():
        print('FAIL: CMakeLists.txt not found; run install_lab.py first')
        return 2
    if run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests_ai', '-v']).returncode:
        print('FAIL: Python agent tests')
        return 3
    if run(['cmake', '-S', str(ROOT), '-B', str(ROOT / 'build')]).returncode:
        return 4
    if run(['cmake', '--build', str(ROOT / 'build'), '--config', 'Debug', '--parallel', '2']).returncode:
        return 5
    result = run(['ctest', '--test-dir', str(ROOT / 'build'), '-C', 'Debug', '--output-on-failure'])
    failed = set(re.findall(r'^\s*\d+\s+-\s+([A-Za-z0-9_]+)\s+\(Failed\)', result.stdout, re.MULTILINE))
    print('FAILED_TESTS=', sorted(failed))
    if args.expect == 'green':
        passed = result.returncode == 0 and not failed and '100% tests passed' in result.stdout
    else:
        passed = result.returncode != 0 and failed == RED_TESTS
    print('ACCEPTANCE_' + args.expect.upper() + '=' + ('PASS' if passed else 'FAIL'))
    if not passed and args.expect == 'red':
        print('Expected exactly the two controlled failures. Other failures require separate investigation.')
    return 0 if passed else 6


if __name__ == '__main__':
    raise SystemExit(main())
