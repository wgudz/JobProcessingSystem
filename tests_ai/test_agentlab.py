"""Offline unit tests: Skills, allowlist, provider protocol, tool loop, and reporting."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentlab.providers import MockProvider, OllamaProvider
from agentlab.runner import run_agent, save_report
from agentlab.skill_loader import load_skill
from agentlab.tools import (
    ToolExecutor,
    TOOL_SCHEMAS,
    validate_tool_result,
    make_tool_result
)
from agentlab.cli import main

from urllib.error import HTTPError

import subprocess

ROOT = Path(__file__).resolve().parent.parent


class BaseCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name)
        (self.ws / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.20)\nproject(test NONE)\nenable_testing()\nadd_test(NAME pass_test COMMAND ${CMAKE_COMMAND} -E true)\n')
        for name in ('src', 'include/job_system', 'tests'):
            (self.ws / name).mkdir(parents=True, exist_ok=True)
        (self.ws / 'src/statistics.cpp').write_text('++cancelled_;\n')
        (self.ws / 'include/job_system/thread_safe_queue.h').write_text('template<class T> class ThreadSafeQueue {};\n')
        (self.ws / 'tests/thread_safe_queue_test.cpp').write_text('int main(){return 0;}\n')

class CliTest(BaseCase):
    def test_issue_id_requires_issue_file(self):
        stderr = io.StringIO()

        with patch('sys.stderr', stderr):
            with self.assertRaises(SystemExit) as context:
                main(['--issue-id', 'BUG-001'])

        self.assertEqual(context.exception.code, 2)
        self.assertIn(
            '--issue-id and --issue-file must be used together',
            stderr.getvalue()
        )
    def test_invalid_issue_json_is_rejected(self):
        issue_file = self.ws / 'bad.json'
        issue_file.write_text(
            '{"title": "Błąd", "symptoms": }',
            encoding='utf-8'
        )

        report = self.ws / 'report.md'
        stderr = io.StringIO()

        with patch('sys.stderr', stderr):
            with self.assertRaises(SystemExit) as context:
                main([
                    '--workspace', str(self.ws),
                    '--issue-id', 'BAD-001',
                    '--issue-file', 'bad.json',
                    '--report', str(report)
                ])

        self.assertEqual(context.exception.code, 2)
        self.assertIn('Invalid JSON in issue file', stderr.getvalue())
        self.assertFalse(report.exists())

    def test_issue_file_outside_workspace_is_rejected(self):
        outside_file = Path(self.tmp.name).parent / 'outside-issue.json'
        outside_file.write_text(
            '{"title":"X","symptoms":"Y","expected":"Z"}',
            encoding='utf-8'
        )
        self.addCleanup(lambda: outside_file.unlink(missing_ok=True))

        stderr = io.StringIO()

        with patch('sys.stderr', stderr):
            with self.assertRaises(SystemExit) as context:
                main([
                    '--workspace', str(self.ws),
                    '--issue-id', 'OUTSIDE-001',
                    '--issue-file', str(outside_file)
                ])

        self.assertEqual(context.exception.code, 2)
        self.assertIn(
            '--issue-file must be inside workspace',
            stderr.getvalue()
        )

    def test_valid_issue_runs_with_mock(self):
        issue_file = self.ws / 'issue.json'
        issue_file.write_text(
            json.dumps({
                'title': 'Worker shutdown problem',
                'symptoms': 'worker_test hangs',
                'expected': 'Worker should stop',
                'suspected_tests': ['worker_test']
            }),
            encoding='utf-8'
        )

        report = self.ws / 'report.md'
        output_json = self.ws / 'report.json'
        stdout = io.StringIO()

        with patch('sys.stdout', stdout):
            result = main([
                '--provider', 'mock',
                '--workspace', str(self.ws),
                '--issue-id', 'BUG-001',
                '--issue-file', 'issue.json',
                '--report', str(report),
                '--output-json', str(output_json)
            ])

        self.assertEqual(result, 0)
        self.assertTrue(report.exists())
        self.assertTrue(output_json.exists())

        data = json.loads(output_json.read_text(encoding='utf-8'))
        self.assertEqual(data['issue_id'], 'BUG-001')

    def test_missing_workspace_is_rejected(self):
        missing_workspace = self.ws / 'does-not-exist'
        stderr = io.StringIO()

        with patch('sys.stderr', stderr):
            with self.assertRaises(SystemExit) as context:
                main([
                    '--workspace', str(missing_workspace),
                    '--issue-id', 'BUG-001',
                    '--issue-file', 'issue.json'
                ])

        self.assertEqual(context.exception.code, 2)
        self.assertIn(
            'Workspace directory not found',
            stderr.getvalue()
    )

    def test_search_code_through_cli(self):
        path = self.ws / 'src/example.cpp'

        path.write_text(
            'void waitAndPop();\n',
            encoding='utf-8'
        )

        class SearchProvider:
            def __init__(self):
                self.calls = 0

            def chat(self, messages, tools):
                self.calls += 1

                if self.calls == 1:
                    return {
                        'content': '',
                        'tool_calls': [{
                            'function': {
                                'name': 'search_code',
                                'arguments': {
                                    'query': 'waitAndPop'
                                }
                            }
                        }]
                    }

                return {
                    'content': 'Search completed.'
                }

        report = self.ws / 'search-report.md'

        with patch(
            'agentlab.cli.MockProvider',
            return_value=SearchProvider()
        ):
            result = main([
                '--provider', 'mock',
                '--workspace', str(self.ws),
                '--report', str(report)
            ])

        self.assertEqual(result, 0)
        self.assertIn(
            'search_code',
            report.read_text(encoding='utf-8')
        )

class SafeToolsTest(BaseCase):
    def test_list_files_works(self):
        paths = ToolExecutor(self.ws).execute('list_files', {})['files']
        self.assertIn('src/statistics.cpp', paths)
        self.assertIn('include/job_system/thread_safe_queue.h', paths)

    def test_read_allowed_file(self):
        answer = ToolExecutor(self.ws).execute('read_file', {'path': 'src/statistics.cpp'})
        self.assertEqual(answer['content'], '++cancelled_;\n')

    def test_reject_absolute_paths_and_traversal(self):
        for path in ('../../secret.txt', '/etc/passwd', '../CMakeLists.txt', r'..\secret', 'build/CMakeCache.txt'):
            with self.subTest(path=path):
                self.assertIn('error', ToolExecutor(self.ws).execute('read_file', {'path': path}))

    def test_reject_non_strings_and_bad_arguments(self):
        for arguments in ({'path': 33}, {'path': {'a': 1}}, ['src/statistics.cpp']):
            with self.subTest(arguments=arguments):
                self.assertIn('error', ToolExecutor(self.ws).execute('read_file', arguments))

    def test_reject_arbitrary_commands(self):
        self.assertIn('Unknown tool', ToolExecutor(self.ws, True).execute('execute_shell', {'command': 'echo hi'})['error'])

    def test_execute_requires_consent(self):
        for name in ('run_cmake_configure', 'run_cmake_build', 'run_ctest', 'list_ctest'):
            with self.subTest(name=name):
                self.assertIn('Execution denied', ToolExecutor(self.ws).execute(name, {})['error'])

    def test_symlink_blocked(self):
        target = self.ws / 'src' / 'link.cpp'
        try:
            target.symlink_to(self.ws / 'CMakeLists.txt')
        except (OSError, NotImplementedError):
            self.skipTest('Cannot create symlinks')
        self.assertIn('error', ToolExecutor(self.ws).execute('read_file', {'path': 'src/link.cpp'}))

    def test_command_not_found(self):
        self.assertEqual(ToolExecutor(self.ws).run_cmd(['definitely-no-such-executable-12345678'], 1)['exit_code'], 127)

    def test_schema_contains_expected_tools(self):
        names = [item['function']['name'] for item in TOOL_SCHEMAS]
        self.assertEqual(len(names), len(set(names)))
        for name in (
            'read_file',
            'run_ctest',
            'git_diff',
            'git_status',
            'git_show'
        ):
            self.assertIn(name, names)

    def test_normalized_command_success(self):
        result = ToolExecutor(self.ws).run_cmd(
            ['cmake', '-E', 'true'],
            5
        )

        self.assertTrue(validate_tool_result(result))
        self.assertEqual(result['status'], 'OK')
        self.assertEqual(result['exit_code'], 0)


    def test_normalized_command_failure(self):
        result = ToolExecutor(self.ws).run_cmd(
            ['cmake', '-E', 'false'],
            5
        )

        self.assertTrue(validate_tool_result(result))
        self.assertEqual(
            result['status'],
            'COMMAND_FAILED'
        )
        self.assertEqual(result['exit_code'], 1)


    def test_normalized_command_not_found(self):
        result = ToolExecutor(self.ws).run_cmd(
            ['definitely-no-such-command-123456'],
            5
        )

        self.assertTrue(validate_tool_result(result))
        self.assertEqual(result['status'], 'NOT_FOUND')
        self.assertEqual(result['exit_code'], 127)


    def test_normalized_command_timeout(self):
        with patch(
            'agentlab.tools.subprocess.run',
            side_effect=subprocess.TimeoutExpired(
                ['fake'],
                1
            )
        ):
            result = ToolExecutor(self.ws).run_cmd(
                ['fake'],
                1
            )

        self.assertTrue(validate_tool_result(result))
        self.assertEqual(result['status'], 'TIMEOUT')
        self.assertEqual(result['exit_code'], 124)

    def test_search_code_mark_statistics_recorded(self):
        path = self.ws / 'src/statistics.cpp'

        path.write_text(
            'bool markStatisticsRecorded();\n',
            encoding='utf-8'
        )

        result = ToolExecutor(self.ws).execute(
            'search_code',
            {
                'query': 'markStatisticsRecorded'
            }
        )

        self.assertEqual(result['status'], 'OK')

        data = json.loads(result['stdout'])

        self.assertEqual(data['count'], 1)
        self.assertEqual(
            data['matches'][0]['path'],
            'src/statistics.cpp'
        )


    def test_search_code_wait_and_pop(self):
        path = (
            self.ws
            / 'include/job_system/thread_safe_queue.h'
        )

        path.write_text(
            'std::optional<T> waitAndPop();\n',
            encoding='utf-8'
        )

        result = ToolExecutor(self.ws).execute(
            'search_code',
            {
                'query': 'waitAndPop'
            }
        )

        data = json.loads(result['stdout'])

        self.assertEqual(data['count'], 1)
        self.assertEqual(
            data['matches'][0]['line'],
            1
        )


    def test_search_code_no_match(self):
        result = ToolExecutor(self.ws).execute(
            'search_code',
            {
                'query': 'DefinitelyFakeSymbol123'
            }
        )

        data = json.loads(result['stdout'])

        self.assertEqual(result['status'], 'OK')
        self.assertEqual(data['count'], 0)
        self.assertEqual(data['matches'], [])


    def test_search_code_rejects_outside_directory(self):
        result = ToolExecutor(self.ws).execute(
            'search_code',
            {
                'query': 'test',
                'directory': '../'
            }
        )

        self.assertEqual(
            result['status'],
            'INVALID_ARGUMENTS'
        )


    def test_search_code_limits_matches(self):
        path = self.ws / 'src/many.cpp'

        path.write_text(
            'return 1;\n'
            'return 2;\n'
            'return 3;\n'
            'return 4;\n',
            encoding='utf-8'
        )

        result = ToolExecutor(self.ws).execute(
            'search_code',
            {
                'query': 'return',
                'max_matches': 2
            }
        )

        data = json.loads(result['stdout'])

        self.assertEqual(data['count'], 2)
        self.assertTrue(result['truncated'])

class GitToolsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        self.ws = Path(self.tmp.name)

        (self.ws / 'src').mkdir()

        (self.ws / 'CMakeLists.txt').write_text(
            'cmake_minimum_required(VERSION 3.20)\n',
            encoding='utf-8'
        )

        (self.ws / 'src/example.cpp').write_text(
            'int value = 1;\n',
            encoding='utf-8'
        )

        subprocess.run(
            ['git', 'init'],
            cwd=self.ws,
            check=True,
            capture_output=True
        )

        subprocess.run(
            [
                'git',
                'config',
                'user.email',
                'test@example.com'
            ],
            cwd=self.ws,
            check=True
        )

        subprocess.run(
            [
                'git',
                'config',
                'user.name',
                'Test User'
            ],
            cwd=self.ws,
            check=True
        )

        subprocess.run(
            ['git', 'add', '.'],
            cwd=self.ws,
            check=True
        )

        subprocess.run(
            [
                'git',
                'commit',
                '-m',
                'initial'
            ],
            cwd=self.ws,
            check=True,
            capture_output=True
        )

        self.executor = ToolExecutor(self.ws)

    def git(self, *args):
        return subprocess.run(
            ['git', *args],
            cwd=self.ws,
            check=True,
            capture_output=True,
            text=True
        ).stdout.strip()

    def test_git_status_clean_head(self):
        result = self.executor.execute(
            'git_status',
            {}
        )

        data = json.loads(result['stdout'])

        self.assertEqual(result['status'], 'OK')
        self.assertEqual(
            data['head'],
            self.git('rev-parse', 'HEAD')
        )
        self.assertEqual(
            data['working_tree'],
            []
        )

    def test_git_status_uncommitted_change(self):
        (self.ws / 'src/example.cpp').write_text(
            'int value = 2;\n',
            encoding='utf-8'
        )

        result = self.executor.execute(
            'git_status',
            {}
        )

        data = json.loads(result['stdout'])

        self.assertEqual(
            data['working_tree'][0]['worktree'],
            'M'
        )
        self.assertEqual(
            data['working_tree'][0]['path'],
            'src/example.cpp'
        )

    def test_git_status_staged_change(self):
        (self.ws / 'src/example.cpp').write_text(
            'int value = 2;\n',
            encoding='utf-8'
        )

        self.git('add', 'src/example.cpp')

        result = self.executor.execute(
            'git_status',
            {}
        )

        data = json.loads(result['stdout'])

        self.assertEqual(
            data['working_tree'][0]['index'],
            'M'
        )
        self.assertEqual(
            data['working_tree'][0]['worktree'],
            ' '
        )

    def test_git_show_new_commit(self):
        old_head = self.git(
            'rev-parse',
            'HEAD'
        )

        (self.ws / 'src/example.cpp').write_text(
            'int value = 2;\n',
            encoding='utf-8'
        )

        self.git('add', 'src/example.cpp')
        self.git('commit', '-m', 'change value')

        new_head = self.git(
            'rev-parse',
            'HEAD'
        )

        result = self.executor.execute(
            'git_show',
            {
                'commit': new_head
            }
        )

        data = json.loads(result['stdout'])

        self.assertEqual(result['status'], 'OK')
        self.assertEqual(data['commit'], new_head)
        self.assertEqual(data['base'], old_head)
        self.assertIn(
            'src/example.cpp',
            data['diff']
        )

    def test_git_show_rejects_invalid_reference(self):
        result = self.executor.execute(
            'git_show',
            {
                'commit': '--stat'
            }
        )

        self.assertEqual(
            result['status'],
            'INVALID_ARGUMENTS'
        )

        result = self.executor.execute(
            'git_show',
            {
                'commit': '0' * 40
            }
        )

        self.assertEqual(
            result['status'],
            'INVALID_ARGUMENTS'
        )

class SkillTest(unittest.TestCase):
    def test_skill_loaded(self):
        text = load_skill(ROOT / 'skills', 'job-processing-triage')
        self.assertIn('name: job-processing-triage', text)
        self.assertIn('run_ctest', text)
        self.assertIn('thread_safe_queue.h', text)

    def test_invalid_names(self):
        for name in ('../../secret', '../', 'C:\\Windows'):
            with self.assertRaises(ValueError):
                load_skill(ROOT / 'skills', name)

    def test_missing_entry(self):
        with self.assertRaises(FileNotFoundError):
            load_skill(ROOT / 'skills', 'nonexistent')

    def test_bad_frontmatter(self):
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp) / 'wrong'
            d.mkdir()
            (d / 'SKILL.md').write_text('no yaml')
            with self.assertRaises(ValueError):
                load_skill(Path(temp), 'wrong')


class AgentTest(BaseCase):
    def test_mock_runs_and_reports(self):
        agent = run_agent(ROOT, self.ws, 'job-processing-triage', MockProvider(), allow_exec=False, max_steps=12)
        self.assertEqual(len(agent.events), 8)
        self.assertEqual(agent.events[0]['tool'], 'list_files')
        self.assertIn('Execution denied', agent.events[3]['result']['error'])
        self.assertIn('MOCK', agent.report)
        dest = self.ws / 'report.md'
        save_report(agent, dest, self.ws, 'job-processing-triage')
        text = dest.read_text()
        self.assertIn('## Evidence', text)
        self.assertIn('run_ctest', text)

    def test_cannot_use_unapproved_tool(self):
        class BadModel:
            def __init__(self): self.counter = 0
            def chat(self, messages, tools):
                self.counter += 1
                if self.counter == 1:
                    return {'role': 'assistant', 'content': '', 'tool_calls': [
                        {'function': {'name': 'delete_all_files', 'arguments': {}}}]}
                return {'role': 'assistant', 'content': 'Denied'}
        agent = run_agent(ROOT, self.ws, 'job-processing-triage', BadModel())
        self.assertIn('Unknown tool', agent.events[0]['result']['error'])

    def test_respects_step_limit(self):
        agent = run_agent(
            ROOT,
            self.ws,
            'job-processing-triage',
            MockProvider(),
            max_steps=1
        )

        self.assertEqual(len(agent.events), 1)
        self.assertEqual(agent.status, 'BLOCKED')
        self.assertEqual(agent.termination_reason, 'max_steps_reached')
        self.assertEqual(agent.steps, 1)
        self.assertEqual(agent.tool_calls, 1)
        self.assertIn('Analysis incomplete', agent.report)

    def test_multiple_tool_calls(self):
        class Multi:
            def __init__(self): self.n = 0
            def chat(self, messages, tools):
                self.n += 1
                if self.n == 1:
                    return {'role': 'assistant', 'tool_calls': [
                        {'function': {'name': 'list_files', 'arguments': '{}'}},
                        {'function': {'name': 'read_file', 'arguments': {'path': 'CMakeLists.txt'}}}]}
                return {'role': 'assistant', 'content': 'Done'}
        agent = run_agent(ROOT, self.ws, 'job-processing-triage', Multi())
        self.assertEqual(len(agent.events), 2)
        self.assertEqual(agent.report, 'Done')

    def test_report_includes_model_name(self):
        class Local:
            model = 'local-test'
            def chat(self, messages, tools): return {'role': 'assistant', 'content': 'Summary'}
        agent = run_agent(ROOT, self.ws, 'job-processing-triage', Local())
        dest = self.ws / 'report.md'
        save_report(agent, dest, self.ws, 'job-processing-triage')
        self.assertIn('local-test', dest.read_text())

    def test_tools_do_not_accept_mutation_by_model(self):
        executor = ToolExecutor(self.ws, allow_exec=True)
        for cmd in ('git_commit', 'git_push', 'write_file', 'delete_file', 'run_command'):
            self.assertIn('Unknown tool', executor.execute(cmd, {})['error'])

    def test_completed_after_collecting_evidence(self):
        class Provider:
            def __init__(self):
                self.calls = 0

            def chat(self, messages, tools):
                self.calls += 1

                if self.calls == 1:
                    return {
                        'content': '',
                        'tool_calls': [{
                            'function': {
                                'name': 'list_files',
                                'arguments': {}
                            }
                        }]
                    }

                return {
                    'content': 'Diagnosis completed.'
                }

        agent = run_agent(
            ROOT,
            self.ws,
            'job-processing-triage',
            Provider()
        )

        self.assertEqual(agent.status, 'COMPLETED')
        self.assertEqual(agent.termination_reason, 'final_answer')
        self.assertEqual(agent.steps, 2)
        self.assertEqual(agent.tool_calls, 1)


    def test_repeated_tool_call_is_blocked(self):
        class Provider:
            def chat(self, messages, tools):
                return {
                    'content': '',
                    'tool_calls': [{
                        'function': {
                            'name': 'list_files',
                            'arguments': {}
                        }
                    }]
                }

        agent = run_agent(
            ROOT,
            self.ws,
            'job-processing-triage',
            Provider(),
            max_steps=10
        )

        self.assertEqual(agent.status, 'BLOCKED')
        self.assertEqual(
            agent.termination_reason,
            'repeated_tool_call'
        )
        self.assertEqual(agent.tool_calls, 3)


    def test_empty_final_response_is_blocked(self):
        class Provider:
            def __init__(self):
                self.calls = 0

            def chat(self, messages, tools):
                self.calls += 1

                if self.calls == 1:
                    return {
                        'content': '',
                        'tool_calls': [{
                            'function': {
                                'name': 'list_files',
                                'arguments': {}
                            }
                        }]
                    }

                return {
                    'content': ''
                }

        agent = run_agent(
            ROOT,
            self.ws,
            'job-processing-triage',
            Provider()
        )

        self.assertEqual(agent.status, 'BLOCKED')
        self.assertEqual(
            agent.termination_reason,
            'empty_final_response'
        )


    def test_provider_error_is_failed(self):
        class Provider:
            def chat(self, messages, tools):
                raise RuntimeError('provider unavailable')

        agent = run_agent(
            ROOT,
            self.ws,
            'job-processing-triage',
            Provider()
        )

        self.assertEqual(agent.status, 'FAILED')
        self.assertEqual(
            agent.termination_reason,
            'provider_error'
        )


class ProviderTest(unittest.TestCase):
    def test_local_host_and_tools(self):
        response = io.BytesIO(json.dumps({'message': {'role': 'assistant', 'content': 'PASS'}}).encode())
        with patch('agentlab.providers.urlopen', return_value=response) as fn:
            data = OllamaProvider('qwen3:4b').chat([{'role': 'user', 'content': 'hi'}], TOOL_SCHEMAS)
        self.assertEqual(data['content'], 'PASS')
        request = fn.call_args.args[0]
        self.assertEqual(request.full_url, 'http://127.0.0.1:11434/api/chat')
        payload = json.loads(request.data)
        self.assertFalse(payload['stream'])
        self.assertEqual(payload['model'], 'qwen3:4b')
    def test_timeout(self):
        with patch(
            'agentlab.providers.urlopen',
            side_effect=TimeoutError()
        ) as fn:
            with self.assertRaisesRegex(
                RuntimeError,
                'Ollama timeout'
            ):
                OllamaProvider(
                    'qwen3:4b',
                    retries=1
                ).chat([], [])

        self.assertEqual(fn.call_count, 2)


    def test_http_404(self):
        error = HTTPError(
            'http://127.0.0.1',
            404,
            'Not Found',
            None,
            None
        )

        with patch(
            'agentlab.providers.urlopen',
            side_effect=error
        ) as fn:
            with self.assertRaisesRegex(
                RuntimeError,
                'Ollama HTTP 404'
            ):
                OllamaProvider('qwen3:4b').chat([], [])

        self.assertEqual(fn.call_count, 1)


    def test_http_500_is_retried(self):
        error = HTTPError(
            'http://127.0.0.1',
            500,
            'Server Error',
            None,
            None
        )

        with patch(
            'agentlab.providers.urlopen',
            side_effect=error
        ) as fn:
            with self.assertRaisesRegex(
                RuntimeError,
                'Ollama HTTP 500'
            ):
                OllamaProvider(
                    'qwen3:4b',
                    retries=1
                ).chat([], [])

        self.assertEqual(fn.call_count, 2)


    def test_empty_response(self):
        response = io.BytesIO(b'')

        with patch(
            'agentlab.providers.urlopen',
            return_value=response
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                'empty response'
            ):
                OllamaProvider('qwen3:4b').chat([], [])


    def test_invalid_json(self):
        response = io.BytesIO(b'{broken json')

        with patch(
            'agentlab.providers.urlopen',
            return_value=response
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                'invalid JSON'
            ):
                OllamaProvider('qwen3:4b').chat([], [])


    def test_missing_message(self):
        response = io.BytesIO(
            json.dumps({}).encode()
        )

        with patch(
            'agentlab.providers.urlopen',
            return_value=response
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                'missing message'
            ):
                OllamaProvider('qwen3:4b').chat([], [])


    def test_invalid_tool_calls(self):
        response = io.BytesIO(
            json.dumps({
                'message': {
                    'content': '',
                    'tool_calls': [
                        {'wrong': 'format'}
                    ]
                }
            }).encode()
        )

        with patch(
            'agentlab.providers.urlopen',
            return_value=response
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                'invalid tool_calls'
            ):
                OllamaProvider('qwen3:4b').chat([], [])

class CTestSelectionTest(BaseCase):
    def setUp(self):
        super().setUp()

        self.executor = ToolExecutor(
            self.ws,
            allow_exec=True
        )

    def listed_tests(self):
        return make_tool_result(
            'list_ctest',
            {},
            'OK',
            exit_code=0,
            stdout=json.dumps({
                'build_dir': 'build',
                'configuration': 'Debug',
                'tests': [
                    'thread_safe_queue_test',
                    'statistics_test',
                    'worker_pool_test'
                ]
            })
        )

    def test_known_selected_test(self):
        with patch.object(
            self.executor,
            'list_ctest',
            return_value=self.listed_tests()
        ):
            with patch.object(
                self.executor,
                'run_cmd',
                return_value=make_tool_result(
                    'run_selected_tests',
                    {},
                    'OK',
                    exit_code=0,
                    stdout='Passed'
                )
            ):
                result = self.executor.execute(
                    'run_selected_tests',
                    {
                        'tests': [
                            'thread_safe_queue_test'
                        ]
                    }
                )

        self.assertEqual(
            result['status'],
            'OK'
        )

    def test_unknown_selected_test(self):
        with patch.object(
            self.executor,
            'list_ctest',
            return_value=self.listed_tests()
        ):
            result = self.executor.execute(
                'run_selected_tests',
                {
                    'tests': [
                        'not_a_real_test'
                    ]
                }
            )

        self.assertEqual(
            result['status'],
            'INVALID_ARGUMENTS'
        )

    def test_list_ctest_without_build(self):
        result = self.executor.execute(
            'list_ctest',
            {}
        )

        self.assertEqual(
            result['status'],
            'NOT_FOUND'
        )

    def test_selected_test_timeout(self):
        with patch.object(
            self.executor,
            'list_ctest',
            return_value=self.listed_tests()
        ):
            with patch.object(
                self.executor,
                'run_cmd',
                return_value=make_tool_result(
                    'run_selected_tests',
                    {},
                    'TIMEOUT',
                    exit_code=124,
                    error='Timeout'
                )
            ):
                result = self.executor.execute(
                    'run_selected_tests',
                    {
                        'tests': [
                            'statistics_test'
                        ]
                    }
                )

        self.assertEqual(
            result['status'],
            'TIMEOUT'
        )

    def test_selected_test_failed(self):
        with patch.object(
            self.executor,
            'list_ctest',
            return_value=self.listed_tests()
        ):
            with patch.object(
                self.executor,
                'run_cmd',
                return_value=make_tool_result(
                    'run_selected_tests',
                    {},
                    'COMMAND_FAILED',
                    exit_code=8,
                    stdout='FAILED'
                )
            ):
                result = self.executor.execute(
                    'run_selected_tests',
                    {
                        'tests': [
                            'worker_pool_test'
                        ]
                    }
                )

        self.assertEqual(
            result['status'],
            'COMMAND_FAILED'
        )
        self.assertEqual(
            result['exit_code'],
            8
        )

    def test_full_ctest_green(self):
        with patch.object(
            self.executor,
            'run_cmd',
            return_value=make_tool_result(
                'run_ctest',
                {},
                'OK',
                exit_code=0,
                stdout='100% tests passed'
            )
        ) as run:
            result = self.executor.execute(
                'run_ctest',
                {}
            )

        self.assertEqual(
            result['status'],
            'OK'
        )

        command = run.call_args.args[0]

        self.assertIn(
            '--output-on-failure',
            command
        )
        self.assertNotIn(
            '-R',
            command
        )
        
if __name__ == '__main__':
    unittest.main()
