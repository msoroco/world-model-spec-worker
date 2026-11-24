"""Select the two exact CPU capture requests without claiming Native acceptance."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    source = json.loads((HERE / 'current-v2-candidate-manifest.json').read_text())
    frozen = ROOT / 'inputs' / HERE.name / 'assignment.json'
    assignment = json.loads(frozen.read_text())
    review = {'format': 'c110919-conditional-cpu-selection-review',
              'assignment_id': HERE.name,
              'decision': 'select_two_same_cell_conditional_capture_requests',
              'selected_case_ids': [entry['case_id'] for entry in source['cases']],
              'sources': [{'path': frozen.relative_to(ROOT).as_posix(), 'sha256': sha(frozen)},
                          {'path': f'work/{HERE.name}/case-plan.json',
                           'sha256': sha(HERE / 'case-plan.json')},
                          {'path': f'work/{HERE.name}/statutory-review.json',
                           'sha256': sha(HERE / 'statutory-review.json')}],
              'exact_target_clause': assignment['law']['text'],
              'selection_scope': 'two-cycle motorcycle red right-turn request and one-cycle control at one authored intersection',
              'original_native_observed': False,
              'physical_unknowns': ['actual signal and motorcycle state', 'actual detector nonresponse cause',
                                    'turn prohibition and yielding pixels', 'full source-bound frame review'],
              'legal_verdict': None}
    review_path = HERE / 'native/selection-review.json'
    write(review_path, review)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
                'runtime_manifest_sha256': source['runtime_manifest_sha256'],
                'selection_review': {'path': review_path.relative_to(HERE).as_posix(),
                                     'sha256': sha(review_path)},
                'status': 'selected_cpu_preparation_incomplete', 'cases': []}
    for entry in source['cases']:
        manifest['cases'].append({**entry, 'kind': 'delivery'})
    target = HERE / 'execution-manifest.json'
    write(target, manifest)
    print(json.dumps({'selected_cases': len(manifest['cases']), 'manifest_sha256': sha(target)}))


if __name__ == '__main__':
    main()
