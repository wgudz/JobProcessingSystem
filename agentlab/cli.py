"""CLI for a bounded, offline-capable C++ code triage agent."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .providers import MockProvider, OllamaProvider
from .runner import (
    run_agent,
    save_report,
    save_json_report,
    save_evidence_journal,
    validate_report_path
)

ROOT = Path(__file__).resolve().parent.parent

def load_issue(path: Path) -> dict:
    try:
        with path.open('r', encoding='utf-8') as file:
            return json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError('Invalid JSON in issue file') from exc

def resolve_issue_path(workspace: Path, issue_file: Path) -> Path:
    workspace = workspace.resolve()

    if issue_file.is_absolute():
        path = issue_file.resolve()
    else:
        path = (workspace / issue_file).resolve()

    try:
        path.relative_to(workspace)
    except ValueError:
        raise ValueError('--issue-file must be inside workspace')

    if not path.is_file():
        raise FileNotFoundError(f'Issue file not found: {path}')

    return path

def validate_issue(issue: dict) -> dict:
    if not isinstance(issue, dict):
        raise ValueError('Issue must be a JSON object')

    for field in ('title', 'symptoms', 'expected'):
        value = issue.get(field)

        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'Issue field "{field}" must be a non-empty string')

    suspected_tests = issue.get('suspected_tests', [])

    if not isinstance(suspected_tests, list):
        raise ValueError('Issue field "suspected_tests" must be a list')

    if not all(isinstance(test, str) and test.strip() for test in suspected_tests):
        raise ValueError('Every suspected test must be a non-empty string')

    issue['suspected_tests'] = suspected_tests
    return issue

def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog='python -m agentlab',
        description='JobProcessingSystem AI Lab (local Ollama, no paid API)',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            'Examples:\n'
            '  File-only analysis:\n'
            '    python -m agentlab --provider mock --issue-id BUG-001 '
            '--issue-file issues\\BUG-001.json\n\n'
            '  Analysis with tests:\n'
            '    python -m agentlab --provider ollama --model qwen3:4b '
            '--issue-id BUG-001 --issue-file issues\\BUG-001.json --allow-exec\n\n'
            '  Analysis with Skill:\n'
            '    python -m agentlab --provider ollama --model qwen3:4b '
            '--issue-id BUG-001 --issue-file issues\\BUG-001.json '
            '--skill job-processing-triage --allow-exec'
        )
    )
    p.add_argument('--provider', choices=('mock', 'ollama'), default='mock')
    p.add_argument('--model', default='qwen3:4b')
    p.add_argument('--workspace', type=Path, default=ROOT)
    p.add_argument('--skill', default='job-processing-triage')

    p.add_argument(
        '--issue-id',
        help='Incident identifier, e.g. BUG-001'
    )

    p.add_argument(
        '--issue-file',
        type=Path,
        help='Path to incident JSON inside workspace'
    )

    p.add_argument(
        '--output-json',
        type=Path,
        help='Optional machine-readable JSON report'
    )

    p.add_argument('--allow-exec', action='store_true', help='Run CMake and CTest on TRUSTED code only')
    p.add_argument('--max-steps', type=int, default=14)
    p.add_argument(
        '--report',
        type=Path,
        default=Path('reports/latest.md')
    )
    args = p.parse_args(argv)

    if bool(args.issue_id) != bool(args.issue_file):
        p.error('--issue-id and --issue-file must be used together')

    if not 1 <= args.max_steps <= 30:
        p.error('--max-steps must be between 1 and 30')

    provider = MockProvider() if args.provider == 'mock' else OllamaProvider(args.model)

    try:
        workspace = args.workspace.resolve()

        if not workspace.is_dir():
            raise ValueError(f'Workspace directory not found: {workspace}')
        report_path = validate_report_path(
            args.report,
            workspace,
            '.md'
        )

        output_json_path = None

        if args.output_json:
            output_json_path = validate_report_path(
                args.output_json,
                workspace,
                '.json'
            )
        issue = None

        if args.issue_file:
            issue_path = resolve_issue_path(args.workspace, args.issue_file)
            issue = validate_issue(load_issue(issue_path))

        result = run_agent(
            ROOT,
            workspace,
            args.skill,
            provider,
            issue_id=args.issue_id,
            issue=issue,
            allow_exec=args.allow_exec,
            max_steps=args.max_steps
        )

        evidence_path = (
            workspace
            / 'reports'
            / f'evidence-{result.session_id}.json'
        )

        save_evidence_journal(
            result,
            evidence_path,
            workspace,
            args.skill,
            args.allow_exec
        )

        save_report(
            result,
            report_path,
            workspace,
            args.skill,
            args.issue_id
        )

        if output_json_path:
            save_json_report(
                result,
                output_json_path,
                workspace,
                args.skill,
                issue_id=args.issue_id
            )
        
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        p.exit(2, f'ERROR: {exc}\n')

    print(f'Provider: {args.provider}; model: {args.model if args.provider == "ollama" else "none (mock)"}')
    print(f'Status: {result.status}')
    print(f'Reason: {result.termination_reason}')
    print(f'Steps: {result.steps}')
    print(f'Tool calls: {len(result.events)}')
    print( f'Evidence: {evidence_path.resolve()}')
    for event in result.events:
        print(f'  {event["tool"]}: exit={event["result"].get("exit_code", "n/a")}')

    print(f'Report: {report_path}\n')
    print(result.report)

    if result.status == 'COMPLETED':
        return 0

    return 2
