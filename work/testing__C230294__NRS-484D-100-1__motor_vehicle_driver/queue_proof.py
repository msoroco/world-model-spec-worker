"""Check exact case and comparison dispatch tokens in the proposed queue."""
import json
from pathlib import Path
import shlex
import subprocess


def main():
    folder = Path(__file__).resolve().parent
    plan = json.loads((folder / 'case-plan.json').read_text())
    proposal = json.loads((folder / 'gpu-queue-proposal.json').read_text())
    aid = folder.name
    expected_cases = [row['case_id'] for row in plan['cases']]
    cases = proposal['cases']
    if [row['case_id'] for row in cases] != expected_cases or [row['order'] for row in cases] != list(range(1, len(cases) + 1)):
        raise ValueError('queue order or exact cases differ')
    checked = 0
    for row in cases:
        if row['assignment_id'] != aid:
            raise ValueError('queue assignment changed')
        for name in ('prepare_command', 'execute_command', 'capture_command',
                     'accept_command', 'owner_release_command', 'postprocessing_command',
                     'additional_source_audit_command'):
            command = row[name]
            tokens = shlex.split(command)
            if not any(row['case_id'] == token or token.endswith('=' + row['case_id']) for token in tokens):
                raise ValueError('queue command lost exact case: ' + name)
            if subprocess.run(['bash', '-n'], input=command, text=True, capture_output=True).returncode:
                raise ValueError('queue shell syntax invalid: ' + name)
            checked += 1
        for candidate, command in row['candidate_commands'].items():
            tokens = shlex.split(command)
            if candidate not in tokens or row['case_id'] not in tokens or 'prepare-delivery' not in tokens:
                raise ValueError('queue fallback selector invalid')
            if subprocess.run(['bash', '-n'], input=command, text=True, capture_output=True).returncode:
                raise ValueError('queue fallback shell syntax invalid')
            checked += 1
    comparisons = proposal['comparison_audit_commands']
    if [row['comparison_id'] for row in comparisons] != [row['comparison_id'] for row in plan['comparisons']]:
        raise ValueError('queue comparisons differ')
    for row in comparisons:
        tokens = shlex.split(row['command'])
        if row['assignment_id'] != aid or row['comparison_id'] not in tokens:
            raise ValueError('comparison selector invalid')
        if subprocess.run(['bash', '-n'], input=row['command'], text=True, capture_output=True).returncode:
            raise ValueError('comparison shell syntax invalid')
        checked += 1
    print(json.dumps({'assignment_id': aid, 'exact_cases': len(cases),
                      'exact_comparisons': len(comparisons), 'shell_commands_checked': checked,
                      'passed': True}))


if __name__ == '__main__':
    main()
