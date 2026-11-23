"""Ollama localhost chat or a deterministic MOCK (no language-model reasoning)."""
from __future__ import annotations
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


MAX_INPUT_BYTES = 100_000


class OllamaProvider:
    def __init__(
        self,
        model: str,
        host='http://127.0.0.1:11434',
        timeout=240,
        retries=1
    ):
        self.model = model
        self.host = host.rstrip('/')
        self.url = self.host + '/api/chat'
        self.timeout = timeout
        self.retries = retries

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        body = {
            'model': self.model,
            'messages': messages,
            'tools': tools,
            'stream': False,
            'think': False,
            'options': {'temperature': 0}
        }

        payload = json.dumps(body).encode('utf-8')

        if len(payload) > MAX_INPUT_BYTES:
            raise RuntimeError('Ollama input too large')

        req = Request(
            self.url,
            data=payload,
            headers={'Content-Type': 'application/json'}
        )

        data = None

        for attempt in range(self.retries + 1):
            try:
                with urlopen(req, timeout=self.timeout) as response:
                    raw = response.read()

                if not raw:
                    raise RuntimeError('Ollama returned an empty response')

                try:
                    data = json.loads(raw.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    raise RuntimeError(
                        'Ollama returned invalid JSON'
                    ) from exc

                break

            except HTTPError as exc:
                if 400 <= exc.code < 500:
                    raise RuntimeError(
                        f'Ollama HTTP {exc.code}: request rejected'
                    ) from exc

                if 500 <= exc.code < 600:
                    if attempt < self.retries:
                        continue

                    raise RuntimeError(
                        f'Ollama HTTP {exc.code}: server error'
                    ) from exc

                raise RuntimeError(
                    f'Ollama HTTP {exc.code}'
                ) from exc

            except TimeoutError as exc:
                if attempt < self.retries:
                    continue

                raise RuntimeError(
                    'Ollama timeout'
                ) from exc

            except URLError as exc:
                if attempt < self.retries:
                    continue

                raise RuntimeError(
                    'Ollama connection error'
                ) from exc

        if not isinstance(data, dict):
            raise RuntimeError(
                'Ollama returned invalid response'
            )

        message = data.get('message')

        if not isinstance(message, dict):
            raise RuntimeError(
                'Ollama response missing message'
            )

        tool_calls = message.get('tool_calls')

        if tool_calls is not None:
            if not isinstance(tool_calls, list):
                raise RuntimeError(
                    'Ollama returned invalid tool_calls'
                )

            for call in tool_calls:
                if not isinstance(call, dict):
                    raise RuntimeError(
                        'Ollama returned invalid tool_calls'
                    )

                function = call.get('function')

                if not isinstance(function, dict):
                    raise RuntimeError(
                        'Ollama returned invalid tool_calls'
                    )

                if not isinstance(function.get('name'), str):
                    raise RuntimeError(
                        'Ollama returned invalid tool_calls'
                    )

                arguments = function.get('arguments', {})

                if not isinstance(arguments, (dict, str)):
                    raise RuntimeError(
                        'Ollama returned invalid tool_calls'
                    )

        content = message.get('content') or ''

        if '</think>' in content:
            content = (
                content
                .rsplit('</think>', 1)[1]
                .lstrip()
            )

        message = dict(message)
        message['content'] = content

        return message


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
