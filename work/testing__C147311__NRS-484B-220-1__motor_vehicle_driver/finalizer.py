"""Saved-only one-way result from original travel, site and camera sources."""
import argparse
import hashlib
import json
from pathlib import Path

from one_way_measurements import analyze

ASSIGNMENT = 'testing__C147311__NRS-484B-220-1__motor_vehicle_driver'
WITH = ASSIGNMENT + '__source_verified_with_designation'
AGAINST = ASSIGNMENT + '__source_verified_against_designation'
CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def _sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_one_way_direction(report):
    return {'all_steps_designated_direction': report['all_steps_designated_direction'],
            'all_body_on_roadway': all(s['complete_body_on_one_way_roadway'] for s in report['samples']),
            'projected_displacement_m': sum(report['projected_step_m'])}


def finalize(attempt, output):
    from worker_exchange.native_output import physical_result, write_result
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt/'result.json').exists() or (attempt/'channels').exists():
        raise ValueError('Retain prior finalization; use a fresh attempt')
    for name in ('config.json', 'road_context.json', 'site_packet.json',
                 'travel_history.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                 'capture/evidence.jsonl', *CAMERAS):
        if not (attempt/name).is_file(): raise ValueError('Missing required source: '+name)
    config = json.loads((attempt/'config.json').read_text())
    if config.get('selected_case_id') not in (WITH, AGAINST):
        raise ValueError('Exact C147311 selected case required')
    description = config.get('recording_description')
    if not isinstance(description, dict) or not description.get('channels'):
        raise ValueError('Selected recording description required')
    report = analyze(attempt)
    observed = measure_one_way_direction(report)
    expected = config['selected_case_id'] == WITH
    channel_dir = attempt/'channels'; channel_dir.mkdir()
    extract = {
        'designated_motion': lambda i, sample: report['projected_step_m'][i-1] > 0 if i else False,
        'heading_alignment': lambda i, sample: sample['heading_alignment'],
        'roadway_occupancy': lambda i, sample: sample['complete_body_on_one_way_roadway'],
    }
    evidence = []
    for name, fn in extract.items():
        path = channel_dir/(name+'.jsonl')
        with path.open('x') as stream:
            for i, sample in enumerate(report['samples']):
                stream.write(json.dumps({'original_frame': sample['frame'], 'time_s': sample['time_s'],
                                         'value': fn(i, sample)}, separators=(',', ':'))+'\n')
        evidence.append({'name': name, 'unit': 'scalar' if name == 'heading_alignment' else 'boolean',
                         'reference': 'channels/'+path.name})
    (channel_dir/'road_context.json').write_text(json.dumps({'road_context': json.loads(
        (attempt/'road_context.json').read_text())}, indent=2)+'\n')
    evidence.append({'name': 'road_context', 'unit': 'structured record',
                     'reference': 'channels/road_context.json'})
    check = {'target': 'original complete-body movement along designated direction',
             'requested': expected, 'measured': observed['all_steps_designated_direction'],
             'method': 'source-backed same-road complete body, heading and projected displacement',
             'tolerance': 0, 'matched': observed['all_steps_designated_direction'] == expected and
             observed['all_body_on_roadway'], 'physical_cause_confirmed': False,
             'cause_evidence': ['travel_history.jsonl', 'video_frames.jsonl',
                                'road_context.json', 'site_packet.json']}
    result = {'case_id': config['selected_case_id'], 'measured_values': observed,
              'target_checks': [check], 'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'saved original-source analysis; authority and physical review remain separate',
              'physical_failure_flags': ['authority designation and sign visibility need independent review',
                                        'source-camera visibility needs full decode and pixel review'],
              'trace_reference': 'trace.jsonl', 'video_references': list(CAMERAS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'source_evidence_hashes': report['sources'],
              'capture_evidence_sha256': _sha(attempt/'capture/evidence.jsonl'),
              'realized_observables': {}}
    result = physical_result(attempt, result)
    inputs = ('road_context.json', 'site_packet.json', 'travel_history.jsonl', 'video_frames.jsonl')
    measurements = {'one_way_direction': {'method': 'measure_one_way_direction',
                    'value': observed, 'sources': {name: report['sources'][name] for name in inputs}}}
    analysis = {'format': 'worker-one-way-analysis', 'case_id': config['selected_case_id'],
                'measurements': measurements, 'source_report': report,
                'source_hashes': report['sources'], 'physical_checks': result['physical_checks'],
                'legal_verdict_asserted': False}
    write_result(attempt, result)
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False)+'\n')
    return analysis


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True); args = parser.parse_args()
    finalize(args.attempt, args.output)


if __name__ == '__main__': main()
