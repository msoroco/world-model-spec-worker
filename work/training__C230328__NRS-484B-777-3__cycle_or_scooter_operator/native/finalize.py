"""Saved-only rider geometry. No geometric cutoff or legal verdict is inferred."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_abreast import CAMERAS, measure


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def measure_roadway_riding(geometry, context):
    return {'rider_count': geometry['rider_count'],
            'source_review_kind': context['review_kind'],
            'roadway_source': context['roadway_boundary_source'],
            'bicycle_device_source': context['rider_device_source'],
            'original_physical_qualification_review_pending': True}


def measure_exclusive_use_exception(geometry, context):
    return {'reviewed': context['exclusive_use_reviewed'],
            'exclusive_use_source': context['exclusive_use_source'],
            'exclusive_use_review_source': context['exclusive_use_review_source'],
            'legal_exception_result': None}


MEASUREMENTS = (
    ('roadway_riding', measure_roadway_riding, ('rider_poses.jsonl', 'road_context.json')),
    ('exclusive_use_exception', measure_exclusive_use_exception,
     ('rider_poses.jsonl', 'road_context.json')),
)


def finalize(attempt, output):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text())
    for name in ('video_frames.jsonl', 'rider_poses.jsonl', 'road_context.json',
                 'trace.jsonl', 'capture/evidence.jsonl'):
        required(root, name)
    for name in CAMERAS:
        required(root, name + '.mkv')
    context = json.loads((root / 'road_context.json').read_text())
    if context.get('assignment_id') != config['assignment_id']:
        raise ValueError('Saved roadway review belongs to another assignment')
    if context.get('legal_verdict') is not None:
        raise ValueError('Saved context asserts a legal verdict')
    geometry = measure(root)
    expected = 2 if config['case_id'].endswith('__controlled_1') else 3
    if geometry['rider_count'] != expected:
        raise ValueError('Selected rider count differs from original source')
    frames = [json.loads(line) for line in (root / 'video_frames.jsonl').read_text().splitlines()]
    poses = [json.loads(line) for line in (root / 'rider_poses.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in (root / 'trace.jsonl').read_text().splitlines()]
    events = [json.loads(line) for line in (root / 'capture/evidence.jsonl').read_text().splitlines()]
    if any(len(stream) != 600 for stream in (frames, poses, trace, events)):
        raise ValueError('Full 600-frame saved source required')
    for frame, pose, state, event in zip(frames, poses, trace, events):
        original = frame['native_frame']
        if (pose['native_frame'] != original or state.get('frame') != original or
                event.get('original_frame') != original or
                any(frame.get('camera_native_frames', {}).get(name) != original for name in CAMERAS)):
            raise ValueError('Saved rider, trace and camera frame join differs')
    measurements = {key: {'method': function.__name__,
                          'value': function(geometry, context),
                          'sources': {name: digest(root / name) for name in sources}}
                    for key, function, sources in MEASUREMENTS}
    channel_dir = root / 'channels'
    channel_dir.mkdir(exist_ok=True)
    recording = []
    for item in config['recording_description']['channels']:
        name = item['name']
        path = channel_dir / (name.replace('/', '_') + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': frame['time_s'],
            'value': {'native_frame': frame['native_frame'],
                      'riders': pose['riders'],
                      'source_kind': pose['source_kind']}}, separators=(',', ':')) + '\n'
            for frame, pose in zip(frames, poses)))
        recording.append({'name': name, 'unit': item['unit'],
                          'reference': 'channels/' + path.name})
    for item in config['recording_description']['context_inputs']:
        name = item['name']
        path = channel_dir / (name + '.json')
        path.write_text(json.dumps({name: context}, separators=(',', ':')) + '\n')
        recording.append({'name': name, 'unit': item['unit'],
                          'reference': 'channels/' + path.name})
    diagnostic = context['review_kind'] == 'synthetic_diagnostic'
    overlaps = [sample['pairwise'] for sample in geometry['per_frame_geometry']]
    matching = all(len(pairwise) == expected * (expected - 1) // 2 for pairwise in overlaps)
    result = {'case_id': config['case_id'],
              'measured_values': {'rider_count': expected,
                                  'pair_count_per_frame': len(overlaps[0]),
                                  'abreast_classification': None,
                                  'legal_result': None},
              'target_checks': [{'target': 'requested_rider_count',
                'requested': expected, 'measured': geometry['rider_count'],
                'method': '600 source-joined original rider identities', 'tolerance': 0,
                'matched': matching, 'physical_cause_confirmed': False,
                'cause_evidence': ['rider_poses.jsonl', 'road_context.json']}],
              'setup_confirmed': not diagnostic, 'behavior_attempted': not diagnostic,
              'maneuver_completed': not diagnostic,
              'termination_reason': 'full original source window' if not diagnostic else 'synthetic diagnostic window',
              'physical_failure_flags': ['original_rider_and_roadway_review_pending'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': recording,
              'realized_observables': {'rider_count': {'value': expected,
                'unit': 'count', 'method': 'saved rider identity join',
                'time_window': '600 frames', 'statistic': 'exact',
                'reference': 'rider_poses.jsonl'}},
              'provenance_kind': 'synthetic_cpu' if diagnostic else 'native',
              'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    if (root / 'result.json').exists():
        raise ValueError('Saved processing cannot overwrite a prior result')
    (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    report = {'format': 'c230328-abreast-saved-analysis-v1',
              'case_id': config['case_id'], 'measurements': measurements,
              'source_geometry': geometry,
              'original_native_source': not diagnostic,
              'abreast_classification': None, 'legal_verdict': None}
    Path(output).write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = finalize(args.attempt, args.output)
    print(json.dumps({'case_id': report['case_id'],
                      'source_frames': report['source_geometry']['sample_count'],
                      'legal_verdict': None}))


if __name__ == '__main__':
    main()
