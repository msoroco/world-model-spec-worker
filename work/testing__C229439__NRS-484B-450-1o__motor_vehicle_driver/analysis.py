"""Selected saved-only source measurement; never labels a parking violation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from parking import measure_original_history


INPUTS = ('site-source.json', 'device-source.json', 'actor_rows.json')


def _source(root, name, expected_hash):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_hash:
        raise ValueError('Original source hash mismatch: ' + name)
    return json.loads(raw), digest


def measure_official_prohibition(stage):
    root = Path(stage)
    attempt_path = root / 'attempt.json'
    if not attempt_path.is_file():
        raise ValueError('Missing required source: attempt.json')
    attempt = json.loads(attempt_path.read_text())
    refs = attempt.get('source_context', {})
    if set(refs) != set(INPUTS):
        raise ValueError('Original site, device and actor source bindings required')
    values = {}
    hashes = {}
    for name in INPUTS:
        reference = refs[name]
        if reference.get('path') != name:
            raise ValueError('Original source path changed: ' + name)
        values[name], hashes[name] = _source(root, name, reference['sha256'])
    site, device, rows = (values[name] for name in INPUTS)
    if (site.get('cell_id') != 'C229439' or
            device.get('device_id') != attempt['device_id'] or
            device.get('exact_instruction') != attempt['device_instruction'] or
            device.get('governed_polygon') != site.get('parking_polygon') or
            site.get('parking_polygon') != attempt['parking_polygon']):
        raise ValueError('Original reviewed site or device differs from attempt')
    if not all(device.get(name) for name in ('authority_source', 'placement_source',
                                            'traffic_purpose_source',
                                            'legal_consistency_source')):
        raise ValueError('Original official device review incomplete')
    expected = {key: attempt[key] for key in ('frame_count', 'first_frame',
        'case_id', 'subject_id', 'device_id', 'device_instruction',
        'parking_polygon', 'halt_action')}
    measured = measure_original_history(rows, expected)
    return {'method': 'measure_official_prohibition', 'value': measured,
            'sources': hashes}


def analyze(stage, output):
    stage = Path(stage)
    measurement = measure_official_prohibition(stage)
    report = {'format': 'worker-analysis-report',
              'case_id': measurement['value']['case_id'],
              'measurements': {'official_prohibition_history': measurement},
              'legal_judgment': None,
              'limitations': ['Original source measurements need physical and independent legal review.']}
    Path(output).write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(analyze(args.attempt, args.output)['case_id'])


if __name__ == '__main__':
    main()
