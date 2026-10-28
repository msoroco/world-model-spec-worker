"""Audit fresh assignment ownership, source mappings and exact CPU checks."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    batch = read(ROOT / 'batch.json')
    validation = read(ROOT / 'work/_shared/lead-validation.json')
    by_case = {c['case_id']: c for c in validation['cases']}
    packages = []
    for aid in batch['assignments']:
        folder = ROOT / 'work' / aid
        result = read(folder / 'result.json')
        plan = read(folder / 'case-plan.json')
        proposal = read(folder / 'proposals/cases.json')
        manifest = read(folder / 'execution-manifest.json')
        original = read(ROOT / 'inputs' / aid / 'assignment.json')
        terms = {term['term'] for term in original['source_observation_terms']}
        mapping = plan['source_observation_mapping']
        if set(mapping) != terms:
            raise ValueError('Incomplete source mapping: ' + aid)
        channels = {c['name'] for c in proposal['cases'][0]['recording_description']['channels']}
        if any(not item['evidence'] or not item['channels'] and not item['source_refs'] or
               not set(item['channels']) <= channels for item in mapping.values()):
            raise ValueError('Unacquired source term: ' + aid)
        expected = {c['case_id'] for c in proposal['cases'] if c['target_type'] != 'baseline'}
        exact = {c['case_id'] for c in manifest['cases']}
        if expected != exact:
            raise ValueError('Exact case coverage differs: ' + aid)
        checks = [by_case[cid] for cid in sorted(exact)]
        if result['status'] == 'ready' and any(c['compatibility']['exit_code'] for c in checks):
            raise ValueError('Ready package lacks passing compatibility: ' + aid)
        if any(c['offline']['exit_code'] or c.get('atom_preflight', {}).get('exit_code') for c in checks):
            raise ValueError('Unresolved implementable CPU failure: ' + aid)
        if result.get('physical_acceptance') is True:
            raise ValueError('Unverified physical acceptance: ' + aid)
        packages.append({'assignment_id': aid, 'status': result['status'],
            'readiness_kind': result.get('readiness_kind'), 'reason': result.get('reason'),
            'source_observation_terms': sorted(terms),
            'source_observation_mapping': mapping,
            'case_ids': sorted(exact), 'per_case_commands_and_hashed_logs': checks,
            'compatibility_receipts': [c.get('compatibility', {}).get('receipt') for c in manifest['cases']],
            'unresolved_physical_checks': result.get('unresolved_physical_checks') or
                ['Native motion, environmental setup, camera visibility and duration remain operator checks; see HANDOFF.md'],
            'handoff': str((folder / 'HANDOFF.md').relative_to(ROOT)),
            'result_sha256': sha(folder / 'result.json')})
    report = {'format': 'fresh-demo-test-lead-acceptance-v1',
        'batch_id': batch['batch_id'], 'branch': batch['return_branch'],
        'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
        'assignment_count': len(packages), 'exact_case_count': len(validation['cases']),
        'ready_count': sum(p['status'] == 'ready' for p in packages),
        'partial_count': sum(p['status'] == 'partial' for p in packages),
        'all_offline_passed': validation['all_offline_passed'],
        'all_atom_preflight_passed': validation['all_atom_preflight_passed'],
        'all_compatibility_passed': validation['all_compatibility_passed'],
        'pinned_runtime_selftest': read(ROOT / 'work/_shared/runtime-proof.json'),
        'submission_validation': read(ROOT / 'work/_shared/submission-validation.json'),
        'preparation_acceptance': read(ROOT / 'work/_shared/preparation-acceptance.json'),
        'packages': packages,
        'limitations': ['Current pinned diagnostic fixtures prove software compatibility only.',
                        'No CARLA, physical acceptance, or legal conclusion was performed.']}
    target = ROOT / 'work/_shared/lead-acceptance.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'assignments': len(packages), 'cases': len(validation['cases']),
        'ready': report['ready_count'], 'partial': report['partial_count']}))


if __name__ == '__main__':
    main()
