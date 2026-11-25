"""Bind source-observed prior stop and entrant approach to both selected cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def crossing_interval(rows):
    crossing = [i for i, row in enumerate(rows) if -7 <= row['entrant']['x_m'] <= 7]
    if crossing != list(range(180, 261)):
        raise ValueError('Selected entrant crossing interval differs')
    return crossing


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    prior_proof_path = HERE / 'entrant-antecedent-proof.json'
    prior = json.loads(prior_proof_path.read_text())
    if len(prior['negative_rejections']) != 3 or prior['lawful_prior_yield_verified']:
        raise ValueError('Missing antecedent negatives or unsupported legal claim')
    cases = []
    for entry in manifest['cases']:
        case = entry['case_id']
        number = case.rsplit('_', 1)[-1]
        public_path = HERE / entry['compatibility']['receipt']
        if sha(public_path) != entry['compatibility']['sha256']:
            raise ValueError('Selected compatibility receipt changed')
        public = json.loads(public_path.read_text())
        measure = public['measurement_examples']['priority_requirement']['value']
        source = HERE / f'current-v2-probe-{number}-fixture/native_samples.jsonl'
        if (measure['case_id'] != case or measure['native_samples_sha256'] != sha(source)
                or measure['entrant_prior_stopped_frames'] != 140
                or measure['about_to_enter_first_frame'] != 140
                or measure['entrant_lawful_prior_yield_verified']):
            raise ValueError('Selected source antecedent absent or legal status overstated')
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        crossing = crossing_interval(rows)
        no_crossing = [dict(row) for row in rows]
        no_crossing[200] = dict(no_crossing[200])
        no_crossing[200]['entrant'] = {'x_m': -12.0}
        try:
            crossing_interval(no_crossing)
        except ValueError:
            pass
        else:
            raise AssertionError('Missing entrant crossing frame was accepted')
        cases.append({'case_id': case, 'construction_sha256': entry['construction_sha256'],
                      'source_sha256': sha(source), 'prior_stopped_frames': 140,
                      'about_to_enter_first_frame': 140,
                      'intersection_entry_frame': crossing[0],
                      'intersection_exit_frame': crossing[-1],
                      'crossing_frame_count': len(crossing),
                      'missing_crossing_frame_negative_rejected': True,
                      'lawful_prior_yield_verified': False})
    if len(cases) != 2:
        raise ValueError('Both exact cases required')
    output = {'format': 'c111294-selected-antecedent-cpu-proof-v1', 'passed': True,
              'manifest_sha256': sha(manifest_path), 'prior_negative_proof_sha256': sha(prior_proof_path),
              'cases': cases, 'original_native_observed': False,
              'lawful_prior_yield_verified': False, 'legal_verdict_claimed': False}
    path = HERE / 'selected-antecedent-audit.json'
    path.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'passed': True, 'cases': len(cases), 'receipt_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
