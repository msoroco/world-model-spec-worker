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


def _native_result(stage, measurement):
    """Build derived review streams from saved rows; leave physical status false."""
    root = Path(stage)
    config = json.loads((root / 'config.json').read_text())
    construction = json.loads((root / 'construction.json').read_text())
    description = construction['recording_description']
    if config['case']['case_id'] != measurement['value']['case_id']:
        raise ValueError('selected Native case identity differs')
    rows = json.loads((root / 'actor_rows.json').read_text())
    streams = {
        'actual_halt_activity': lambda r: r['halt_activity'],
        'body_footprint_history': lambda r: r['body_corners_xy'],
        'official_device_instruction': lambda r: r['device_instruction'],
        'effective_conditions': lambda r: {'device_effective': r['device_effective'],
                                            'prohibited_actions': r['prohibited_actions']},
        'exception_circumstances': lambda r: {key: r[key] for key in
            ('traffic_conflict', 'law_direction', 'police_direction', 'device_direction')},
        'capture_quality': lambda r: r['camera_frames'],
    }
    channel_root = root / 'channels'
    channel_root.mkdir(exist_ok=False)
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in streams:
            raise ValueError('selected channel has no source projection: ' + name)
        path = channel_root / (name + '.jsonl')
        with path.open('x') as output:
            for row in rows:
                output.write(json.dumps({'time_s': row['time_s'],
                                         'value': streams[name](row)}, separators=(',', ':')) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': str(path.relative_to(root))})
    site = json.loads((root / 'site-source.json').read_text())
    device = json.loads((root / 'device-source.json').read_text())
    contexts = {'reviewed_site': site, 'official_device_authority': device,
                'applicable_law_source': {'law_id': config['law_id'],
                                          'cell_id': config['cell_id'],
                                          'scope': 'exact frozen assignment; no legal judgment'}}
    for item in description['context_inputs']:
        name = item['name']
        if name not in contexts:
            raise ValueError('selected context has no source projection: ' + name)
        path = channel_root / (name + '.json')
        path.write_text(json.dumps({name: contexts[name]}, separators=(',', ':')) + '\n')
        evidence.append({'name': name, 'unit': item['unit'],
                         'reference': str(path.relative_to(root))})
    target = {'target': 'original device/vehicle source join', 'requested': True,
              'measured': True, 'method': 'measure_official_prohibition',
              'tolerance': 0, 'matched': True, 'physical_cause_confirmed': False,
              'cause_evidence': measurement['sources']}
    result = {'case_id': config['case']['case_id'], 'measured_values': measurement['value'],
              'target_checks': [target], 'setup_confirmed': False,
              'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': 'Saved source measurements only; physical review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in
                  ('overview', 'approach', 'reference_corner', 'driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {}, 'legal_judgment': None}
    (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def analyze(stage, output, *, report_only=False):
    stage = Path(stage)
    measurement = measure_official_prohibition(stage)
    report = {'format': 'worker-analysis-report',
              'case_id': measurement['value']['case_id'],
              'measurements': {'official_prohibition_history': measurement},
              'legal_judgment': None,
              'limitations': ['Original source measurements need physical and independent legal review.']}
    if not report_only:
        _native_result(stage, measurement)
    Path(output).write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--report-only', action='store_true')
    args = parser.parse_args()
    print(analyze(args.attempt, args.output, report_only=args.report_only)['case_id'])


if __name__ == '__main__':
    main()
