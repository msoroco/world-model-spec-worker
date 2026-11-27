"""Resolve and execute this assignment's exact local delivery queue commands."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[1]
STAGES = ('prepare_command', 'execute_command', 'capture_command',
          'owner_release_command', 'postprocessing_command',
          'additional_source_audit_command', 'accept_command')


def resolve(identifier: str, stage: str, candidate: str | None = None) -> str:
    proposal = json.loads((WORK / 'queue-proposal.json').read_text(encoding='utf-8'))
    if stage == 'comparison':
        if candidate is not None:
            raise ValueError('comparison has no candidate')
        return next(row['command'] for row in proposal['comparison_audit_commands']
                    if row['comparison_id'] == identifier)
    row = next(row for row in proposal['cases'] if row['case_id'] == identifier)
    if candidate is not None:
        if stage != 'prepare_command':
            raise ValueError('candidate is valid only with prepare_command')
        return row['candidate_commands'][candidate]
    return row[stage]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('identifier')
    parser.add_argument('stage', choices=(*STAGES, 'comparison'))
    parser.add_argument('candidate', nargs='?')
    parser.add_argument('--show', action='store_true')
    args = parser.parse_args()
    command = resolve(args.identifier, args.stage, args.candidate)
    if args.show:
        print(command)
        return 0
    return subprocess.run(['bash', '-c', command], cwd=ROOT, check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
