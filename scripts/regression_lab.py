"""Apply two opt-in, deterministic training regressions to the pinned clean branch."""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIN = '9eddee6112b3bd7879dd17a79ea638746a1a0437'
SCENARIOS = {
    'priority': (
        'include/job_system/thread_safe_queue.h',
        'if (priority == 2)\n        {\n            highQueue_.push(std::move(value));',
        'if (priority == 2)\n        {\n            lowQueue_.push(std::move(value));',
    ),
    'statistics': (
        'src/statistics.cpp',
        '    ++cancelled_;\n    ++finishedJobs_;',
        '    ++failed_;\n    ++finishedJobs_;',
    ),
}


def git(*args):
    p = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f'git command failed: {p.stderr.strip()}')
    return p.stdout.strip()


def ensure_safe_branch():
    if git('rev-parse', 'HEAD') != PIN:
        raise RuntimeError('STOP: base HEAD is not pinned upstream commit; do not apply against random revision')
    if git('branch', '--show-current') != 'training/ai-job-processing':
        raise RuntimeError('STOP: use dedicated training/ai-job-processing branch')
    if git('diff', '--name-only', '--', 'src', 'include', 'tests', 'CMakeLists.txt'):
        raise RuntimeError('STOP: source files already modified; resolve/commit changes first')
    if git('diff', '--cached', '--name-only', '--', 'src', 'include', 'tests', 'CMakeLists.txt'):
        raise RuntimeError('STOP: staged source changes found')


def apply(scenarios):
    ensure_safe_branch()
    updates = []
    for item in scenarios:
        rel, old, new = SCENARIOS[item]
        path = ROOT / rel
        text = path.read_text(encoding='utf-8')
        if text.count(old) != 1:
            raise RuntimeError(f'STOP: {rel} does not match expected upstream code')
        updates.append((path, text.replace(old, new, 1)))
    for path, updated in updates:
        path.write_text(updated, encoding='utf-8')
    print('TRAINING_REGRESSION=APPLIED:', ', '.join(scenarios))
    print('Next: python scripts/verify_lab.py --expect red')
    print('Agent never applies fixes: student reviews the diff and makes the repairs.')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--scenario', choices=('priority', 'statistics', 'both'), required=True)
    p.add_argument('--apply', action='store_true', help='Mandatory confirmation; edits C++ source in TRAINING branch')
    args = p.parse_args()
    if not args.apply:
        p.error('Specify --apply to deliberately introduce a training regression')
    scenarios = list(SCENARIOS) if args.scenario == 'both' else [args.scenario]
    try:
        apply(scenarios)
    except (RuntimeError, OSError) as exc:
        print('REGRESSION=STOP:', exc, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
