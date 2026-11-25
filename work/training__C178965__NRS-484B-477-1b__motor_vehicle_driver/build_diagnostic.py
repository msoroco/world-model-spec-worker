"""Build bounded synthetic alley-width inputs for CPU protocol checking only."""
import hashlib
import json
from pathlib import Path

from native.geometry import open_drive

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'work/training__C10014__NRS-484B-477-2__motor_vehicle_driver/update041-diagnostic-reference.json'
ASSIGNMENT = HERE.name


def text_rows(value, count):
    return [json.loads(line) for line in value.splitlines()[:count]]


def encoded_rows(values):
    return ''.join(json.dumps(value, separators=(',', ':')) + '\n' for value in values)


def main():
    base = json.loads(SOURCE.read_text())
    source_files = base['files']
    count = 9
    for suffix, width in (('controlled_1', 7.5), ('controlled_at_10', 6.648),
                          ('controlled_2', 6.0)):
        files = {name: encoded_rows(text_rows(source_files[name], count)) for name in
                 ('trace.jsonl', 'video_frames.jsonl', 'capture/evidence.jsonl',
                  'capture/native/frames.jsonl')}
        trace_source = [json.loads(row) for row in files['trace.jsonl'].splitlines()]
        for row in trace_source:
            row['velocity_mps'] = [row['speed_mps'], 0.0, 0.0]
        files['trace.jsonl'] = encoded_rows(trace_source)
        files['road.xodr'] = open_drive(width)
        files['capture/recorder_info.txt'] = source_files['capture/recorder_info.txt']
        frames = [json.loads(row) for row in files['video_frames.jsonl'].splitlines()]
        trace = [json.loads(row) for row in files['trace.jsonl'].splitlines()]
        for frame in frames:
            frame['camera_native_frames'] = {name: frame['native_frame'] for name in
                                             ('overview', 'approach', 'reference_corner',
                                              'driver_reference')}
        files['video_frames.jsonl'] = encoded_rows(frames)
        poses = []
        for index, (frame, t) in enumerate(zip(frames, trace)):
            if frame['native_frame'] != t['frame'] or abs(frame['time_s'] - t['time_s']) > 1e-4:
                raise ValueError('Source graph and trace frame map differ')
            x, y = t['position_m'][:2]
            poses.append({'video_frame': index, 'native_frame': frame['native_frame'],
                          'time_s': frame['time_s'],
                          'subject': {'vehicle_id': 'synthetic-subject', 'xy_m': [x, y],
                                      'yaw_rad': 0, 'half_length_m': 2.0,
                                      'half_width_m': .5, 'speed_mps': t['speed_mps']},
                          'other': {'vehicle_id': 'synthetic-other',
                                    'xy_m': [x, .6 - width], 'yaw_rad': 0,
                                    'half_length_m': 2.0, 'half_width_m': .5,
                                    'speed_mps': 0}})
        files['vehicle-poses.jsonl'] = encoded_rows(poses)
        inventory = {'assignment_id': ASSIGNMENT, 'source_kind': 'synthetic_native_sample',
                     'alley_lateral_edges_m': [-width, 0],
                     'boundary_measurement_source_id': 'synthetic-open-drive-width',
                     'public_highway_source_id': 'synthetic-only-public-highway',
                     'city_block_source_id': 'synthetic-only-block',
                     'rear_access_source_id': 'synthetic-only-rear-access',
                     'abutting_property_source_id': 'synthetic-only-abutting-property',
                     'non_culdesac_source_id': 'synthetic-only-open-ends',
                     'local_jurisdiction_source_id': 'synthetic-only-jurisdiction',
                     'local_ordinance_review_source_id': 'synthetic-only-ordinance',
                     'other_alley_scope_review_source_id': 'synthetic-only-other-alley',
                     'halt_purpose_review_source_id': 'synthetic-only-purpose',
                     'occupant_activity_review_source_id': 'synthetic-only-occupancy',
                     'traffic_conflict_review_source_id': 'synthetic-only-conflict',
                     'official_direction_review_source_id': 'synthetic-only-direction',
                     'source_status': 'synthetic software protocol only; no site or ordinance finding'}
        files['alley-inventory.json'] = json.dumps(inventory, indent=2) + '\n'
        manifest = {'extraction_confirmed': True, 'frames': count,
                    'synthetic_diagnostic': True,
                    'sources': {name: hashlib.sha256(files[name].encode()).hexdigest()
                                for name in ('road.xodr', 'trace.jsonl')}}
        files['capture/manifest.json'] = json.dumps(manifest, separators=(',', ':'))
        spec = {'files': files,
                'graphs': base['graphs'][:count],
                'videos': [dict(video, frames=count) for video in base['videos']]}
        spec_path = HERE / f'diagnostic-{suffix}.json'
        spec_path.write_text(json.dumps(spec, separators=(',', ':')) + '\n')
        sha = hashlib.sha256(spec_path.read_bytes()).hexdigest()
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json',
                               'source': str(spec_path.relative_to(ROOT)), 'sha256': sha}],
                  'generator': {'source': str(spec_path.relative_to(ROOT)), 'sha256': sha}}
        recipe_path = HERE / f'diagnostic-{suffix}-recipe.json'
        recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
        print(suffix, 'spec_sha256', sha, 'spec_bytes', spec_path.stat().st_size)


if __name__ == '__main__':
    main()
