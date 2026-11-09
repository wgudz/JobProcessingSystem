"""Safe environment diagnostics; no downloads or modifications."""
from __future__ import annotations
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    print('AI JOB PROCESSING / ENVIRONMENT')
    print('Python:', sys.version.split()[0])
    required = ('git', 'cmake', 'ctest')
    optional = ('ollama', 'cl', 'g++', 'clang++')
    missing = []
    for name in (*required, *optional):
        found = shutil.which(name)
        print(name + ':', found or 'NOT FOUND')
        if name in required and not found:
            missing.append(name)
    if not any(shutil.which(name) for name in ('cl', 'g++', 'clang++')):
        print('Compiler not detected; on Windows use Developer PowerShell for VS with C++ tools')
        missing.append('C++20 compiler')
    for path in ('CMakeLists.txt', 'src/job_manager.cpp', 'include/job_system/thread_safe_queue.h', 'skills/job-processing-triage/SKILL.md'):
        if not (ROOT / path).is_file():
            print('MISSING:', path)
            missing.append(path)
    if shutil.which('git') and (ROOT / '.git').exists():
        p = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, text=True, capture_output=True)
        print('Git commit:', p.stdout.strip())
    print('ENVIRONMENT=' + ('FAIL' if missing else 'PASS'))
    return 1 if missing else 0


if __name__ == '__main__':
    raise SystemExit(main())
