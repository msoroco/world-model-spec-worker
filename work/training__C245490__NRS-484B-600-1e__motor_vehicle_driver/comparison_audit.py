"""Independent source-readback comparison for the three lane-change speed cases."""
import argparse
import hashlib
import json
import math
from pathlib import Path

AID = 'training__C245490__NRS-484B-600-1e__motor_vehicle_driver'
TARGETS = {'probe_01': 30.0, 'probe_02': 35.7632, 'probe_03': 36.5}
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FACTOR = 2.2369362921


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    if not path.is_file():
        raise ValueError('Missing original comparison source: '+path.name)
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(directories, configurations):
    if len(directories) != 3 or len(configurations) != 3:
        raise ValueError('Require all three exact speed cases')
    records = []
    for (probe, target), folder, config_path in zip(TARGETS.items(), directories, configurations):
        folder, config_path = Path(folder), Path(config_path)
        config = json.loads(config_path.read_text())
        case = AID+'__'+probe
        if (config.get('selected_case_id') != case or
                config.get('requested_speed_mps') != target or
                config.get('cell_id') != 'C245490' or
                config.get('actor') != 'motor_vehicle_driver'):
            raise ValueError('Exact comparison construction differs: '+probe)
        rows = read_rows(folder/'speed-lane-history.jsonl')
        frames = read_rows(folder/'video_frames.jsonl')
        if len(rows) != 600 or len(frames) != 600:
            raise ValueError('Incomplete original comparison history: '+probe)
        values = []
        for index, (row, frame) in enumerate(zip(rows, frames)):
            if (row['video_frame'] != index or frame['video_frame'] != index or
                    row['native_frame'] != frame['native_frame'] or
                    abs(row['time_s']-frame['time_s']) > .005 or
                    set(frame['camera_native_frames']) != set(CAMERAS) or
                    any(v != frame['native_frame'] for v in frame['camera_native_frames'].values())):
                raise ValueError('Original comparison frame/camera join differs: '+probe)
            velocity = row['velocity_xyz_mps']
            if len(velocity) != 3 or not all(type(v) in (int,float) and math.isfinite(v) for v in velocity):
                raise ValueError('Original comparison velocity missing: '+probe)
            values.append(math.sqrt(sum(v*v for v in velocity))*FACTOR)
        if rows[0]['lane_id'] != -1 or rows[-1]['lane_id'] != -2:
            raise ValueError('Lane-change source history incomplete: '+probe)
        road = folder/'road.xodr'
        if not road.is_file():
            raise ValueError('Missing fixed road source: '+probe)
        records.append({'case_id':case, 'requested_speed_mps':target,
                        'observed_minimum_mph':min(values),
                        'observed_maximum_mph':max(values),
                        'samples_above_80_mph':sum(v>80 for v in values),
                        'road_sha256':sha(road),
                        'original_speed_history_sha256':sha(folder/'speed-lane-history.jsonl'),
                        'original_frame_map_sha256':sha(folder/'video_frames.jsonl')})
    if len({r['road_sha256'] for r in records}) != 1:
        raise ValueError('Comparison fixed road differs')
    return {'format':'worker-lane-change-speed-comparison-audit',
            'assignment_id':AID, 'cases':records,
            'fixed_conditions':['cell','actor','same-direction two-lane road','lane-change maneuver',
                                '20 Hz / 30 s four-view source capture'],
            'deliberate_differences':['requested longitudinal speed'],
            'physical_acceptance_claimed':False,'legal_verdict_claimed':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-dirs',nargs=3,type=Path,required=True)
    parser.add_argument('--configs',nargs=3,type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.source_dirs,args.configs),indent=2)+'\n')
