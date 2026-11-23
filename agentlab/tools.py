"""Read-only inspection and allowlisted build/test actions, never arbitrary shell."""
from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Any
import time
import json
import re
import os

TOOLS = [
    (
        'list_files',
        'List C++ sources, application, tests and CMake files.',
        {}
    ),
    (
        'read_file',
        'Read one allowlisted project file by repository-relative path.',
        {
            'path': {
                'type': 'string',
                'description': (
                    'Path under src/, include/, tests/ or app/, '
                    'e.g. include/job_system/thread_safe_queue.h'
                )
            }
        }
    ),
    (
        'search_code',
        'Search C++ source code for a symbol or phrase without returning entire files.',
        {
            'query': {
                'type': 'string',
                'description': 'Symbol or phrase to search for.'
            },
            'extensions': {
                'type': 'array',
                'items': {
                    'type': 'string'
                },
                'description': (
                    'Optional allowed file extensions, e.g. .cpp, .h.'
                )
            },
            'max_files': {
                'type': 'integer',
                'description': 'Maximum number of files to scan.'
            },
            'max_matches': {
                'type': 'integer',
                'description': 'Maximum number of matches to return.'
            },
            'directory': {
                'type': 'string',
                'enum': [
                    'src',
                    'include',
                    'tests',
                    'app'
                ],
                'description': (
                    'Optional allowlisted directory to search.'
                )
            }
        }
    ),
    (
        'git_diff',
        'Read unstaged Git source diff. Changes may be uncommitted.',
        {}
    ),
    (
        'git_status',
        'Read current branch, HEAD and working tree status.',
        {}
    ),
    (
        'git_show',
        'Read source diff for one exact commit SHA.',
        {
            'commit': {
                'type': 'string',
                'description': 'Full 40-character Git commit SHA.'
            }
        }
    ),
    (
        'git_log',
        'Inspect recent local commit summaries.',
        {}
    ),
    (
        'run_cmake_configure',
        'Configure CMake in build/ (requires --allow-exec).',
        {}
    ),
    (
        'run_cmake_build',
        'Build the project (requires --allow-exec).',
        {}
    ),
    (
        'run_ctest',
        'Run full CTest with failure output (requires --allow-exec).',
        {}
    ),
    (
        'list_ctest',
        'List registered CTest tests and detected build configuration.',
        {}
    ),
    (
        'run_selected_tests',
        'Run only selected registered CTest tests (requires --allow-exec).',
        {
            'tests': {
                'type': 'array',
                'items': {
                    'type': 'string'
                },
                'description': 'Registered CTest test names.'
            }
        }
    ),
]


TOOL_SCHEMAS = [
    {
        'type': 'function',
        'function': {
            'name': name,
            'description': description,
            'parameters': {
                'type': 'object',
                'properties': properties,
                **(
                    {'required': ['path']}
                    if name == 'read_file'
                    else {'required': ['query']}
                    if name == 'search_code'
                    else {'required': ['commit']}
                    if name == 'git_show'
                    else {'required': ['tests']}
                    if name == 'run_selected_tests' 
                    else {}
                ),
                'additionalProperties': False
            }
        }
    }
    for name, description, properties in TOOLS
]


ALLOWED_TOOLS = {item[0] for item in TOOLS}
SOURCE_DIRS = {'src', 'include', 'tests', 'app'}
TOP_FILES = {'CMakeLists.txt', 'README.md', 'Jenkinsfile.ai'}
ALLOWED_SUFFIXES = {'.cpp', '.cc', '.c', '.h', '.hpp', '.hxx', '.txt', '.cmake', '.md'}
MAX_READ = 17000
MAX_OUTPUT = 11000

SELECTED_TEST_TIMEOUT = 60
FULL_CTEST_TIMEOUT = 150
MAX_SELECTED_TESTS = 10

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

SEARCH_DIRS = ('src', 'include', 'tests', 'app')

SEARCH_EXTENSIONS = {
    '.cpp',
    '.h',
    '.hpp',
    '.cc',
    '.cxx'
}

MAX_SEARCH_FILE_SIZE = 250_000
SEARCH_TIMEOUT = 2.0

GIT_PATHS = [
    'src',
    'include',
    'tests',
    'app',
    'CMakeLists.txt'
]

