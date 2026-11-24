"""Source-shaped 30-second CPU proof with negative source-join tests."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile

from driving_cues import FRAMES, RATE, measure

ROOT = Path(__file__).resolve().parents[1]


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))


def fixture(path, erratic=False):
    path.mkdir(parents=True)
    motion, mapping, geometry = [], [], []
    for index in range(FRAMES):
        native = 70000 + index
        yaw = (4.0 if index % 20 < 10 else -4.0) if erratic else 0.0
        acceleration = -3.0 if erratic and 200 <= index < 240 else 0.0
        gap = 0.5 if erratic and 300 <= index < 340 else 3.0
        motion.append({'source_kind': 'synthetic_native_sample', 'native_frame': native,
                       'time_s': index / RATE, 'velocity_mps': [6.0, 0.0, 0.0],
                       'acceleration_mps2': [acceleration, 0.0, 0.0],
                       'yaw_deg': yaw, 'minimum_surface_gap_m': gap,
                       'contact': False, 'pedestrian_visible': index >= 450})
        geometry.append({
            'source_kind': 'synthetic_native_sample', 'native_frame': native,
            'time_s': index / RATE,
            'ego_footprint_xy_m': [[-1, -0.5], [1, -0.5], [1, 0.5], [-1, 0.5]],
            'participants': [{'actor_id': 2, 'type_id': 'vehicle.test',
                              'footprint_xy_m': [[1 + gap, -0.5], [3 + gap, -0.5],
                                                 [3 + gap, 0.5], [1 + gap, 0.5]],
                              'planar_gap_m': gap}],
            'minimum_surface_gap_m': gap,
            'gap_method': 'original_native_2d_body_footprint_separation'})
        mapping.append({'native_frame': native, 'video_frame': index, 'time_s': index / RATE})
    write_rows(path / 'native-ego-frames.jsonl', motion)
    write_rows(path / 'native-body-geometry.jsonl', geometry)
    (path / 'native-collision-events.jsonl').write_text('')
    write_rows(path / 'video_frames.jsonl', mapping)
    (path / 'driving-context.json').write_text(json.dumps({
        'source_kind': 'synthetic_native_sample', 'cell_id': 'C230222',
        'law_id': 'LVMC-11-22-020', 'actor': 'motor_vehicle_driver',
        'highway_in_city_evidence': None}, indent=2) + '\n')
    return motion, mapping


def rejects(path, name, action):
    with tempfile.TemporaryDirectory(dir=os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT')) as temp:
        source = Path(temp) / name
        motion, mapping = fixture(source)
        action(source, motion, mapping)
        try:
            measure(source)
        except ValueError as error:
            return {'case': name, 'rejected': True, 'error': str(error)}
        raise AssertionError(name + ' was accepted')


def main():
    with tempfile.TemporaryDirectory(dir=os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT')) as temp:
        controlled, erratic = Path(temp) / 'controlled', Path(temp) / 'erratic'
        fixture(controlled)
        fixture(erratic, True)
        a, b = measure(controlled), measure(erratic)
        assert a['sample_count'] == b['sample_count'] == 600
        assert a['legal_carelessness_or_imprudence'] is None
        assert b['legal_carelessness_or_imprudence'] is None
        assert max(abs(row['yaw_rate_degps'] or 0) for row in b['measurements']) > 0
        assert max(abs(row['yaw_rate_degps'] or 0) for row in a['measurements']) == 0
        assert min(row['minimum_surface_gap_m'] for row in b['measurements']) == 0.5
        assert min(row['minimum_surface_gap_m'] for row in a['measurements']) == 3.0
        positive = {
            label: {'source_sha256': item['source_sha256'], 'sample_count': item['sample_count'],
                    'max_abs_yaw_rate_degps': max(abs(row['yaw_rate_degps'] or 0) for row in item['measurements']),
                    'min_surface_gap_m': min(row['minimum_surface_gap_m'] for row in item['measurements']),
                    'min_longitudinal_acceleration_mps2': min(row['longitudinal_acceleration_mps2'] for row in item['measurements']),
                    'legal_verdict': item['legal_carelessness_or_imprudence']}
            for label, item in (('controlled_fixture', a), ('erratic_fixture', b))}
    negative = [
        rejects(Path('.'), 'missing_trace', lambda p, m, f: (p / 'native-ego-frames.jsonl').unlink()),
        rejects(Path('.'), 'short_trace', lambda p, m, f: write_rows(p / 'native-ego-frames.jsonl', m[:-1])),
        rejects(Path('.'), 'frame_mismatch', lambda p, m, f: (f[250].update(native_frame=90000), write_rows(p / 'video_frames.jsonl', f))),
        rejects(Path('.'), 'time_mismatch', lambda p, m, f: (m[250].update(time_s=99), write_rows(p / 'native-ego-frames.jsonl', m))),
        rejects(Path('.'), 'missing_gap', lambda p, m, f: (m[250].pop('minimum_surface_gap_m'), write_rows(p / 'native-ego-frames.jsonl', m))),
        rejects(Path('.'), 'missing_geometry', lambda p, m, f: (p / 'native-body-geometry.jsonl').unlink()),
        rejects(Path('.'), 'altered_geometry', lambda p, m, f: (m[250].update(minimum_surface_gap_m=1.0), write_rows(p / 'native-ego-frames.jsonl', m))),
        rejects(Path('.'), 'unbound_collision', lambda p, m, f: (m[250].update(contact=True), write_rows(p / 'native-ego-frames.jsonl', m))),
        rejects(Path('.'), 'bad_identity', lambda p, m, f: (p / 'driving-context.json').write_text(json.dumps({'source_kind':'synthetic_native_sample','cell_id':'wrong','law_id':'LVMC-11-22-020','actor':'motor_vehicle_driver','highway_in_city_evidence':None}))),
    ]
    proof = {'format': 'c230222-curbside-driving-cues-proof-v1',
             'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'meter_sha256': hashlib.sha256((ROOT / 'native/driving_cues.py').read_bytes()).hexdigest(),
             'positive': positive, 'negative': negative,
             'source_kind': 'synthetic_native_sample', 'physical_observation': False,
             'legal_verdict': None}
    destination = ROOT / 'native/driving-cues-proof.json'
    destination.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'proof': str(destination), 'negative_count': len(negative),
                      'proof_sha256': hashlib.sha256(destination.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
