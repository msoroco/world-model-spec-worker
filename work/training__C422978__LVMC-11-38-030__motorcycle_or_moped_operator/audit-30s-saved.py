"""Independently recompute six 600-frame synthetic saved motorcycle sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c422978-30s-saved'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit_one(case, candidate, receipt):
    folder = SCRATCH / (case + '-' + candidate)
    construction = (HERE / 'extended-primary' / case /
                    ('construction.json' if candidate == 'primary' else candidate + '/construction.json'))
    if sha(construction) != receipt['construction_sha256']:
        raise ValueError('Construction source changed')
    for name, expected in receipt['source_hashes'].items():
        if sha(folder / name) != expected:
            raise ValueError('Saved source changed: ' + name)
    if sha(folder / 'city-context.json') != receipt['context_sha256']:
        raise ValueError('City context changed')
    context = json.loads((folder / 'city-context.json').read_text())
    if (context['city_authority_reviewed'] is not False or
            context['map_readback_sha256'] != sha(folder / 'native-map-readback.json') or
            context['driveway_crossing_polygons'] != []):
        raise ValueError('City context binding or review status differs')
    observed = rows(folder / 'native-observed.jsonl')
    mapping = rows(folder / 'video_frames.jsonl')
    evidence = rows(folder / 'capture/evidence.jsonl')
    requested = rows(ROOT / '.runtime-work/c422978-30s-v4' /
                     (case + '-' + candidate) / 'requested-tracks.jsonl')
    if len(observed) != len(mapping) or len(mapping) != len(evidence) or len(evidence) != len(requested) or len(requested) != 600:
        raise ValueError('Six hundred synchronized source rows absent')
    overlap = 0
    for index, (row, frame, capture, request) in enumerate(zip(observed, mapping, evidence, requested)):
        if (row['frame'] != frame['video_frame'] or row['frame'] != request['frame'] or
                row['frame'] != index or row['native_frame'] != frame['native_frame'] or
                row['native_frame'] != capture['original_frame'] or
                abs(row['time_s'] - index / 20) > 1e-5 or
                row['source_kind'] != 'synthetic_cpu' or
                row['motorcycle_blueprint'] != 'vehicle.kawasaki.ninja' or
                row['speed_mps'] != request['requested_speed_mps'] or
                row['center_native_xy_m'][0] != request['requested_center_xy_m'][0] or
                row['center_native_xy_m'][1] != -request['requested_center_xy_m'][1]):
            raise ValueError('Saved motorcycle/frame/request join differs')
        ys = [point[1] for point in row['body_native_xy_m']]
        overlap += min(ys) < 5.5 and max(ys) > 3.5
    expected = 0 if case == 'witness_1' else (535 if candidate == 'fallback1' else 520)
    if overlap != receipt['moving_overlap_frames'] or overlap != expected:
        raise ValueError('Saved sidewalk occupancy differs')
    return observed, folder, overlap


def main():
    proof = json.loads((HERE / 'extended-primary/saved-proof.json').read_text())
    if proof['selected'] or not proof['synthetic_only'] or len(proof['results']) != 6:
        raise ValueError('Saved proof scope differs')
    result = {}
    for candidate in ('primary', 'fallback1', 'fallback3'):
        pair = []
        for case in ('witness_1', 'witness_2'):
            receipt = next(item for item in proof['results'] if
                           item['case_id'].endswith('__' + case) and item['candidate_id'] == candidate)
            pair.append(audit_one(case, candidate, receipt))
        (left, left_folder, left_overlap), (right, right_folder, right_overlap) = pair
        for a, b in zip(left, right):
            for key in ('frame', 'native_frame', 'time_s', 'motorcycle_blueprint',
                        'speed_mps', 'native_road_id'):
                if a[key] != b[key]:
                    raise ValueError('Fixed comparison condition changed: ' + key)
            if a['center_native_xy_m'][0] != b['center_native_xy_m'][0]:
                raise ValueError('Paired longitudinal motion changed')
        for name in ('native-map-readback.json', 'video_frames.jsonl',
                     'capture/evidence.jsonl', 'city-context.json'):
            if sha(left_folder / name) != sha(right_folder / name):
                raise ValueError('Paired fixed source changed: ' + name)
        result[candidate] = [left_overlap, right_overlap]
    output = {'format': 'c422978-30s-saved-independent-audit-v1',
              'saved_proof_sha256': sha(HERE / 'extended-primary/saved-proof.json'),
              'cases_audited': 6, 'frames_per_case': 600,
              'overlap_frames_by_candidate': result,
              'fixed_conditions_checked': ['frame/time', 'motorcycle identity',
                                           'speed', 'Native road', 'longitudinal position',
                                           'city/sidewalk/driveway packet'],
              'original_native_observed': False, 'city_authority_reviewed': False}
    path = HERE / 'extended-primary/saved-audit.json'
    path.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'audit_sha256': sha(path), 'cases': 6, 'overlap': result}))


if __name__ == '__main__':
    main()
