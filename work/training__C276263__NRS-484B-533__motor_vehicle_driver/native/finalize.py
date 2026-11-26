"""Saved-only three-duty finalization, preserving original acquisition bytes."""
import argparse
import json
from pathlib import Path

from measure import SOURCES, measure, sha

VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv')
CHANNELS = ('engine_running', 'parking_brake_set',
            'front_wheel_heading_to_curb_deg', 'unattended_interval')


def _rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines()]


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Use a fresh saved attempt and analysis output')
    for name in (*SOURCES, *VIDEOS, 'acquisition-hashes.json', 'config.json',
                 'construction.json', 'acquisition-provenance.json'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    hashes = json.loads((attempt / 'acquisition-hashes.json').read_text())
    if hashes != {name: sha(attempt / name) for name in SOURCES}:
        raise ValueError('Original saved source hash inventory differs')
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    provenance = json.loads((attempt / 'acquisition-provenance.json').read_text())
    diagnostic = provenance.get('diagnostic_fixture') is True
    case = config.get('case_id')
    if (case != construction.get('case_id') or
            case not in {config.get('assignment_id', '') + '__reference',
                         config.get('assignment_id', '') + '__contrast'}):
        raise ValueError('Exact saved case identity differs')
    if config.get('recording_description') != construction.get('recording_description'):
        raise ValueError('Saved recording description differs')
    measured = measure(attempt, hashes, diagnostic=diagnostic)
    vehicle = _rows(attempt / 'vehicle-frames.jsonl')
    occupancy = _rows(attempt / 'occupancy-frames.jsonl')
    channels = config['recording_description']['channels']
    if {c['name'] for c in channels} != set(CHANNELS):
        raise ValueError('Four exact three-duty channels required')
    values = {
        'engine_running': [row['engine_running'] for row in vehicle],
        'parking_brake_set': [row['parking_brake_set'] for row in vehicle],
        'front_wheel_heading_to_curb_deg':
            [row['front_wheel_heading_to_curb_deg'] for row in vehicle],
        'unattended_interval':
            [row['occupant_count'] == 0 and row['responsible_person_outside']
             for row in occupancy],
    }
    channel_dir = attempt / 'channels'
    channel_dir.mkdir(exist_ok=False)
    evidence = []
    for channel in channels:
        name = channel['name']
        reference = 'channels/' + name + '.jsonl'
        with (attempt / reference).open('x') as stream:
            for row, value in zip(vehicle, values[name]):
                stream.write(json.dumps({'time_s': row['time_s'], 'value': value}) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': reference})
    result = {
        'case_id': case, 'measured_values': measured,
        'target_checks': [{'target': 'original three-duty source window joined',
                           'requested': True, 'measured': True,
                           'method': 'measure: six source hashes, 600 synchronized frames',
                           'tolerance': 0, 'matched': True,
                           'physical_cause_confirmed': False,
                           'cause_evidence': list(SOURCES)}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'Saved source measurement complete; physical and legal review pending',
        'physical_failure_flags': ['Original engine, wheel, brake effectiveness and attendance need physical review'],
        'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': evidence, 'realized_observables': {},
        'provenance_kind': 'synthetic_local_diagnostic' if diagnostic else 'original_source_review',
        'accepted': False,
    }
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': {
                  'text_0_three_duties': {
                      'value': measured, 'method': 'finalize', 'sources': hashes},
                  'reviewed_scope_0_three_duties': {
                      'value': measured, 'method': 'finalize', 'sources': hashes}},
              'source_complete': True, 'diagnostic_fixture': diagnostic,
              'physical_or_legal_acceptance': False}
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
