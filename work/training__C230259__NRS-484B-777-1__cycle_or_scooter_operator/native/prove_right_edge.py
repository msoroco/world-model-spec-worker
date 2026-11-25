"""Thirty-second source-shaped CPU proof for cyclist right-edge measurement."""
import hashlib
import json
from pathlib import Path
import tempfile

from measure_right_edge import SOURCES, digest, measure

HERE = Path(__file__).resolve().parent
OWNER = HERE.parent
ROOT = OWNER.parents[1]
AID = OWNER.name
OUT = OWNER / 'right-edge-measurement-proof.json'


def write(path, data):
    path.write_text(json.dumps(data, sort_keys=True) + '\n')


def rows(path, data):
    path.write_text(''.join(json.dumps(item, sort_keys=True) + '\n' for item in data))


def hashes(folder):
    return {name: digest(folder / name) for name in SOURCES}


def sample(folder, suffix):
    folder.mkdir()
    write(folder / 'native-map-readback.json', {'format': 'c230259-road-edge-v1',
          'right_edge_source': 'synthetic_cpu', 'right_side': 'lower_y',
          'right_roadway_edge_y_m': -3.5, 'road_id': 1})
    write(folder / 'standing-vehicle.json', {'format': 'c230259-standing-vehicle-v1',
          'source_kind': 'synthetic_cpu', 'actor_id': 29,
          'body_native_xy_m': [[55, -5.2], [59, -5.2], [59, -3.7], [55, -3.7]]})
    track, video = [], []
    y = -2.8 if suffix == 'reference' else -1.75
    for i in range(600):
        x = round(10 + 3 * i / 20, 4)
        t = i / 20
        track.append({'frame': i, 'native_frame': i + 1000, 'time_s': t,
                      'actor_id': 17, 'blueprint': 'vehicle.bh.crossbike',
                      'body_native_xy_m': [[x-.9, y-.3], [x+.9, y-.3],
                                           [x+.9, y+.3], [x-.9, y+.3]],
                      'source_kind': 'synthetic_native_sample'})
        video.append({'video_frame': i, 'native_frame': i + 1000,
                      'carla_frame': i + 1000, 'time_s': t,
                      'source_rgb_sha256': {view: hashlib.sha256(
                          f'{view}:{i}'.encode()).hexdigest()
                          for view in ('overview', 'approach', 'reference_corner', 'driver_reference')}})
    rows(folder / 'native-cycle-frames.jsonl', track)
    rows(folder / 'video_frames.jsonl', video)


def reject(fn, label):
    try:
        fn()
    except ValueError:
        return label
    raise ValueError('Negative unexpectedly accepted: ' + label)


def main():
    assignment = json.loads((ROOT / 'inputs' / AID / 'assignment.json').read_text())
    plan = json.loads((OWNER / 'case-plan.json').read_text())
    if assignment['law']['text'] != plan['source_law_text'] or assignment['cell_id'] != 'C230259':
        raise ValueError('Frozen law or cell differs')
    scratch = ROOT / '.runtime-work'
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='c230259-edge-', dir=scratch) as temp:
        temp = Path(temp)
        measurements = {}
        for suffix in ('reference', 'contrast'):
            folder = temp / suffix
            sample(folder, suffix)
            measurements[suffix] = measure(folder, hashes(folder), diagnostic=True)
        reference = measurements['reference']
        contrast = measurements['contrast']
        if (reference['right_edge_body_margin_min_m'], contrast['right_edge_body_margin_min_m']) != (.4, 1.45):
            raise ValueError('Requested right-edge pair differs')
        if (reference['standing_vehicle_clearance_min_m'], contrast['standing_vehicle_clearance_min_m']) != (.6, 1.65):
            raise ValueError('Standing vehicle geometry differs')
        if reference['standing_vehicle_pass_frames'] != contrast['standing_vehicle_pass_frames']:
            raise ValueError('Passing time changed between pair')
        folder = temp / 'reference'
        original_hashes = hashes(folder)
        negatives = [reject(lambda: measure(folder, dict(original_hashes,
                          **{'native-cycle-frames.jsonl': '0'*64}), diagnostic=True),
                            'changed_source_hash')]
        negatives.append(reject(lambda: measure(folder, original_hashes),
                                'synthetic_as_native'))
        video_path = folder / 'video_frames.jsonl'
        video = [json.loads(line) for line in video_path.read_text().splitlines()]
        del video[5]['source_rgb_sha256']['driver_reference']
        rows(video_path, video)
        negatives.append(reject(lambda: measure(folder, hashes(folder), diagnostic=True),
                                'missing_camera'))
        track_path = folder / 'native-cycle-frames.jsonl'
        track = [json.loads(line) for line in track_path.read_text().splitlines()]
        track[5]['native_frame'] += 1
        rows(track_path, track)
        negatives.append(reject(lambda: measure(folder, hashes(folder), diagnostic=True),
                                'frame_join_changed'))
        track[-1]['blueprint'] = 'vehicle.harley-davidson.low_rider'
        rows(track_path, track)
        negatives.append(reject(lambda: measure(folder, hashes(folder), diagnostic=True),
                                'motorcycle_identity'))
        track.pop()
        rows(track_path, track)
        negatives.append(reject(lambda: measure(folder, hashes(folder), diagnostic=True),
                                'short_window'))
    result = {'format': 'c230259-right-edge-geometry-proof-v1',
              'assignment_sha256': digest(ROOT / 'inputs' / AID / 'assignment.json'),
              'case_plan_sha256': digest(OWNER / 'case-plan.json'),
              'measurement_source_sha256': digest(HERE / 'measure_right_edge.py'),
              'measurement_contract_sha256': digest(HERE / 'measurement-contract.json'),
              'cases': {suffix: {'right_edge_body_margin_min_m': row['right_edge_body_margin_min_m'],
                                 'standing_vehicle_clearance_min_m': row['standing_vehicle_clearance_min_m'],
                                 'pass_frames': len(row['standing_vehicle_pass_frames']),
                                 'source_hashes': row['source_hashes']}
                        for suffix, row in measurements.items()},
              'negative_rejections': negatives,
              'frames': 600, 'rate_hz': 20, 'synthetic_diagnostic': True,
              'practicability_reviewed': False, 'due_care_reviewed': False,
              'exception_status': 'unreviewed', 'original_native_observed': False,
              'legal_verdict': None, 'delivery_ready': False}
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'proof_sha256': digest(OUT), 'pass_frames': len(reference['standing_vehicle_pass_frames']),
                      'right_edge_margins': [reference['right_edge_body_margin_min_m'],
                                             contrast['right_edge_body_margin_min_m']],
                      'negative_rejections': negatives}))


if __name__ == '__main__':
    main()
