"""Check fixed intersection context and the sampled parked-body contrast."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c110454-450-fallbacks'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(source_b):
    manifest = read(HERE / 'execution-manifest.json')
    if {entry['case_id'].rsplit('__', 1)[-1] for entry in manifest['cases']} != {'probe_a', 'probe_b'}:
        raise ValueError('Selected comparison pair changed')
    pair = {}
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        attempt = (SCRATCH / f'compat3-{suffix}-primary') if suffix == 'probe_a' else source_b
        processing = read(SCRATCH / f'saved3-{suffix}-primary/v0001/processing.json')
        construction = read(HERE / entry['construction'])
        config = json.loads(next(x['content'] for x in construction['files'] if x['path'] == 'config.json'))
        if sha(HERE / entry['construction']) != entry['construction_sha256']:
            raise ValueError('Selected construction changed')
        source = rows(attempt / 'native_samples.jsonl')
        frame_map = rows(attempt / 'video_frames.jsonl')
        if len(source) != 600 or len(frame_map) != 600 or any(
                row['native_frame'] != frame['carla_frame'] or
                abs(row['time_s'] - frame['time_s']) > 1e-8
                for row, frame in zip(source, frame_map)):
            raise ValueError('Original source frame join changed')
        hashes = {name: sha(attempt / name) for name in ('native_samples.jsonl',
            'video_frames.jsonl', 'road_geometry.json', 'road.xodr')}
        if any(processing['original_source_hashes'].get(name) != digest for name, digest in hashes.items()):
            raise ValueError('Original saved source changed')
        exceptions = [row.get('exception_source') for row in source]
        if any(not isinstance(value, dict) or
                value.get('other_traffic_actor_count') != 0 or
                value.get('native_signal_count') != 0 or
                value.get('authored_law_direction_count') != 0
                for value in exceptions):
            raise ValueError('Source-qualified exception context differs')
        parked = sum(abs(row['speed_mps']) < 0.05 for row in source)
        if parked != 360:
            raise ValueError('Parked interval differs')
        public = read(HERE / f'current-v2-matrix/{suffix}/primary/compatibility.json')
        overlap = public['measurement_examples']['intersection_parking_footprint']['value']['max_intersection_body_overlap_m2']
        pair[suffix] = {'case_id': entry['case_id'], 'source_sha256': hashes,
                        'construction_sha256': entry['construction_sha256'],
                        'parked_frames': parked, 'sampled_overlap_m2': overlap,
                        'camera_names': [camera['name'] for camera in config['cameras']],
                        'engineering_knobs': config['engineering_knobs'],
                        'required_atoms': config['required_atoms'],
                        'duration_s': config['duration_s'], 'rate_hz': config['rate_hz']}
    a, b = pair['probe_a'], pair['probe_b']
    for name in ('road_geometry.json', 'road.xodr'):
        if a['source_sha256'][name] != b['source_sha256'][name]:
            raise ValueError('Intersection map changed across comparison')
    for name in ('camera_names', 'engineering_knobs', 'required_atoms', 'duration_s', 'rate_hz', 'parked_frames'):
        if a[name] != b[name]:
            raise ValueError('Fixed comparison condition changed: ' + name)
    if (a['sampled_overlap_m2'], b['sampled_overlap_m2']) != (0.0, 11.44):
        raise ValueError('Parking footprint contrast changed')
    return {'format': 'c110454-selected-cpu-comparison-audit', 'passed': True,
            'cases': pair, 'deliberate_difference': 'parking target and measured sampled full-body intersection overlap',
            'fixed_conditions': ['same Native intersection map', 'same actor and route controller',
                                 'same 20 Hz / 30 s and four-camera profile',
                                 'same source-qualified zero-count diagnostic exception context'],
            'original_native_observed': False, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False,
            'limitations': 'Synthetic CPU source join; original map, motion, pixels and exception judgments remain local review tasks'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-b', type=Path,
                        default=SCRATCH / 'compat3-probe_b-primary')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.source_b)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'passed': True, 'audit_sha256': sha(args.output)}))
