"""Regression-injection guardrails with an isolated local Git fixture."""
from __future__ import annotations
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import regression_lab


class RegressionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ('include/job_system', 'src'):
            (self.root / folder).mkdir(parents=True)
        for rel, old, _ in regression_lab.SCENARIOS.values():
            (self.root / rel).write_text('leading\n' + old + '\ntrailing\n')
        self.git('init', '-q')
        self.git('config', 'user.name', 'Test Student')
        self.git('config', 'user.email', 'student@example.invalid')
        self.git('add', '.')
        self.git('commit', '-m', 'fixture', '-q')
        self.sha = self.git('rev-parse', 'HEAD').stdout.strip()
        self.git('switch', '-c', 'training/ai-job-processing', '-q')

    def git(self, *args):
        p = subprocess.run(['git', *args], cwd=self.root, capture_output=True, text=True)
        if p.returncode:
            raise AssertionError(f'git failed: {args}: {p.stderr}')
        return p

    def test_priority_injection_is_exactly_one_local_edit(self):
        with patch.object(regression_lab, 'ROOT', self.root), patch.object(regression_lab, 'PIN', self.sha):
            regression_lab.apply(['priority'])
        modified = self.git('diff', '--name-only').stdout.strip()
        self.assertEqual(modified, 'include/job_system/thread_safe_queue.h')
        text = (self.root / modified).read_text()
        self.assertIn('lowQueue_.push', text)
        self.assertNotIn('highQueue_.push', text)

    def test_statistics_injection_is_exactly_one_local_edit(self):
        with patch.object(regression_lab, 'ROOT', self.root), patch.object(regression_lab, 'PIN', self.sha):
            regression_lab.apply(['statistics'])
        self.assertEqual(self.git('diff', '--name-only').stdout.strip(), 'src/statistics.cpp')

    def test_wrong_branch_rejected(self):
        self.git('switch', '-c', 'main', '-q')
        with patch.object(regression_lab, 'ROOT', self.root), patch.object(regression_lab, 'PIN', self.sha):
            with self.assertRaisesRegex(RuntimeError, 'branch'):
                regression_lab.apply(['priority'])
        self.assertFalse(self.git('diff', '--name-only').stdout.strip())

    def test_dirty_source_rejected(self):
        path = self.root / 'src/statistics.cpp'
        path.write_text(path.read_text() + '// dirty\n')
        with patch.object(regression_lab, 'ROOT', self.root), patch.object(regression_lab, 'PIN', self.sha):
            with self.assertRaisesRegex(RuntimeError, 'already modified'):
                regression_lab.apply(['priority'])

    def test_double_injection_does_not_overwrite(self):
        with patch.object(regression_lab, 'ROOT', self.root), patch.object(regression_lab, 'PIN', self.sha):
            regression_lab.apply(['priority'])
            with self.assertRaises(RuntimeError):
                regression_lab.apply(['priority'])


if __name__ == '__main__':
    unittest.main()
