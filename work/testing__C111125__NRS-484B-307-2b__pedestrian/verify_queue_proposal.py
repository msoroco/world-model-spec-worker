"""Verify proposed local commands and exact delivery identities."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> None:
    proposal = json.loads((ROOT / 'gpu-queue-proposal.json').read_text())
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    case_ids = {item['case_id'] for item in proposal['cases']}
    if case_ids != {item['case_id'] for item in manifest['cases']} or case_ids != {
            item['case_id'] for item in plan['cases']}:
        raise ValueError('queue case identities differ from selected exact cases')
    comparisons = {item['comparison_id'] for item in proposal['comparison_audit_commands']}
    if comparisons != {item['comparison_id'] for item in plan['comparisons']}:
        raise ValueError('queue comparison identities differ')
    checked = 0
    for row in proposal['cases']:
        for key in ('prepare_command', 'execute_command', 'capture_command',
                    'accept_command', 'postprocessing_command',
                    'owner_release_command', 'additional_source_audit_command'):
            if row['case_id'] not in row[key]:
                raise ValueError('queue command omits exact case: ' + key)
            subprocess.run(['bash', '-n'], input=row[key], text=True, check=True)
            checked += 1
        for command in row['candidate_commands'].values():
            if row['case_id'] not in command:
                raise ValueError('fallback command omits exact case')
            subprocess.run(['bash', '-n'], input=command, text=True, check=True)
            checked += 1
    for row in proposal['comparison_audit_commands']:
        if row['comparison_id'] not in row['command']:
            raise ValueError('comparison command omits exact comparison')
        subprocess.run(['bash', '-n'], input=row['command'], text=True, check=True)
        checked += 1
    print(json.dumps({'case_count': len(case_ids), 'comparison_count': len(comparisons),
                      'shell_commands_checked': checked}, sort_keys=True))


if __name__ == '__main__':
    main()
