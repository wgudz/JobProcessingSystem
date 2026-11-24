import json
import unittest

from agentlab.runner import (
    create_analysis_plan,
    build_docs_only_concurrency_report,
    has_required_concurrency_risk
)


class SK202ContractTest(unittest.TestCase):

    def test_queue_review_has_expected_plan(self):
        issue = {
            'title': (
                'Concurrency review: '
                'ThreadSafeQueue close wake-up'
            ),
            'symptoms': (
                'Review a thread_safe_queue '
                'shutdown change'
            ),
            'expected': (
                'Closing the queue preserves '
                'wake-up behaviour'
            ),
            'suspected_tests': [
                'thread_safe_queue_test'
            ]
        }

        test_map = {
            'thread_safe_queue': [
                'thread_safe_queue_test'
            ]
        }

        plan = create_analysis_plan(
            issue,
            test_map,
            True,
            'job-concurrency-review'
        )

        required_tools = [
            step['tool']
            for step in plan
            if step.get('required', True)
        ]

        self.assertEqual(
            required_tools,
            [
                'git_status',
                'git_diff',
                'run_selected_tests',
                'read_file',
                'search_code'
            ]
        )

        read_steps = [
            step
            for step in plan
            if step['tool'] == 'read_file'
        ]

        self.assertEqual(
            len(read_steps),
            1
        )

        self.assertEqual(
            read_steps[0]['arguments']['path'],
            'include/job_system/thread_safe_queue.h'
        )

    def test_docs_only_report_does_not_invent_concurrency_bug(self):
        plan = [
            {
                'tool': 'git_status',
                'required': True,
                'status': 'DONE',
                'evidence_id': 'EVID-001'
            },
            {
                'tool': 'git_diff',
                'required': True,
                'status': 'DONE',
                'evidence_id': 'EVID-002'
            },
            {
                'tool': 'search_code',
                'required': True,
                'status': 'DONE',
                'evidence_id': 'EVID-003'
            }
        ]

        diff = (
            'diff --git a/README.md b/README.md\n'
            'index 1111111..2222222 100644\n'
            '--- a/README.md\n'
            '+++ b/README.md\n'
            '@@ -1,1 +1,2 @@\n'
            ' Existing documentation\n'
            '+Concurrency review workflow documented.\n'
        )

        evidence = [
            {
                'id': 'EVID-001',
                'tool': 'git_status',
                'arguments': {},
                'result': {
                    'stdout': '',
                    'status': 'OK'
                }
            },
            {
                'id': 'EVID-002',
                'tool': 'git_diff',
                'arguments': {},
                'result': {
                    'stdout': json.dumps({
                        'unstaged': diff,
                        'staged': ''
                    }),
                    'status': 'OK'
                }
            },
            {
                'id': 'EVID-003',
                'tool': 'search_code',
                'arguments': {
                    'query': 'Job'
                },
                'result': {
                    'stdout': '{}',
                    'status': 'OK'
                }
            }
        ]

        report = build_docs_only_concurrency_report(
            evidence,
            plan
        )

        self.assertIsNotNone(report)

        self.assertIn(
            'Brak wystarczających dowodów:',
            report
        )

        self.assertNotIn(
            'Pewne naruszenie kontraktu:',
            report
        )

        self.assertNotIn(
            'Możliwy race condition:',
            report
        )

        self.assertIn(
            'Zmiana jest czysto dokumentacyjna.',
            report
        )

    def test_exactly_one_risk_category_is_required(self):
        self.assertTrue(
            has_required_concurrency_risk(
                '## Risks\n'
                'Pewne naruszenie kontraktu: '
                'lost wake-up.'
            )
        )

        self.assertFalse(
            has_required_concurrency_risk(
                '## Risks\n'
                'Pewne naruszenie kontraktu: X\n'
                'Możliwy race condition: Y'
            )
        )

        self.assertFalse(
            has_required_concurrency_risk(
                '## Risks\nBrak klasyfikacji.'
            )
        )


if __name__ == '__main__':
    unittest.main()