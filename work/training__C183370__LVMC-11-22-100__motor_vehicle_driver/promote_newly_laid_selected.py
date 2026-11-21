"""Promote conditionally reviewed newly laid constructions without claiming readiness."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    target = HERE / 'execution-manifest.json'
    manifest = read(target)
    draft = read(HERE / 'draft-newly-laid-finalized-manifest.json')
    review_path = HERE / 'native/selection-review.json'
    review = read(review_path)
    if len(manifest['cases']) != 10 or len(draft['cases']) != 2:
        raise ValueError('Expected ten selected and two reviewed draft cases')
    existing = {row['case_id'] for row in manifest['cases']}
    additions = {row['case_id'] for row in draft['cases']}
    if existing & additions or existing | additions != set(review['selected_case_ids']):
        raise ValueError('Selection review differs from exact case inventory')
    reference = manifest['cases'][0]
    for source in draft['cases']:
        entry = copy.deepcopy(source)
        short = entry['case_id'].removeprefix(HERE.name + '__')
        if not short.startswith('newly_laid_'):
            raise ValueError('Unexpected selected source case')
        physical = HERE / 'selected-physical-preparation' / short / 'proof.json'
        entry['physical_preparation'] = {
            'receipt': str(physical.relative_to(HERE)), 'sha256': sha(physical)}
        entry['native_handoff'] = copy.deepcopy(reference['native_handoff'])
        entry['acquisition'] = copy.deepcopy(reference['acquisition'])
        entry['post_capture'] = copy.deepcopy(reference['post_capture'])
        entry['post_capture']['command'] = entry['post_capture']['command'].replace(
            reference['case_id'], entry['case_id'])
        entry['post_capture']['test_exit_code'] = None
        entry['post_capture'].pop('test_log', None)
        entry['post_capture'].pop('test_log_sha256', None)
        entry['offline'] = {'exit_code': None,
                            'construction_sha256': entry['construction_sha256'],
                            'status': 'pending_exact_selected_manifest_proof'}
        entry['compatibility'] = {'status': 'pending_exact_selected_manifest_proof'}
        entry['negative'] = {'status': 'pending_exact_selected_manifest_proof'}
        entry['delivery_acceptance'] = {'case_id': entry['case_id'],
                                        'status': 'pending_positive_negative_cpu_contract'}
        for candidate in entry['candidates']:
            candidate['offline'] = {'exit_code': None,
                                    'construction_sha256': candidate['construction_sha256'],
                                    'status': 'pending_exact_selected_manifest_proof'}
            candidate['compatibility'] = {'status': 'pending_exact_selected_manifest_proof'}
        entry['candidate_offline_status'] = 'pending_exact_selected_manifest_proof'
        manifest['cases'].append(entry)
    manifest['selection_review'] = {'path': 'native/selection-review.json',
                                    'sha256': sha(review_path)}
    manifest['status'] = 'selected_twelve_cpu_proofs_incomplete'
    write(target, manifest)
    print(json.dumps({'selected_cases': len(manifest['cases']),
                      'manifest_sha256': sha(target),
                      'original_native_observed': False,
                      'ready': False}, sort_keys=True))


if __name__ == '__main__':
    main()
