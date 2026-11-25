"""Selected saved-only C228133 analyzer; no legal or physical acceptance claim."""

import argparse
import json
from pathlib import Path

from saved_source_analysis import analyze, digest


VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(root, name):
    return [json.loads(line) for line in required(root, name).read_text().splitlines()
            if line.strip()]


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists() or \
            (attempt / 'channels').exists():
        raise ValueError('Retain previous saved analysis; use a fresh attempt')
    config = json.loads(required(attempt, 'config.json').read_text())
    construction = json.loads(required(attempt, 'construction.json').read_text())
    if config.get('case_id') != construction.get('case_id') or \
            config.get('selected_case_id') != config.get('case_id') or \
            config.get('duration_s') != 30 or config.get('rate_hz') != 20 or \
            config.get('case_suffix') not in ('reference', 'contrast'):
        raise ValueError('Exact 30-second selected case configuration differs')
    expected = config['case_suffix'] == 'contrast'
    if config.get('pedestrian_enters_highway_requested') is not expected:
        raise ValueError('Requested comparison variable differs')
    if construction.get('recording_description') != config.get('recording_description'):
        raise ValueError('Construction recording plan differs')
    mapping, trace = rows(attempt, 'video_frames.jsonl'), rows(attempt, 'trace.jsonl')
    if len(mapping) != 600 or len(trace) != 600:
        raise ValueError('Incomplete 600-frame saved source/trace interval')
    for index, (frame, point) in enumerate(zip(mapping, trace)):
        if frame.get('video_frame') != index or \
                point.get('frame') != frame.get('carla_frame') or \
                abs(point.get('time_s', -1) - frame.get('time_s', -2)) > 1e-6:
            raise ValueError('Saved original trace/frame identity differs')
    review = analyze(attempt)
    measurement = review['measurement']
    if measurement['frame_count'] != 600:
        raise ValueError('Saved entry measurement is not full duration')
    observed = bool(measurement['entry_events'])
    source_dir = attempt / 'reviewed-source'
    pedestrian = rows(source_dir, 'native-pedestrian-frames.jsonl')
    signal = rows(source_dir, 'native-signal-frames.jsonl')
    device = rows(source_dir, 'native-pedestrian-device-frames.jsonl')
    streams = {
        'pedestrian_footprint': [row['footprint_roadward_y_m']
                                 for row in pedestrian],
        'governing_red_and_turn_arrow': [
            {'red': row['red'], 'green_turn_arrow': row['green_turn_arrow'],
             'governs_pedestrian': row['governs_pedestrian']}
            for row in signal],
        'other_device_permission': [row['permits_proceed'] for row in device],
    }
    channels = attempt / 'channels'
    channels.mkdir()
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        if name not in streams:
            raise ValueError('Unexpected C228133 recording channel: ' + name)
        path = channels / (name + '.jsonl')
        path.write_text(''.join(json.dumps({
            'time_s': frame['time_s'], 'value': value}, allow_nan=False) + '\n'
            for frame, value in zip(mapping, streams[name])))
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/' + path.name})
    context = {
        'native_road_boundary': {
            'source': 'road-boundary.json',
            'sha256': digest(attempt / 'road-boundary.json')},
        'governing_signal_authority': {
            'source': 'governing-device-authority.json',
            'sha256': digest(attempt / 'governing-device-authority.json')},
        'highway_authority': {
            'source': 'highway-authority.json',
            'sha256': digest(attempt / 'highway-authority.json')},
    }
    (attempt / 'saved-law-context.json').write_text(json.dumps(context, indent=2) + '\n')
    for item in construction['recording_description']['context_inputs']:
        if item['name'] not in context:
            raise ValueError('Unexpected C228133 context input')
        evidence.append({'name': item['name'], 'unit': item['unit'],
                         'reference': 'saved-law-context.json'})
    result = {
        'case_id': config['case_id'],
        'measured_values': {
            'pedestrian_enters_highway': observed,
            'potential_9c_entry_frames': measurement['potential_9c_entry_frames']},
        'target_checks': [{
            'target': 'pedestrian_enters_highway', 'requested': expected,
            'measured': observed,
            'method': 'source-reviewed pedestrian footprint transition at authority-bound boundary',
            'tolerance': 0, 'matched': observed is expected,
            'physical_cause_confirmed': False,
            'cause_evidence': ['native-pedestrian-frames.jsonl',
                               'independent-review.json', 'highway-authority.json']}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': '600 synchronized saved frames analyzed; physical review pending',
        'physical_failure_flags': ['official signal pixels, governance and legal status require independent acceptance'],
        'trace_reference': 'trace.jsonl',
        'video_references': [view + '.mkv' for view in VIEWS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': construction['recording_description'],
        'recording_evidence': evidence,
        'realized_observables': {
            'highway_entry_event_count': {
                'value': len(measurement['entry_events']), 'unit': 'count',
                'method': 'source-reviewed footprint transition',
                'time_window': 'full 30-second saved interval',
                'statistic': 'transition count',
                'reference': 'reviewed-source/measurement.json'}},
        'provenance_kind': ('synthetic_local_diagnostic' if review['diagnostic_fixture']
                            else 'source_review_unverified'),
        'accepted': False,
        'legal_verdict_claimed': False,
    }
    from worker_exchange.native_output import validate_result
    validate_result(result)
    output.write_text(json.dumps({
        'format': 'c228133-saved-analysis-v1',
        'case_id': config['case_id'],
        'measurements': {'road_entry': {
            'method': 'finalize', 'value': measurement,
            'sources': {name: digest(attempt / name) for name in
                        ('native-pedestrian-frames.jsonl', 'road-boundary.json',
                         'independent-review.json')}},
            'signal_context': {
                'method': 'finalize',
                'value': {'frame_count': len(signal), 'reviewed_diagnostic':
                          review['diagnostic_fixture']},
                'sources': {name: digest(attempt / name) for name in
                            ('native-signal-frames.jsonl',
                             'governing-device-authority.json',
                             'independent-review.json')}},
            'other_device_context': {
                'method': 'finalize',
                'value': {'frame_count': len(device), 'permission_frames':
                          sum(bool(item['permits_proceed']) for item in device)},
                'sources': {name: digest(attempt / name) for name in
                            ('native-pedestrian-device-frames.jsonl',
                             'independent-review.json')}}},
        'physical_acceptance_claimed': False,
        'legal_verdict_claimed': False}, indent=2, allow_nan=False) + '\n')
    (attempt / 'result.json').write_text(json.dumps(result, indent=2,
                                                  allow_nan=False) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