COMMIT_RE = re.compile(r'^[0-9a-fA-F]{40}$')

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

    def safe_read_text(
        self,
        relative: str,
        max_size: int | None = None
    ) -> str:

        target = self.safe_path(relative)

        before = os.lstat(target)

        if os.path.islink(target):
            raise PermissionError(
                'Symlinks are not readable'
            )

        flags = os.O_RDONLY

        if hasattr(os, 'O_NOFOLLOW'):
            flags |= os.O_NOFOLLOW

        fd = os.open(
            target,
            flags
        )

        try:
            with os.fdopen(
                fd,
                'r',
                encoding='utf-8',
                errors='replace'
            ) as file:

                opened = os.fstat(
                    file.fileno()
                )

                after = os.lstat(target)

                if (
                    not os.path.samestat(before, opened)
                    or not os.path.samestat(opened, after)
                ):
                    raise PermissionError(
                        'File changed during safe read'
                    )

                if (
                    max_size is not None
                    and opened.st_size > max_size
                ):
                    raise ValueError(
                        'File is too large'
                    )

                return file.read()

        except:
            try:
                os.close(fd)
            except OSError:
                pass

            raise

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

    def search_code(self, arguments: dict) -> dict[str, Any]:
        start = time.perf_counter()

        query = arguments.get('query')
        extensions = arguments.get(
            'extensions',
            sorted(SEARCH_EXTENSIONS)
        )
        max_files = arguments.get('max_files', 30)
        max_matches = arguments.get('max_matches', 20)
        directory = arguments.get('directory')

        if not isinstance(query, str) or not query.strip():
            return make_tool_result(
                'search_code',
                arguments,
                'INVALID_ARGUMENTS',
                error='query must be a non-empty string'
            )

        if directory is not None and directory not in SEARCH_DIRS:
            return make_tool_result(
                'search_code',
                arguments,
                'INVALID_ARGUMENTS',
                error='directory is outside search allowlist'
            )

        if not isinstance(extensions, list):
            return make_tool_result(
                'search_code',
                arguments,
                'INVALID_ARGUMENTS',
                error='extensions must be a list'
            )

        normalized_extensions = set()

        for extension in extensions:
            if not isinstance(extension, str):
                return make_tool_result(
                    'search_code',
                    arguments,
                    'INVALID_ARGUMENTS',
                    error='invalid extension'
                )

            if not extension.startswith('.'):
                extension = '.' + extension

            normalized_extensions.add(
                extension.lower()
            )

        if not normalized_extensions <= SEARCH_EXTENSIONS:
            return make_tool_result(
                'search_code',
                arguments,
                'INVALID_ARGUMENTS',
                error='extension is not allowed'
            )

        if (
            not isinstance(max_files, int)
            or not 1 <= max_files <= 100
            or not isinstance(max_matches, int)
            or not 1 <= max_matches <= 50
        ):
            return make_tool_result(
                'search_code',
                arguments,
                'INVALID_ARGUMENTS',
                error='invalid search limits'
            )

        if directory:
            roots = [self.workspace / directory]
        else:
            roots = [
                self.workspace / name
                for name in SEARCH_DIRS
            ]

        files = []

        for root in roots:
            if not root.is_dir():
                continue

            for path in root.rglob('*'):
                try:
                    relative = path.relative_to(
                        self.workspace
                    ).as_posix()

                    verified = self.safe_path(
                        relative
                    )

                except (
                    PermissionError,
                    ValueError,
                    OSError
                ):
                    continue

                if not verified.is_file():
                    continue

                if (
                    verified.suffix.lower()
                    not in normalized_extensions
                ):
                    continue

                if any(
                    part in {
                        '.git',
                        'build',
                        '__pycache__'
                    }
                    for part in verified.relative_to(
                        self.workspace
                    ).parts
                ):
                    continue

                files.append(verified)

        files.sort(
            key=lambda path: str(path.relative_to(self.workspace))
        )

        matches = []
        scanned_files = 0
        truncated = False

        for path in files:
            if scanned_files >= max_files:
                truncated = True
                break

            if time.perf_counter() - start > SEARCH_TIMEOUT:
                truncated = True
                break

            relative = path.relative_to(
                self.workspace
            ).as_posix()

            try:
                text = self.safe_read_text(
                    relative,
                    MAX_SEARCH_FILE_SIZE
                )

            except (
                PermissionError,
                ValueError,
                FileNotFoundError,
                OSError
            ):
                continue

            scanned_files += 1

            lines = text.splitlines()

            for index, line in enumerate(lines):
                if query not in line:
                    continue

                context = line.strip()[:250]

                matches.append({
                    'path': str(
                        path.relative_to(self.workspace)
                    ).replace('\\', '/'),
                    'line': index + 1,
                    'context': context
                })

                if len(matches) >= max_matches:
                    truncated = True
                    break

            if len(matches) >= max_matches:
                break

        output = {
            'query': query,
            'matches': matches,
            'count': len(matches)
        }

        return make_tool_result(
            'search_code',
            arguments,
            'OK',
            stdout=json.dumps(
                output,
                ensure_ascii=False
            ),
            duration_ms=int(
                (time.perf_counter() - start) * 1000
            ),
            truncated=truncated
        )

    def git_status(self, arguments: dict) -> dict[str, Any]:
        start = time.perf_counter()

        branch = self.run_cmd(
            ['git', 'branch', '--show-current'],
            10,
            'git_status',
            arguments
        )

        if branch['status'] != 'OK':
            return branch

        head = self.run_cmd(
            ['git', 'rev-parse', 'HEAD'],
            10,
            'git_status',
            arguments
        )

        if head['status'] != 'OK':
            return head

        status = self.run_cmd(
            [
                'git',
                'status',
                '--porcelain=v1',
                '--untracked-files=all'
            ],
            10,
            'git_status',
            arguments
        )

        if status['status'] != 'OK':
            return status

        changes = []

        for line in status['stdout'].splitlines():
            if len(line) < 3:
                continue

            changes.append({
                'index': line[0],
                'worktree': line[1],
                'path': line[3:]
            })

        data = {
            'branch': branch['stdout'].strip() or '(detached)',
            'head': head['stdout'].strip(),
            'working_tree': changes
        }

        return make_tool_result(
            'git_status',
            arguments,
            'OK',
            stdout=json.dumps(
                data,
                ensure_ascii=False
            ),
            duration_ms=int(
                (time.perf_counter() - start) * 1000
            ),
            truncated=status['truncated']
        )


    def git_show(self, arguments: dict) -> dict[str, Any]:
        start = time.perf_counter()

        commit = arguments.get('commit')

        if (
            not isinstance(commit, str)
            or not COMMIT_RE.fullmatch(commit)
        ):
            return make_tool_result(
                'git_show',
                arguments,
                'INVALID_ARGUMENTS',
                error='commit must be a full 40-character SHA'
            )

        exists = self.run_cmd(
            [
                'git',
                'cat-file',
                '-e',
                commit + '^{commit}'
            ],
            10,
            'git_show',
            arguments
        )

        if exists['status'] != 'OK':
            return make_tool_result(
                'git_show',
                arguments,
                'INVALID_ARGUMENTS',
                error='Unknown commit'
            )

        ancestor = self.run_cmd(
            [
                'git',
                'merge-base',
                '--is-ancestor',
                commit,
                'HEAD'
            ],
            10,
            'git_show',
            arguments
        )

        if ancestor['exit_code'] != 0:
            return make_tool_result(
                'git_show',
                arguments,
                'INVALID_ARGUMENTS',
                error='Commit is outside current HEAD history'
            )

        parents = self.run_cmd(
            [
                'git',
                'rev-list',
                '--parents',
                '-n',
                '1',
                commit
            ],
            10,
            'git_show',
            arguments
        )

        if parents['status'] != 'OK':
            return parents

        parts = parents['stdout'].strip().split()

        base = parts[1] if len(parts) > 1 else None

        diff = self.run_cmd(
            [
                'git',
                'show',
                '--format=',
                '--no-ext-diff',
                '--no-renames',
                commit,
                '--',
                *GIT_PATHS
            ],
            20,
            'git_show',
            arguments
        )

        if diff['status'] != 'OK':
            return diff

        data = {
            'commit': commit,
            'base': base,
            'scope': GIT_PATHS,
            'diff': diff['stdout']
        }

        return make_tool_result(
            'git_show',
            arguments,
            'OK',
            stdout=json.dumps(
                data,
                ensure_ascii=False
            ),
            duration_ms=int(
                (time.perf_counter() - start) * 1000
            ),
            truncated=diff['truncated']
        )

    def detect_build_config(self):
        build = self.workspace / 'build'
        cache = build / 'CMakeCache.txt'

        if not build.is_dir() or not cache.is_file():
            return None

        text = cache.read_text(
            encoding='utf-8',
            errors='replace'
        )

        for line in text.splitlines():
            if line.startswith('CMAKE_BUILD_TYPE:STRING='):
                value = line.split('=', 1)[1].strip()

                if value:
                    return value

        for line in text.splitlines():
            if line.startswith('CMAKE_CONFIGURATION_TYPES:STRING='):
                configs = line.split('=', 1)[1].split(';')

                if 'Debug' in configs:
                    return 'Debug'

                if configs:
                    return configs[0]

        return ''


    def list_ctest(self, arguments: dict) -> dict[str, Any]:
        start = time.perf_counter()

        build = self.workspace / 'build'

        if not build.is_dir():
            return make_tool_result(
                'list_ctest',
                arguments,
                'NOT_FOUND',
                error='Build directory not found'
            )

        config = self.detect_build_config()

        if config is None:
            return make_tool_result(
                'list_ctest',
                arguments,
                'NOT_FOUND',
                error='Build configuration not found'
            )

        command = [
            'ctest',
            '--test-dir',
            str(build)
        ]

        if config:
            command += [
                '-C',
                config
            ]

        command.append('-N')

        result = self.run_cmd(
            command,
            30,
            'list_ctest',
            arguments
        )

        if result['status'] != 'OK':
            return result

        tests = []

        for line in result['stdout'].splitlines():
            match = re.search(
                r'Test\s+#\d+:\s+(.+)$',
                line
            )

            if match:
                tests.append(
                    match.group(1).strip()
                )

        data = {
            'build_dir': 'build',
            'configuration': config or 'single-config',
            'tests': tests
        }

        result['stdout'] = json.dumps(
            data,
            ensure_ascii=False
        )

        return result


    def run_selected_tests(
        self,
        arguments: dict
    ) -> dict[str, Any]:

        start = time.perf_counter()

        requested = arguments.get('tests')

        if (
            not isinstance(requested, list)
            or not requested
            or len(requested) > MAX_SELECTED_TESTS
            or not all(
                isinstance(name, str) and name
                for name in requested
            )
        ):
            return make_tool_result(
                'run_selected_tests',
                arguments,
                'INVALID_ARGUMENTS',
                error='tests must be a non-empty list of test names'
            )

        listed = self.list_ctest({})

        if listed['status'] != 'OK':
            return make_tool_result(
                'run_selected_tests',
                arguments,
                listed['status'],
                exit_code=listed['exit_code'],
                stderr=listed['stderr'],
                error=listed['error']
            )

        data = json.loads(
            listed['stdout']
        )

        available = set(
            data['tests']
        )

        for name in requested:
            if name not in available:
                return make_tool_result(
                    'run_selected_tests',
                    arguments,
                    'INVALID_ARGUMENTS',
                    error='Unknown CTest test: ' + name
                )

        build = str(
            self.workspace / 'build'
        )

        config = data['configuration']

        all_stdout = []
        all_stderr = []
        final_status = 'OK'
        final_exit_code = 0
        truncated = False

        for name in requested:
            command = [
                'ctest',
                '--test-dir',
                build
            ]

            if config != 'single-config':
                command += [
                    '-C',
                    config
                ]

            command += [
                '--output-on-failure',
                '-R',
                '^' + re.escape(name) + '$'
            ]

            result = self.run_cmd(
                command,
                SELECTED_TEST_TIMEOUT,
                'run_selected_tests',
                {'tests': [name]}
            )

            all_stdout.append(
                result['stdout']
            )

            all_stderr.append(
                result['stderr']
            )

            truncated = (
                truncated
                or result['truncated']
            )

            if result['status'] == 'TIMEOUT':
                return make_tool_result(
                    'run_selected_tests',
                    arguments,
                    'TIMEOUT',
                    exit_code=124,
                    stdout='\n'.join(all_stdout),
                    stderr='\n'.join(all_stderr),
                    duration_ms=int(
                        (time.perf_counter() - start) * 1000
                    ),
                    truncated=truncated,
                    error='Selected CTest timed out'
                )

            if result['status'] != 'OK':
                final_status = result['status']
                final_exit_code = result['exit_code']

        return make_tool_result(
            'run_selected_tests',
            arguments,
            final_status,
            exit_code=final_exit_code,
            stdout='\n'.join(all_stdout),
            stderr='\n'.join(all_stderr),
            duration_ms=int(
                (time.perf_counter() - start) * 1000
            ),
            truncated=truncated
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

                content = self.safe_read_text(
                    args.get('path', '')
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

            if name == 'search_code':
                return self.search_code(args)

            if name == 'git_status':
                return self.git_status(args)

            if name == 'git_show':
                return self.git_show(args)

            if name == 'git_diff':
                paths = [
                    'src',
                    'include',
                    'tests',
                    'app',
                    'CMakeLists.txt'
                ]

                unstaged = self.run_cmd(
                    [
                        'git',
                        'diff',
                        '--no-ext-diff',
                        '--',
                        *paths
                    ],
                    20,
                    name,
                    args
                )

                staged = self.run_cmd(
                    [
                        'git',
                        'diff',
                        '--cached',
                        '--no-ext-diff',
                        '--',
                        *paths
                    ],
                    20,
                    name,
                    args
                )

                ok = (
                    unstaged['status'] == 'OK'
                    and staged['status'] == 'OK'
                )

                return make_tool_result(
                    name,
                    args,
                    'OK' if ok else 'COMMAND_FAILED',
                    exit_code=0 if ok else 1,
                    stdout=json.dumps(
                        {
                            'unstaged': unstaged['stdout'],
                            'staged': staged['stdout']
                        },
                        ensure_ascii=False
                    ),
                    stderr=(
                        unstaged['stderr']
                        + staged['stderr']
                    ),
                    truncated=(
                        unstaged['truncated']
                        or staged['truncated']
                    )
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
            if name == 'list_ctest':
                return self.list_ctest(args)

            if name == 'run_selected_tests':
                return self.run_selected_tests(args)

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
                    FULL_CTEST_TIMEOUT
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
