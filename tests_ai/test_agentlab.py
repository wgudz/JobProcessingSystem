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
from agentlab.tools import ToolExecutor, TOOL_SCHEMAS

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
        for name in ('read_file', 'run_ctest', 'git_diff'):
            self.assertIn(name, names)


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
        agent = run_agent(ROOT, self.ws, 'job-processing-triage', MockProvider(), max_steps=1)
        self.assertEqual(len(agent.events), 1)
        self.assertIn('MOCK', agent.report)

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


if __name__ == '__main__':
    unittest.main()
