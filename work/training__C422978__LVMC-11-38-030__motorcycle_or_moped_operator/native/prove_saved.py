"""Synthetic local positives and decisive negatives for the saved occupancy meter."""
import copy
import json
from pathlib import Path

from measure_saved import measure, sha

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / 'saved-fixtures'


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(v, sort_keys=True) + '\n' for v in values))


def packet(case, candidate):
    path = HERE / 'drafts' / case / candidate / 'requested-tracks.jsonl'
    requested = [json.loads(line) for line in path.read_text().splitlines()]
    observed, mapping, evidence = [], [], []
    for row in requested:
        index = row['frame']
        x, y = row['requested_center_xy_m']
        y = -y
        native = 1000 + index
        observed.append({'frame': index, 'native_frame': native,
                         'time_s': row['time_s'], 'source_kind': 'synthetic_cpu',
                         'motorcycle_blueprint': 'vehicle.kawasaki.ninja',
                         'center_native_xy_m': [x, y],
                         'body_native_xy_m': [[round(x + dx, 4), round(y + dy, 4)]
                                              for dx, dy in ((-1.1,-.4),(-1.1,.4),(1.1,-.4),(1.1,.4))],
                         'speed_mps': row['requested_speed_mps'],
                         'native_road_id': 1,
                         'native_lane_id': -2 if y >= 3.5 else -1})
        mapping.append({'video_frame': index, 'native_frame': native,
                        'carla_frame': native, 'time_s': row['time_s']})
        evidence.append({'original_frame': native, 'recording_time_s': row['time_s']})
    return observed, mapping, evidence


def save(folder, observed, mapping, evidence):
    folder.mkdir(parents=True, exist_ok=True)
    write_rows(folder / 'native-observed.jsonl', observed)
    write_rows(folder / 'video_frames.jsonl', mapping)
    write_rows(folder / 'capture/evidence.jsonl', evidence)
    (folder / 'native-map-readback.json').write_text(json.dumps({
        'sidewalk_road_id': 1, 'sidewalk_lane_id': -2,
        'motorcycle_blueprint': 'vehicle.kawasaki.ninja',
        'city_location_verified': False, 'source_kind': 'synthetic_cpu'}, indent=2) + '\n')


def rejection(folder, expected):
    try:
        measure(folder)
    except ValueError as error:
        if str(error) != expected: raise
    else:
        raise ValueError('Saved source mutation accepted: ' + expected)


def prove():
    results = []
    for case in ('witness_1', 'witness_2'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            folder = FIXTURES / case / candidate
            observed, mapping, evidence = packet(case, candidate)
            save(folder, observed, mapping, evidence)
            result = measure(folder)
            if (result['frames'] != 480 or result['moving_frames'] != 480 or
                    bool(result['moving_sidewalk_overlap_frames']) != (case == 'witness_2') or
                    result['source_kind'] != 'synthetic_cpu' or result['legal_verdict'] is not None or
                    result['city_sidewalk_verified']):
                raise ValueError('Synthetic sidewalk comparison differs')
            (folder / 'analysis-report.json').write_text(json.dumps(result, indent=2) + '\n')
            results.append({'case_suffix': case, 'candidate_id': candidate,
                            'analysis_sha256': sha(folder / 'analysis-report.json'),
                            'source_hashes': result['source_hashes'],
                            'moving_sidewalk_overlap_frames': result['moving_sidewalk_overlap_frames']})
    original = packet('witness_2', 'primary')
    bad = FIXTURES / 'negative'
    variants = []
    for name, mutation, expected in (
            ('missing_actor', lambda o,m,e: None, 'Missing required source: native-observed.jsonl'),
            ('frame_join', lambda o,m,e: m[90].update(native_frame=2000),
             'Original Native/video/capture frame join differs'),
            ('body_center', lambda o,m,e: o[90]['body_native_xy_m'][0].__setitem__(1, -20),
             'Original motorcycle body/center differs'),
            ('identity', lambda o,m,e: o[90].update(motorcycle_blueprint='vehicle.tesla.model3'),
             'Original motorcycle identity differs')):
        observed, mapping, evidence = copy.deepcopy(original)
        folder = bad / name
        save(folder, observed, mapping, evidence)
        if name == 'missing_actor':
            (folder / 'native-observed.jsonl').unlink()
        else:
            mutation(observed, mapping, evidence)
            write_rows(folder / 'native-observed.jsonl', observed)
            write_rows(folder / 'video_frames.jsonl', mapping)
        rejection(folder, expected)
        variants.append({'name': name, 'expected_error': expected})
    output = {'format': 'c422978-synthetic-saved-proof-v1',
              'processor_sha256': sha(HERE / 'measure_saved.py'),
              'request_manifest_sha256': sha(HERE / 'drafts/manifest.json'),
              'positives': results, 'negatives': variants,
              'original_native_processed': False, 'legal_verdict': None}
    (HERE / 'saved-proof.json').write_text(json.dumps(output, indent=2) + '\n')
    return output


if __name__ == '__main__':
    print(json.dumps({'positives': len(prove()['positives'])}))
