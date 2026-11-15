"""Read-only inspection and allowlisted build/test actions, never arbitrary shell."""
from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Any
import time
import json

TOOLS = [
 ('list_files', 'List C++ sources, application, tests and CMake files.', {}),
 ('read_file', 'Read one allowlisted project file by relative path.', {'path': {'type': 'string', 'description': 'E.g. include/job_system/thread_safe_queue.h'}}),
 ('git_diff', 'Read unstaged Git source diff. Changes may be uncommitted.', {}),
 ('git_log', 'Inspect recent local commit summaries.', {}),
 ('run_cmake_configure', 'Configure CMake in build/ (requires --allow-exec).', {}),
 ('run_cmake_build', 'Build the project (requires --allow-exec).', {}),
 ('run_ctest', 'Run CTest with failure output (requires --allow-exec).', {}),
 ('list_ctest', 'List registered CTest tests (requires --allow-exec).', {}),
]
TOOL_SCHEMAS = [
 {'type': 'function', 'function': {
     'name': name, 'description': description,
     'parameters': {'type': 'object', 'properties': properties,
                    **({'required': ['path']} if name == 'read_file' else {}),
                    'additionalProperties': False}}}
 for name, description, properties in TOOLS
]
ALLOWED_TOOLS = {item[0] for item in TOOLS}
SOURCE_DIRS = {'src', 'include', 'tests', 'app'}
TOP_FILES = {'CMakeLists.txt', 'README.md', 'Jenkinsfile.ai'}
ALLOWED_SUFFIXES = {'.cpp', '.cc', '.c', '.h', '.hpp', '.hxx', '.txt', '.cmake', '.md'}
MAX_READ = 17000
MAX_OUTPUT = 11000

RESULT_FIELDS = {
    'tool',
    'arguments',
    'status',
    'exit_code',
    'stdout',
    'stderr',
    'duration_ms',
    'truncated',
    'error'
}


def validate_tool_result(result: dict) -> bool:
    return isinstance(result, dict) and RESULT_FIELDS <= result.keys()


def make_tool_result(
    tool,
    arguments,
    status,
    exit_code=None,
    stdout='',
    stderr='',
    duration_ms=0,
    truncated=False,
    error=''
):
    return {
        'tool': tool,
        'arguments': arguments,
        'status': status,
        'exit_code': exit_code,
        'stdout': stdout,
        'stderr': stderr,
        'duration_ms': duration_ms,
        'truncated': truncated,
        'error': error
    }

