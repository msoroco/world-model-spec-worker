"""Select two exact CPU capture requests without asserting physical permission."""
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
    review = {'format': 'c110919-8c-conditional-cpu-selection-review',
              'assignment_id': HERE.name,
              'decision': 'select_two_same_cell_conditional_capture_requests',
              'selected_case_ids': [entry['case_id'] for entry in source['cases']],
              'sources': [{'path': frozen.relative_to(ROOT).as_posix(), 'sha256': sha(frozen)},
                          {'path': f'work/{HERE.name}/case-plan.json', 'sha256': sha(HERE / 'case-plan.json')},
                          {'path': f'work/{HERE.name}/statutory-review.json',
                           'sha256': sha(HERE / 'statutory-review.json')}],
              'exact_target_clause': assignment['law']['text'],
              'selection_scope': 'steady-red right-turn full-halt probe and rolling control at one authored two-way intersection',
              'original_native_observed': False,
              'physical_unknowns': ['governing signal and full-body stop readback',
                                    'extreme-right lane and two-way destination',
                                    'pedestrian and directed-traffic yield pixels',
                                    'full original source-bound frame review'],
              'legal_verdict': None}
    review_path = HERE / 'native/selection-review.json'
    write(review_path, review)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
                'runtime_manifest_sha256': source['runtime_manifest_sha256'],
                'selection_review': {'path': review_path.relative_to(HERE).as_posix(),
                                     'sha256': sha(review_path)},
                'status': 'selected_cpu_preparation_incomplete',
                'cases': [{**entry, 'kind': 'delivery'} for entry in source['cases']]}
    target = HERE / 'execution-manifest.json'
    write(target, manifest)
    print(json.dumps({'selected_cases': len(manifest['cases']), 'manifest_sha256': sha(target)}))


if __name__ == '__main__':
    main()
