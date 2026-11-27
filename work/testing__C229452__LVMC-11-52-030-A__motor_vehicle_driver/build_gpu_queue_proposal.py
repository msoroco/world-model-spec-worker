"""Propose every exact red-curb delivery and comparison command for lead integration."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
DISPATCH = '.venv-cpu/bin/python work/_shared/queue_dispatch.py'


def main():
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    cases = []
    for entry in manifest['cases']:
        case = entry['case_id']
        def command(verb):
            return f'{DISPATCH} {case} {verb}'
        cases.append({
            'assignment_id': ASSIGNMENT, 'case_id': case,
            'prepare_command': command('prepare-delivery'),
            'execute_command': command('execute-delivery'),
            'accept_command': command('accept-delivery'),
            'capture_command': command('capture_command'),
            'postprocessing_command': command('postprocessing_command'),
            'owner_release_command': command('owner_release_command'),
            'additional_source_audit_command': command('additional_source_audit_command'),
            'candidate_commands': {candidate['id']: command('prepare-delivery') + ' --candidate ' + candidate['id']
                                   for candidate in entry['candidates']}})
    comparisons = [{
        'assignment_id': ASSIGNMENT, 'comparison_id': item['comparison_id'],
        'case_ids': item['case_ids'],
        'command': f'.venv-cpu/bin/python work/{ASSIGNMENT}/comparison_audit.py --comparison {item["comparison_id"]}'}
        for item in plan['comparisons']]
    proposal = {'format': 'worker-gpu-queue-proposal', 'assignment_id': ASSIGNMENT,
                'cases': cases, 'comparison_audit_commands': comparisons,
                'scope': 'exact-case commands for lead integration; no Native/GPU result claimed'}
    (ROOT / 'gpu-queue-proposal.json').write_text(json.dumps(proposal, indent=2) + '\n')


if __name__ == '__main__':
    main()
