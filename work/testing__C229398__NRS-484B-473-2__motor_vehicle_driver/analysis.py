"""Finalize source-bound parked-light observations from saved original files."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from parked_lamps import CASES, ROW_SOURCES, valid_number
from source_packet import ASSIGNMENT, verify


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(attempt):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text())
    construction = json.loads(required(root, 'construction.json').read_text())
    case_id = config['selected_case_id']
    case = next((item for item in CASES if case_id == ASSIGNMENT + '__' + item.name), None)
    if case is None or construction['case_id'] != case_id:
        raise ValueError('exact parked-light construction differs')
    required(root, 'parking_lawfulness.txt')
    diagnostic = (root / 'fixture-provenance.json').is_file()
    packet_path = required(root, 'reviewed-packet.json' if diagnostic else
                           'source-packet.json')
    checked = verify(packet_path, diagnostic_fixture=diagnostic)
    if checked['case_id'] != case_id:
        raise ValueError('saved packet selects another parked-light case')
    scene = json.loads(packet_path.read_text())['scene']
    ticks = [json.loads(line) for line in
             required(root, 'original-ticks.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in
             required(root, 'trace.jsonl').read_text().splitlines()]
    mapping = [json.loads(line) for line in
               required(root, 'video_frames.jsonl').read_text().splitlines()]
    expected = 9 if diagnostic else 900
    if len(ticks) != expected or len(trace) != expected or len(mapping) != expected:
        raise ValueError('saved original parked-light frame history incomplete')
    first_frame = ticks[0]['original_frame']
    first_time = ticks[0]['time_s']
    for index, (row, state, frame) in enumerate(zip(ticks, trace, mapping)):
        if (row.get('original_frame') != first_frame + index or
                row.get('vehicle_id') != scene['vehicle_id'] or
                not valid_number(row.get('time_s')) or
                abs(row['time_s'] - first_time - index / 20) > .005 or
                state.get('frame') != row['original_frame'] or
                frame.get('carla_frame') != row['original_frame'] or
                frame.get('time_s') != state.get('time_s')):
            raise ValueError('saved original parked-light frame/time join differs')
        for name in ROW_SOURCES:
            if row.get(name + '_source_sha256') != checked['source_hashes'][name]:
                raise ValueError('saved original parked-light source join differs: ' + name)
        if (row.get('night') is not case.night or
                row.get('lawful_park') is not case.lawful_park or
                row.get('lamp_mode') != case.lamp_mode or
                row.get('auxiliary_lamp') != case.auxiliary_lamp or
                not valid_number(row.get('speed_mps')) or
                not valid_number(row.get('beam_aim_deg'))):
            raise ValueError('saved parked-light state readback differs')
        if index >= scene['park_start_frame'] and row['speed_mps'] > .1:
            raise ValueError('saved original vehicle did not remain parked')
    if not diagnostic:
        from capture_seal import seal
        seal(root)
    return case_id, case, scene, ticks, trace, checked, diagnostic


def analyze(attempt, output):
    root = Path(attempt)
    case_id, case, scene, ticks, trace, checked, diagnostic = measure(root)
    construction = json.loads(required(root, 'construction.json').read_text())
    packet_name = 'reviewed-packet.json' if diagnostic else 'source-packet.json'
    inputs = (packet_name, 'parking_lawfulness.txt', 'nighttime.txt',
              'displayed_lights.txt', 'beam_aim.txt', 'cowl_lamp.txt',
              'parking_lamp.txt', 'vehicle_motion.txt', 'original-ticks.jsonl')
    hashes = {name: sha(required(root, name)) for name in inputs}
    values = {
        'qualifying_vehicle_and_highway': {'vehicle_id': scene['vehicle_id'],
                                           'highway': scene['highway'],
                                           'source_sha256': checked['source_hashes']['highway']},
        'parking_and_nighttime': {'lawful_park': case.lawful_park,
                                  'night': case.night,
                                  'parked_frames': len(ticks) - scene['park_start_frame']},
        'displayed_and_auxiliary_lamps': {'displayed_lamp_mode': case.lamp_mode,
                                         'auxiliary_lamp': case.auxiliary_lamp,
                                         'beam_aim_deg_last': ticks[-1]['beam_aim_deg']},
        'legal_judgment': None}
    reports = {name: {'method': 'measure', 'value': values[name], 'sources': hashes}
               for name in ('qualifying_vehicle_and_highway',
                            'parking_and_nighttime', 'displayed_and_auxiliary_lamps')}
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'measurements': reports, 'diagnostic_fixture': diagnostic,
              'legal_verdict_claimed': False, 'limitations': [
                  'Legal dimming judgment remains source-grounded; no numeric legal cutoff is invented.',
                  'CPU diagnostic media does not establish original Native physical success.']}
    channels = root / 'channels'
    channels.mkdir(exist_ok=False)
    observed = {
        'original_vehicle_motion': {'vehicle_id': scene['vehicle_id'],
                                    'original_frame_count': len(ticks),
                                    'source_sha256': hashes['original-ticks.jsonl']},
        'lamp_state': {'displayed_lamp_mode': case.lamp_mode,
                       'auxiliary_lamp': case.auxiliary_lamp,
                       'beam_aim_deg_last': ticks[-1]['beam_aim_deg'],
                       'source_sha256': hashes['original-ticks.jsonl']},
        'camera_pixels': {'views': ['overview', 'approach', 'reference_corner',
                                    'driver_reference'],
                          'source_sha256': sha(required(root, 'video_frames.jsonl'))}}
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        if name not in observed:
            raise ValueError('unexpected parked-light channel: ' + name)
        target = channels / (name + '.jsonl')
        target.write_text(''.join(json.dumps({'time_s': row['time_s'],
                                              'value': observed[name]}) + '\n'
                                  for row in trace))
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': str(target.relative_to(root))})
    for context in construction['recording_description']['context_inputs']:
        name = context['name']
        if name not in checked['source_hashes']:
            raise ValueError('unexpected parked-light context: ' + name)
        target = channels / ('context_' + name + '.jsonl')
        target.write_text(json.dumps({name: {
            'source_sha256': checked['source_hashes'][name],
            'review_status': 'synthetic' if diagnostic else 'reviewed'}}) + '\n')
        evidence.append({'name': name, 'unit': context['unit'],
                         'reference': str(target.relative_to(root))})
    result = {'case_id': case_id, 'measured_values': values,
              'target_checks': [{'target': 'source-bound parked-light state and 20 Hz stationary interval',
                                 'requested': case_id, 'measured': values,
                                 'method': 'analysis.measure', 'tolerance': 0,
                                 'matched': True, 'physical_cause_confirmed': False,
                                 'cause_evidence': hashes}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Saved original review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in
                                   ('overview', 'approach', 'reference_corner',
                                    'driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'legal_judgment': None, 'physical_acceptance_claimed': False}
    (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    Path(output).write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(analyze(args.attempt, args.output)['case_id'])
