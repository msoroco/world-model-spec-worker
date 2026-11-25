"""Finalize saved flashing-arrow sources without asserting lawful status or a verdict."""
import argparse
import hashlib
import json
from pathlib import Path

PREFIX = 'training__C111603__NRS-484B-307-7a__motor_vehicle_driver__'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('turn-history.jsonl', 'arrow-context.json', 'video_frames.jsonl',
           'trace.jsonl', 'capture/evidence.jsonl')


def sha(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def inside(point):
    return -4 <= point[0] <= 4 and -4 <= point[1] <= 4


def measure(attempt):
    attempt = Path(attempt)
    for name in SOURCES:
        sha(attempt / name)
    rows = read_rows(attempt / 'turn-history.jsonl')
    mapping = read_rows(attempt / 'video_frames.jsonl')
    trace = read_rows(attempt / 'trace.jsonl')
    context = json.loads((attempt / 'arrow-context.json').read_text())
    if len(rows) != 600 or len(mapping) != 600 or len(trace) != 600:
        raise ValueError('Expected 600 saved original frame and time joins')
    source_kind = context.get('source_kind')
    if source_kind not in ('original_native', 'synthetic_cpu_diagnostic'):
        raise ValueError('Arrow context is not from a declared source')
    first_entry = None
    last_other = None
    lit = 0
    ego_values, other_values, arrow_values = [], [], []
    for index, (row, video, pose) in enumerate(zip(rows, mapping, trace)):
        if (row.get('frame') != index or abs(row.get('time_s', -1) - index / 20) > 1e-6
                or abs(video.get('time_s', -1) - index / 20) > 1e-6
                or pose.get('frame') != index):
            raise ValueError('Saved source frame or time join differs')
        if source_kind == 'original_native':
            if (row.get('source_kind') != 'original_native'
                    or row.get('native_frame') != video.get('native_frame')
                    or context.get('actual_arrow_pixels_reviewed') is not False
                    or row.get('other_traffic_lawful_status') is not None
                    or row.get('pedestrian_lawful_status') is not None
                    or row.get('cautiousness_legal_judgment') is not None):
                raise ValueError('Native arrow or legal-source claim differs')
            ego = row['ego']['position_m']
            other = row['other_vehicle']['position_m']
            arrow = row['requested_arrow_lit']
        else:
            if (row.get('original_native_observed') is not False
                    or row['requested_arrow']['governs_ego'] != 'requested_unverified'
                    or row.get('other_traffic_lawful_status') != 'external_review_pending'
                    or context.get('official_arrow_verified') is not False):
                raise ValueError('Synthetic request asserts unreviewed source')
            ego = row['requested_ego_xy_m']
            other = row['requested_other_xy_m']
            arrow = row['requested_arrow']['flashing_yellow_lit']
        ego_values.append(ego)
        other_values.append(other)
        arrow_values.append(arrow)
        lit += bool(arrow)
        if inside(other):
            last_other = index
        if first_entry is None and inside(ego):
            first_entry = index
    if first_entry is None or last_other is None:
        raise ValueError('Turn or other-traffic entry is absent from saved sources')
    return {'frames': 600, 'first_ego_entry_frame': first_entry,
            'last_other_inside_frame': last_other,
            'other_inside_at_ego_entry': inside(other_values[first_entry]),
            'requested_arrow_lit_frames': lit,
            'arrow_governance_verified': False,
            'other_traffic_lawful_status_verified': False,
            'pedestrian_lawful_status_verified': False,
            'cautiousness_legal_judgment': None,
            'legal_verdict_claimed': False,
            'source_kind': source_kind,
            'channels': {'ego_motion': ego_values, 'other_motion': other_values,
                         'arrow_request': arrow_values}}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Use a fresh saved attempt; retain prior sources')
    for name in (*SOURCES, *[view + '.mkv' for view in VIEWS],
                 'config.json', 'construction.json'):
        sha(attempt / name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case = config.get('case_id')
    if case not in (PREFIX + 'controlled_1', PREFIX + 'controlled_2') or construction.get('case_id') != case:
        raise ValueError('Exact selected flashing-arrow case differs')
    metric = measure(attempt)
    mapping = read_rows(attempt / 'video_frames.jsonl')
    history = read_rows(attempt / 'turn-history.jsonl')
    metric['channels']['turn_history'] = history
    metric['channels']['four_camera_video'] = [
        {'video_frame': frame['video_frame'],
         'source_views': [view + '.mkv' for view in VIEWS]}
        for frame in mapping]
    description = construction['recording_description']
    channels = attempt / 'channels'
    channels.mkdir()
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in metric['channels']:
            raise ValueError('Unknown declared source channel: ' + name)
        ref = 'channels/' + name + '.jsonl'
        with (attempt / ref).open('x') as stream:
            for frame, value in zip(mapping, metric['channels'][name]):
                stream.write(json.dumps({'time_s': frame['time_s'], 'value': value}) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': ref})
    contexts = {
        'source_law_and_signal_governance': {
            'law_id': config['law_id'], 'signal_request_source': 'arrow-context.json',
            'signal_request_sha256': sha(attempt / 'arrow-context.json'),
            'governance_status': 'original_source_review_pending'},
        'lawful_status_review': {
            'pedestrian': 'original_source_review_pending',
            'other_traffic': 'original_source_review_pending',
            'cautiousness': 'original_source_review_pending'},
    }
    for context in description['context_inputs']:
        name = context['name']
        if name not in contexts:
            raise ValueError('Unknown declared source context: ' + name)
        ref = 'channels/' + name + '.json'
        (attempt / ref).write_text(json.dumps({name: contexts[name]}, indent=2) + '\n')
        evidence.append({'name': name, 'unit': context['unit'], 'reference': ref})
    measured = {key: value for key, value in metric.items() if key != 'channels'}
    source_hashes = {name: sha(attempt / name) for name in SOURCES}
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': {'flashing_arrow_yield_measurement': {
                  'method': 'measure', 'value': measured, 'sources': source_hashes}},
              'source_complete': True, 'diagnostic_fixture':
                  metric['source_kind'] != 'original_native',
              'physical_or_legal_acceptance': False,
              'limitations': ['Arrow governance, lawful users and cautiousness require independent original-source review']}
    result = {'case_id': case, 'measured_values': measured,
              'target_checks': [{'target': 'source-joined turn relative to other passage',
                                 'requested': True, 'measured': True,
                                 'method': '600 saved frames and two participant positions',
                                 'tolerance': 0, 'matched': True,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(SOURCES)}],
              'setup_confirmed': True, 'behavior_attempted': True,
              'maneuver_completed': True,
              'termination_reason': '600-frame source analysis; legal review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [view + '.mkv' for view in VIEWS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {}, 'accepted': False,
              'provenance_kind': ('native' if metric['source_kind'] == 'original_native'
                                  else 'synthetic_local_diagnostic'),
              'legal_verdict_claimed': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
