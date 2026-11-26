"""Check selected diagnostic contrasts and preserve original review requirements."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = json.loads((HERE / 'case-plan.json').read_text())
EXPECTED = {'stop': {'driver_behavior'},
            'cane': {'cane_or_assistance'},
            'blindness': {'blindness_extent'},
            'assistance': {'cane_or_assistance'},
            'post_stop': {'driver_behavior'}}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def main():
    results = []
    for pair in PLAN['comparisons']:
        name = pair['comparison_id'].rsplit('__', 1)[-1]
        if name not in EXPECTED or len(pair['case_ids']) != 2:
            raise ValueError('Unexpected exact comparison')
        suffixes = [case.rsplit('__', 1)[-1] for case in pair['case_ids']]
        roots = [HERE / 'diagnostic-source' / suffix for suffix in suffixes]
        contexts = [json.loads((root / 'blind-person-context.json').read_text())
                    for root in roots]
        requests = [item['request'] for item in contexts]
        changed = {key for key in requests[0] if requests[0][key] != requests[1][key]}
        if changed != EXPECTED[name]:
            raise ValueError('Uncontrolled blind-person request difference: ' + name)
        poses = [read_rows(root / 'vehicle-person-poses.jsonl') for root in roots]
        if any(len(rows) != 600 for rows in poses):
            raise ValueError('Comparison source frame count differs: ' + name)
        for i in range(600):
            first, second = poses[0][i], poses[1][i]
            for key in ('video_frame', 'native_frame', 'time_s', 'person_id',
                        'person_xyz_m', 'bbox_half_length_m', 'bbox_half_width_m'):
                if first[key] != second[key]:
                    raise ValueError('Fixed condition differs: ' + name + '/' + key)
            if name in ('cane', 'blindness') and (first['vehicle_xyz_m'] != second['vehicle_xyz_m'] or
                                                 first['speed_mps'] != second['speed_mps']):
                raise ValueError('Person-source comparison changed driver motion: ' + name)
            if name != 'assistance' and first['assistant_id'] != second['assistant_id']:
                raise ValueError('Assistant changed outside assistance comparison')
            if name == 'assistance' and first['assistant_id'] == second['assistant_id']:
                raise ValueError('Assistance contrast lacks assistant actor')
        if name in ('stop', 'post_stop') and poses[0][240]['speed_mps'] == poses[1][240]['speed_mps']:
            raise ValueError('Driver behavior contrast absent: ' + name)
        results.append({'comparison_id': pair['comparison_id'],
                        'case_ids': pair['case_ids'],
                        'changed_request_keys': sorted(changed),
                        'diagnostic_context_sha256': [sha(root / 'blind-person-context.json')
                                                      for root in roots],
                        'diagnostic_pose_sha256': [sha(root / 'vehicle-person-poses.jsonl')
                                                   for root in roots],
                        'source_originality': 'diagnostic_only',
                        'original_native_outcome_reviewed': False})
    if len(results) != 5:
        raise ValueError('Full-law comparison count differs')
    output = HERE / 'comparison-audit-specs.json'
    output.write_text(json.dumps({'format': 'c129273-comparison-audit-v1',
                                  'comparisons': results,
                                  'all_original_reviews_pending': True}, indent=2) + '\n')
    print(json.dumps({'comparisons': len(results), 'spec_sha256': sha(output)}))


if __name__ == '__main__':
    main()
