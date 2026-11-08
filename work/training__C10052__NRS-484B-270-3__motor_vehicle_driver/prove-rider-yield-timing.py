"""Build six controlled, source-hashed rider conflict timing fixtures."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from measure_rider_yield import RIDERS, measure
from rider_engineering import CONFLICT_BOUNDS_M, check as route_check, ego_pose, rider_pose


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(rider_type, response):
    for i in range(480):
        rider=rider_pose(i)
        ego=ego_pose(i,response)
        yield {'native_frame': 1000+i, 'time_s': round(i*.05, 6),
               'rider_type': rider_type, 'rider_actor_id': 'rider-1',
               'rider_native_road_id': rider['road_id'],
               'rider_native_lane_id': rider['lane_id'],
               'ego_native_road_id': ego['road_id'],
               'rider_body_xy': rider['body_xy'],
               'ego_body_xy': ego['body_xy'],
               'rider_speed_mps': rider['speed_mps'],
               'ego_speed_mps': ego['speed_mps'],
               'ego_route_index': ego['route_index']}


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def main():
    route_check()
    scratch = ROOT / '.runtime-work/c10052-rider-yield-timing'
    scratch.mkdir(parents=True, exist_ok=True)
    geometry = {'source_kind': 'authored_native_geometry_proposal',
                'bicycle_facility_native_xy_bounds_m': [-60,-5,60,-3],
                'conflict_native_xy_bounds_m': list(CONFLICT_BOUNDS_M),
                'rider_road_id': 1, 'rider_lane_id': -2, 'ego_road_ids': [1,2],
                'native_readback_verified': False}
    geometry_path = scratch / 'geometry.json'
    write(geometry_path, geometry)
    receipts = []
    for rider_type in RIDERS:
        for response in ('clear','conflict'):
            folder = scratch / f'{rider_type}-{response}'
            folder.mkdir(exist_ok=True)
            samples = folder / 'native_rider_ego_samples.jsonl'
            samples.write_text(''.join(json.dumps(row,separators=(',',':'))+'\n'
                                       for row in rows(rider_type,response)))
            manifest = folder / 'rider-source-manifest.json'
            write(manifest, {'source_kind': 'synthetic_native_shaped_diagnostic',
                             'rider_type': rider_type, 'rider_actor_id': 'rider-1',
                             'samples_sha256': sha(samples), 'geometry_sha256': sha(geometry_path),
                             'accepted': False})
            result = measure(samples, geometry_path, manifest)
            assert result['ego_entered_after_rider_cleared'] is (response == 'clear')
            if response == 'clear':
                assert result['simultaneous_conflict_frames'] == 0
            else:
                assert result['simultaneous_conflict_frames'] > 0
            receipts.append({'case': f'{rider_type}-{response}', 'measurement': result,
                             'sources': {'samples': samples.relative_to(ROOT).as_posix(),
                                         'geometry': geometry_path.relative_to(ROOT).as_posix(),
                                         'manifest': manifest.relative_to(ROOT).as_posix()}})
            changed = folder / 'changed-source.jsonl'
            changed.write_bytes(samples.read_bytes().replace(b'"rider_actor_id":"rider-1"',
                                                       b'"rider_actor_id":"other"',1))
            try:
                measure(changed,geometry_path,manifest)
            except ValueError as exc:
                assert 'Changed original source bytes' in str(exc)
            else:
                raise AssertionError('Changed source accepted')
            changed.unlink()
    by_type = {typ: [r for r in receipts if r['case'].startswith(typ+'-')] for typ in RIDERS}
    for typ, pair in by_type.items():
        a,b=pair
        assert a['measurement']['first_rider_frame']==b['measurement']['first_rider_frame']
        assert a['measurement']['last_rider_frame']==b['measurement']['last_rider_frame']
        assert a['measurement']['first_ego_frame'] > b['measurement']['first_ego_frame']
    summary = {'format': 'c10052-rider-timing-prototype-v1', 'passed': True,
               'scope': 'six synthetic source-bound 480-frame timing diagnostics; no exact packages or Native actor proof',
               'geometry_sha256': sha(geometry_path), 'receipts': receipts,
               'changed_source_negatives': 6, 'selected': False, 'accepted': False}
    write(HERE / 'rider-timing-prototype.json', summary)
    print(json.dumps({'passed': True, 'pairs': 3,
                      'measurements': [(r['case'],r['measurement']['first_ego_frame'],
                                        r['measurement']['last_rider_frame'],
                                        r['measurement']['simultaneous_conflict_frames'])
                                       for r in receipts]}, indent=2))


if __name__ == '__main__':
    main()
