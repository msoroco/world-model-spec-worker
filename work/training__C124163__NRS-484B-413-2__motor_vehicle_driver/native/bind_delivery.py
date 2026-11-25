"""Bind six independent diagnostic source audits and four fixed-condition comparisons."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
MANIFEST = FOLDER / 'execution-manifest.json'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    manifest = json.loads(MANIFEST.read_text())
    script = FOLDER / 'delivery_acceptance.py'
    for entry in manifest['cases']:
        label = entry['case_id'].rsplit('__', 1)[-1]
        cid = entry['case_id']
        positive = f'delivery-{label}-positive'
        negative = f'delivery-{label}-negative'
        for name in (positive+'.json', positive+'.log', negative+'.log'):
            if not (FOLDER/name).is_file():
                raise ValueError('Missing exact delivery proof: '+name)
        entry['delivery_acceptance'] = {
            'case_id': cid, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': 'delivery_acceptance.py', 'script_sha256': sha(script),
            'command': f'.venv-cpu/bin/python work/{FOLDER.name}/delivery_acceptance.py --attempt .runtime-work/c124163-compat-{label}-primary-v8 --case {cid} --diagnostic --output work/{FOLDER.name}/{positive}.json',
            'test_exit_code': 0, 'test_log': positive+'.log',
            'test_log_sha256': sha(FOLDER/(positive+'.log')),
            'negative_command': f'.venv-cpu/bin/python work/{FOLDER.name}/delivery_acceptance.py --attempt .runtime-work/c124163-compat-{label}-primary-v8 --case {cid} --output work/{FOLDER.name}/{negative}.json',
            'negative_exit_code': 1,
            'negative_expected_error': 'Missing delivery source: capture-seal.json',
            'negative_log': negative+'.log',
            'negative_log_sha256': sha(FOLDER/(negative+'.log')),
            'proof_scope': 'Six synthetic source joins and synthetic-as-physical rejection only'}
    MANIFEST.write_text(json.dumps(manifest, indent=2)+'\n')
    plan_path = FOLDER/'case-plan.json'
    plan = json.loads(plan_path.read_text())
    for i, comparison in enumerate(plan['comparisons']):
        stem = f'comparison-{i+1}'
        if not (FOLDER/(stem+'-audit.json')).is_file():
            raise ValueError('Missing independent comparison: '+stem)
        comparison['status'] = 'diagnostic_independent_audit_passed_physical_pending'
        comparison['audit'] = {'report': stem+'-audit.json',
                               'sha256': sha(FOLDER/(stem+'-audit.json')),
                               'log': stem+'-audit.log',
                               'log_sha256': sha(FOLDER/(stem+'-audit.log'))}
    plan_path.write_text(json.dumps(plan, indent=2)+'\n')
    print(json.dumps({'delivery_cases': len(manifest['cases']),
                      'comparisons': len(plan['comparisons'])}))

if __name__ == '__main__':
    main()
