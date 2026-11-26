"""Independently audit the two C111334 controlled CPU comparisons.

Synthetic fixtures prove audit logic and source joins, not physical behavior.
"""

import hashlib
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent.parent
SUFFIXES = ('probe_1', 'probe_2', 'permission_before_entry')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load():
    out = {}
    for suffix in SUFFIXES:
        folder = PACKAGE / 'native-selected' / suffix
        receipt = json.loads((folder / 'public-saved-proof.json').read_text())
        compat = json.loads((folder / 'primary-compatibility.json').read_text())
        saved = json.loads((folder / 'saved-positive-processing.json').read_text())
        require(receipt['files']['primary-compatibility.json']['sha256'] ==
                sha(folder / 'primary-compatibility.json'),
                'Compatibility receipt source changed')
        require(receipt['files']['saved-positive-processing.json']['sha256'] ==
                sha(folder / 'saved-positive-processing.json'),
                'Saved processing source changed')
        require(compat['passed'] and saved['passed'] and
                compat['case_id'] == receipt['case_id'],
                'Source case identity or CPU processing differs')
        value = compat['measurement_examples']['pedestrian_entry_measurement']['value']
        require(value['case_id'] == receipt['case_id'] and
                value['source_kind'] == 'synthetic_cpu_fixture' and
                value['legal_verdict_claimed'] is False,
                'Measurement provenance or case differs')
        out[suffix] = value
    return out


def audit(values):
    wait, entry, permitted = (values[s] for s in SUFFIXES)
    require(all(v['green_arrow_alone_facing_throughout'] for v in values.values()),
            'Arrow and facing context differs')
    require(wait['first_highway_entry_frame'] is None and
            wait['highway_occupancy_frames'] == 0 and
            entry['first_highway_entry_frame'] is not None and
            entry['highway_occupancy_frames'] > 0 and
            entry['entry_before_permission'] is True,
            'Wait versus entry distinction not measured')
    require(entry['first_highway_entry_frame'] ==
            permitted['first_highway_entry_frame'] and
            entry['highway_occupancy_frames'] ==
            permitted['highway_occupancy_frames'],
            'Permission comparison changed entry trajectory')
    for key in ('c111334-native-samples.jsonl', 'video_frames.jsonl'):
        require(entry['source_sha256'][key] == permitted['source_sha256'][key],
                'Permission comparison changed ' + key)
    require(entry['video_sha256'] == permitted['video_sha256'],
            'Permission comparison changed camera streams')
    require(entry['source_sha256']['device-review.json'] !=
            permitted['source_sha256']['device-review.json'] and
            entry['other_device_permission_at_first_entry'] is False and
            permitted['other_device_permission_at_first_entry'] is True and
            permitted['first_other_device_permission_frame'] <
            permitted['first_highway_entry_frame'],
            'Permission distinction absent or mistimed')
    return {
        'format': 'c111334-comparison-cpu-audit-v1',
        'case_ids': {suffix: values[suffix]['case_id'] for suffix in SUFFIXES},
        'wait_vs_entry': 'passed',
        'same_entry_permission_change': 'passed',
        'source_kind': 'synthetic_cpu_fixture',
        'physical_acceptance_claimed': False,
        'legal_verdict_claimed': False,
    }


def prove():
    values = load()
    result = audit(values)
    altered = json.loads(json.dumps(values))
    altered['permission_before_entry']['source_sha256']['c111334-native-samples.jsonl'] = '0' * 64
    try:
        audit(altered)
    except ValueError as error:
        require('changed c111334-native-samples.jsonl' in str(error),
                'Wrong negative rejection')
    else:
        raise AssertionError('Altered trajectory source was accepted')
    result['negative_changed_trajectory_rejected'] = True
    result['auditor_sha256'] = sha(Path(__file__))
    target = PACKAGE / 'native/comparison-cpu-proof.json'
    target.write_text(json.dumps(result, indent=2) + '\n')
    return {'proof_sha256': sha(target), 'comparisons': 2, 'negatives': 1}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
