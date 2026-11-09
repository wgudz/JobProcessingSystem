"""Ollama localhost chat or a deterministic MOCK (no language-model reasoning)."""
from __future__ import annotations
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class OllamaProvider:
    def __init__(self, model: str):
        self.model = model
        self.url = 'http://127.0.0.1:11434/api/chat'

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        body = {'model': self.model, 'messages': messages, 'tools': tools,
                'stream': False, 'think': False, 'options': {'temperature': 0}}
        req = Request(self.url, data=json.dumps(body).encode('utf-8'),
                      headers={'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=240) as response:
                data = json.load(response)
        except HTTPError as exc:
            raise RuntimeError(f'Ollama HTTP {exc.code}: check model name and ollama list') from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError('Local Ollama unreachable at 127.0.0.1:11434. Run ollama serve and ollama pull qwen3:4b.') from exc
        if not isinstance(data, dict) or not isinstance(data.get('message'), dict):
            raise RuntimeError('Ollama returned no assistant message')
        return data['message']


class MockProvider:
    """Tests the complete plumbing. Does not infer root causes or act as real AI."""
    def __init__(self):
        self.model = 'mock'
        self.calls = 0
        self.sequence = [
            ('list_files', {}),
            ('run_cmake_configure', {}),
            ('run_cmake_build', {}),
            ('run_ctest', {}),
            ('git_diff', {}),
            ('read_file', {'path': 'tests/thread_safe_queue_test.cpp'}),
            ('read_file', {'path': 'include/job_system/thread_safe_queue.h'}),
            ('read_file', {'path': 'src/statistics.cpp'}),
        ]

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        if tools and self.calls < len(self.sequence):
            name, args = self.sequence[self.calls]
            self.calls += 1
            return {'role': 'assistant', 'content': '', 'tool_calls': [
                {'type': 'function', 'function': {'name': name, 'arguments': args}}]}
        return {'role': 'assistant', 'content': (
            '## MOCK verification only\n\nFixed tool sequence executed. '
            'This is NOT an AI diagnosis. Check the Evidence section for actual CTest output '
            'and run --provider ollama to request a model-generated investigation.\n')}
