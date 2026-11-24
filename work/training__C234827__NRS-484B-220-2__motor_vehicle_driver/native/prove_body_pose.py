"""Prove pose-derived rotary corners in both retained synthetic saved cases."""
import copy
import hashlib
import json
from pathlib import Path

from validate_body_pose import validate

HERE = Path(__file__).resolve().parent
CASES = ('reference', 'contrast')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def reject(data, change, expected):
    altered = copy.deepcopy(data)
    change(altered)
    try:
        validate(altered, 2.0, 0.9)
    except ValueError as error:
        if expected not in str(error):
            raise
        return str(error)
    raise ValueError('Changed rotary body geometry was accepted')


def main():
    saved_proof_path = HERE / 'saved-proof.json'
    saved_proof = json.loads(saved_proof_path.read_text())
    retained = {item['case']: item for item in saved_proof['positives']}
    if set(retained) != set(CASES) or saved_proof['original_native_observed']:
        raise ValueError('Retained synthetic saved-case proof differs')
    cases = []
    negatives = []
    for case in CASES:
        path = HERE / 'saved-fixtures' / case / 'native-observed.jsonl'
        if sha(path) != retained[case]['source_hashes'][path.name]:
            raise ValueError('Retained saved actor source changed: ' + case)
        data = rows(path)
        counts = validate(data, 2.0, 0.9)
        cases.append({'case': case, 'source_sha256': sha(path), **counts})
        negatives.append({'case': case, 'mutation': 'final-corner-0.1m',
                          'rejection': reject(data, lambda changed:
                                              changed[-1]['ego_body_xy_m'][0].__setitem__(0,
                                              changed[-1]['ego_body_xy_m'][0][0] + 0.1),
                                              'corner differs at 239/0')})
        negatives.append({'case': case, 'mutation': 'final-heading-1deg',
                          'rejection': reject(data, lambda changed:
                                              changed[-1].__setitem__('ego_heading_deg',
                                              changed[-1]['ego_heading_deg'] + 1.0),
                                              'corner differs at 239/0')})
        negatives.append({'case': case, 'mutation': 'missing-final-corner',
                          'rejection': reject(data, lambda changed:
                                              changed[-1]['ego_body_xy_m'].pop(),
                                              'corner inventory differs at 239')})
    receipt = {'format': 'c234827-saved-body-pose-cpu-v1',
               'passed': True, 'diagnostic_only': True,
               'assignment_id': HERE.parent.name,
               'saved_proof_sha256': sha(saved_proof_path),
               'checker_sha256': sha(HERE / 'validate_body_pose.py'),
               'prover_sha256': sha(Path(__file__)),
               'cases': cases, 'negative_controls': negatives,
               'original_native_observed': False,
               'physical_island_verified': False,
               'legal_verdict': None, 'delivery_ready': False}
    output = HERE / 'body-pose-proof.json'
    output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'cases': len(cases),
                      'corners_checked': 1920,
                      'negative_controls_rejected': len(negatives)}))


if __name__ == '__main__':
    main()
