"""Independent source-bound comparison of the two right-pass attempts."""
import argparse
import hashlib
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text())


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(plan_path, attempts):
    plan = load(plan_path)
    comparison = plan['comparisons'][0]
    if len(attempts) != 2 or len(set(attempts)) != 2:
        raise ValueError('Comparison requires two distinct attempts')
    records = []
    for expected, attempt in zip(comparison['case_ids'], attempts):
        folder = Path(attempt)
        config = load(folder / 'config.json')
        if config['case_id'] != expected or config['assignment_id'] != plan['assignment_id']:
            raise ValueError('Comparison case identity differs')
        native = lines(folder / 'native_motion.jsonl')
        trace = lines(folder / 'trace.jsonl')
        video = lines(folder / 'video_frames.jsonl')
        if len(native) != len(trace) or len(native) != len(video) or len(native) != 600:
            raise ValueError('Comparison source duration differs')
        for i, (motion, row, frame) in enumerate(zip(native, trace, video)):
            if (motion['native_frame'] != i or row['frame'] != i or
                    frame['carla_frame'] != i or abs(row['time_s'] - frame['time_s']) > 1e-6 or
                    abs(motion['time_s'] - row['time_s']) > 1e-6):
                raise ValueError('Comparison frame or time join differs')
        provenance = {row['source_kind'] for row in native}
        if len(provenance) != 1 or not provenance <= {'synthetic_cpu_pass', 'original_native_capture'}:
            raise ValueError('Comparison source provenance differs')
        if provenance == {'original_native_capture'} and not (folder / 'capture-seal.json').is_file():
            raise ValueError('Original comparison lacks capture seal')
        camera = [(x['name'], x['width'], x['height'], x['fov_deg'], x['pose_strategy'])
                  for x in config['cameras']]
        lead = native[0]['lead']
        ego = native[0]['ego']
        records.append({
            'case_id': expected,
            'source_kind': next(iter(provenance)),
            'road_sha256': sha(folder / 'road.xodr'),
            'native_motion_sha256': sha(folder / 'native_motion.jsonl'),
            'trace_sha256': sha(folder / 'trace.jsonl'),
            'video_frames_sha256': sha(folder / 'video_frames.jsonl'),
            'camera': camera,
            'duration': (config['duration_s'], config['rate_hz'], config['frames']),
            'blueprints': (ego['blueprint_id'], lead['blueprint_id']),
            'speeds': (ego['speed_mps'], lead['speed_mps']),
            'initial_longitudinal': (ego['center_xyz_m'][0], lead['center_xyz_m'][0]),
            'lateral': (ego['center_xyz_m'][1], lead['center_xyz_m'][1]),
            'frame_times': [(m['time_s'], m['ego']['center_xyz_m'][0], m['lead']['center_xyz_m'][0])
                            for m in native],
        })
    a, b = records
    for key in ('source_kind', 'road_sha256', 'camera', 'duration', 'blueprints',
                'speeds', 'initial_longitudinal', 'frame_times'):
        if a[key] != b[key]:
            raise ValueError('Comparison fixed condition differs: ' + key)
    if a['lateral'] == b['lateral']:
        raise ValueError('Comparison has no deliberate lateral route difference')
    return {
        'format': 'c146314-independent-comparison-audit-v1',
        'comparison_id': comparison['comparison_id'],
        'case_ids': comparison['case_ids'],
        'source_kind': a['source_kind'],
        'source_hashes': {r['case_id']: {k: r[k] for k in
                          ('road_sha256', 'native_motion_sha256', 'trace_sha256', 'video_frames_sha256')}
                          for r in records},
        'fixed_conditions_checked': ['road source', 'four camera policy', 'duration', 'actor blueprints',
                                     'longitudinal speed and timing', '600 source frame joins'],
        'deliberate_lateral_placements_m': {r['case_id']: r['lateral'] for r in records},
        'diagnostic_fixture': a['source_kind'] == 'synthetic_cpu_pass',
        'physical_comparison_complete': False,
        'legal_verdict': None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    parser.add_argument('--attempt', action='append', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.plan, args.attempt)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'comparison_id': result['comparison_id'], 'cases': 2,
                      'physical_comparison_complete': False}))


if __name__ == '__main__':
    main()
