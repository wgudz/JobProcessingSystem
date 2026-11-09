"""CLI for a bounded, offline-capable C++ code triage agent."""
from __future__ import annotations
import argparse
from pathlib import Path
from .providers import MockProvider, OllamaProvider
from .runner import run_agent, save_report

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='JobProcessingSystem AI Lab (local Ollama, no paid API)')
    p.add_argument('--provider', choices=('mock', 'ollama'), default='mock')
    p.add_argument('--model', default='qwen3:4b')
    p.add_argument('--workspace', type=Path, default=ROOT)
    p.add_argument('--skill', default='job-processing-triage')
    p.add_argument('--allow-exec', action='store_true', help='Run CMake and CTest on TRUSTED code only')
    p.add_argument('--max-steps', type=int, default=14)
    p.add_argument('--report', type=Path, default=ROOT / 'reports' / 'latest.md')
    args = p.parse_args(argv)
    if not 1 <= args.max_steps <= 30:
        p.error('--max-steps must be between 1 and 30')
    provider = MockProvider() if args.provider == 'mock' else OllamaProvider(args.model)
    try:
        result = run_agent(ROOT, args.workspace, args.skill, provider,
                           allow_exec=args.allow_exec, max_steps=args.max_steps)
        save_report(result, args.report, args.workspace, args.skill)
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        p.exit(2, f'ERROR: {exc}\n')
    print(f'Provider: {args.provider}; model: {args.model if args.provider == "ollama" else "none (mock)"}')
    print(f'Tool calls: {len(result.events)}')
    for event in result.events:
        print(f'  {event["tool"]}: exit={event["result"].get("exit_code", "n/a")}')
    print(f'Report: {args.report.resolve()}\n')
    print(result.report)
    return 0