class ToolExecutor:
    def __init__(self, workspace: Path, allow_exec: bool = False):
        self.workspace = Path(workspace).resolve(strict=True)
        if not (self.workspace / 'CMakeLists.txt').is_file():
            raise ValueError('Workspace must contain CMakeLists.txt')
        self.allow_exec = allow_exec

    def safe_path(self, relative: str) -> Path:
        if not isinstance(relative, str) or not relative or '\\' in relative or '\x00' in relative:
            raise PermissionError('Invalid relative path')
        p = Path(relative)
        if p.is_absolute() or '..' in p.parts:
            raise PermissionError('Path outside workspace forbidden')
        allowed = (p.as_posix() in TOP_FILES or
                   (len(p.parts) >= 2 and p.parts[0] in SOURCE_DIRS and p.suffix.lower() in ALLOWED_SUFFIXES))
        if not allowed:
            raise PermissionError('File category not allowlisted')
        target = self.workspace / p
        if not target.resolve().is_relative_to(self.workspace):
            raise PermissionError('Symlink escapes workspace')
        cursor = self.workspace
        for part in p.parts:
            cursor /= part
            if cursor.is_symlink():
                raise PermissionError('Symlinks are not readable')
        return target

    def run_cmd(
        self,
        args: list[str],
        timeout: int,
        tool='command',
        arguments=None
    ) -> dict[str, Any]:

        start = time.perf_counter()

        try:
            result = subprocess.run(
                args,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                errors='replace',
                timeout=timeout,
                check=False
            )

            stdout = result.stdout
            stderr = result.stderr
            truncated = False

            if len(stdout) > MAX_OUTPUT:
                stdout = stdout[-MAX_OUTPUT:]
                truncated = True

            if len(stderr) > MAX_OUTPUT:
                stderr = stderr[-MAX_OUTPUT:]
                truncated = True

            status = (
                'OK'
                if result.returncode == 0
                else 'COMMAND_FAILED'
            )

            return make_tool_result(
                tool=tool,
                arguments=arguments or {},
                status=status,
                exit_code=result.returncode,
                stdout=stdout,
                stderr=stderr,
                duration_ms=int(
                    (time.perf_counter() - start) * 1000
                ),
                truncated=truncated
            )

        except FileNotFoundError as exc:
            return make_tool_result(
                tool=tool,
                arguments=arguments or {},
                status='NOT_FOUND',
                exit_code=127,
                duration_ms=int(
                    (time.perf_counter() - start) * 1000
                ),
                error=f'Missing command: {exc.filename}'
            )

        except subprocess.TimeoutExpired:
            return make_tool_result(
                tool=tool,
                arguments=arguments or {},
                status='TIMEOUT',
                exit_code=124,
                duration_ms=int(
                    (time.perf_counter() - start) * 1000
                ),
                error=f'Timeout after {timeout}s'
            )

    def execute(
        self,
        name: str,
        arguments: dict | None
    ) -> dict[str, Any]:

        start = time.perf_counter()
        args = arguments if arguments is not None else {}

        if not isinstance(args, dict):
            return make_tool_result(
                name,
                {},
                'INVALID_ARGUMENTS',
                duration_ms=int(
                    (time.perf_counter() - start) * 1000
                ),
                error='Tool arguments must be a JSON object'
            )

        if name not in ALLOWED_TOOLS:
            return make_tool_result(
                name,
                args,
                'INVALID_ARGUMENTS',
                duration_ms=int(
                    (time.perf_counter() - start) * 1000
                ),
                error=f'Unknown tool: {name}'
            )

        try:
            if name == 'list_files':
                files = sorted(
                    str(f.relative_to(self.workspace)).replace('\\', '/')
                    for folder in SOURCE_DIRS
                    if (self.workspace / folder).is_dir()
                    for f in (self.workspace / folder).rglob('*')
                    if f.is_file()
                    and not f.is_symlink()
                    and f.suffix.lower() in ALLOWED_SUFFIXES
                    and not any(
                        part in {'build', '.git', '__pycache__'}
                        for part in f.relative_to(self.workspace).parts
                    )
                )

                files.extend(
                    f
                    for f in TOP_FILES
                    if (self.workspace / f).is_file()
                )

                files = sorted(files)[:130]

                result = make_tool_result(
                    name,
                    args,
                    'OK',
                    stdout=json.dumps(files),
                    duration_ms=int(
                        (time.perf_counter() - start) * 1000
                    )
                )

                # zostawiamy dla kompatybilności starych testów
                result['files'] = files
                return result

            if name == 'read_file':
                target = self.safe_path(
                    args.get('path', '')
                )

                if not target.is_file():
                    return make_tool_result(
                        name,
                        args,
                        'NOT_FOUND',
                        duration_ms=int(
                            (time.perf_counter() - start) * 1000
                        ),
                        error='Requested file not found'
                    )

                content = target.read_text(
                    encoding='utf-8',
                    errors='replace'
                )

                truncated = len(content) > MAX_OUTPUT

                if truncated:
                    content = content[:MAX_OUTPUT]

                result = make_tool_result(
                    name,
                    args,
                    'OK',
                    stdout=content,
                    duration_ms=int(
                        (time.perf_counter() - start) * 1000
                    ),
                    truncated=truncated
                )

                result['path'] = str(
                    target.relative_to(self.workspace)
                ).replace('\\', '/')

                # kompatybilność ze starymi testami
                result['content'] = content

                return result

            if name == 'git_diff':
                return self.run_cmd(
                    [
                        'git',
                        'diff',
                        '--no-ext-diff',
                        '--',
                        'src',
                        'include',
                        'tests',
                        'app',
                        'CMakeLists.txt'
                    ],
                    20,
                    name,
                    args
                )

            if name == 'git_log':
                return self.run_cmd(
                    [
                        'git',
                        'log',
                        '-n',
                        '5',
                        '--oneline',
                        '--no-decorate'
                    ],
                    20,
                    name,
                    args
                )

            if not self.allow_exec:
                return make_tool_result(
                    name,
                    args,
                    'DENIED',
                    duration_ms=int(
                        (time.perf_counter() - start) * 1000
                    ),
                    error=(
                        'Execution denied: enable '
                        '--allow-exec for trusted code'
                    )
                )

            build = str(
                self.workspace / 'build'
            )

            commands = {
                'run_cmake_configure': (
                    [
                        'cmake',
                        '-S',
                        str(self.workspace),
                        '-B',
                        build
                    ],
                    120
                ),
                'run_cmake_build': (
                    [
                        'cmake',
                        '--build',
                        build,
                        '--config',
                        'Debug',
                        '--parallel',
                        '2'
                    ],
                    150
                ),
                'run_ctest': (
                    [
                        'ctest',
                        '--test-dir',
                        build,
                        '-C',
                        'Debug',
                        '--output-on-failure'
                    ],
                    150
                ),
                'list_ctest': (
                    [
                        'ctest',
                        '--test-dir',
                        build,
                        '-C',
                        'Debug',
                        '-N'
                    ],
                    30
                )
            }

            command, timeout = commands[name]

            return self.run_cmd(
                command,
                timeout,
                name,
                args
            )

        except PermissionError as exc:
            return make_tool_result(
                name,
                args,
                'INVALID_ARGUMENTS',
                duration_ms=int(
                    (time.perf_counter() - start) * 1000
                ),
                error=str(exc)
            )

        except (OSError, ValueError) as exc:
            return make_tool_result(
                name,
                args,
                'NOT_FOUND',
                duration_ms=int(
                    (time.perf_counter() - start) * 1000
                ),
                error=str(exc)
            )
