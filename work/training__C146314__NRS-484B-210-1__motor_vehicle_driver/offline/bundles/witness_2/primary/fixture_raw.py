"""Create labelled synthetic raw-shaped C146314 controls from saved fixtures."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def write_rows(path, values):
    Path(path).write_text(''.join(json.dumps(v, allow_nan=False) + '\n' for v in values))


def pose(actor_id, x, y, body, speed):
    return {'actor_id': actor_id, 'blueprint': 'vehicle.tesla.model3',
            'center_native_xyz_m': [x, y, 0], 'yaw_deg': 0,
            'velocity_native_xyz_mps': [speed, 0, 0], 'speed_mps': speed,
            'body_native_xyz_m': [[px, py, z] for z in (0, 1)
                                  for px, py in body]}


def build(bundle, output):
    bundle, output = Path(bundle), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    cfg = json.loads((bundle/'config.json').read_text())
    saved = bundle/'saved'
    observed = rows(saved/'native-observed.jsonl')
    requested = rows(bundle/'requested-tracks.jsonl')
    raw, video, review = [], [], []
    for i, (row, req) in enumerate(zip(observed, requested)):
        t, native = row['time_s'], 1000+i
        prior = observed[max(0, i-1)]
        ego_speed = 0 if i == 0 else 20*(row['ego_x_m']-prior['ego_x_m'])
        lead_speed = 0 if i == 0 else 20*(row['lead_x_m']-prior['lead_x_m'])
        obstruction = None
        if cfg['right_lane_obstruction_requested']:
            ox, oy = cfg['obstruction_x_m'], cfg['obstruction_y_m']
            r = cfg['obstruction_radius_m']
            obstruction = {'actor_id': 3, 'blueprint': 'static.prop.trafficcone',
                'center_native_xyz_m': [ox, oy, 0], 'yaw_deg': 0,
                'velocity_native_xyz_mps': [0, 0, 0], 'speed_mps': 0,
                'body_native_xyz_m': [[ox+dx, oy+dy, z] for z in (0, 1)
                    for dx, dy in ((-r,-r),(-r,r),(r,r),(r,-r))]}
        raw.append({'frame': i, 'native_frame': native, 'time_s': t,
            'source_kind': 'synthetic_cpu',
            'requested_ego_x_m': req['ego_x_m'],
            'requested_ego_y_m': req['ego_y_m'],
            'requested_lead_x_m': req['lead_x_m'],
            'observed_ego_road_id': 210,
            'observed_ego_lane_id': row['ego_lane_id'],
            'observed_lead_road_id': 210,
            'observed_lead_lane_id': row['lead_lane_id'],
            'ego': pose(1,row['ego_x_m'],row['ego_y_m'],row['ego_body_xy_m'],ego_speed),
            'lead': pose(2,row['lead_x_m'],row['lead_y_m'],row['lead_body_xy_m'],lead_speed),
            'obstruction': obstruction,
            'one_way_designation_verified': False,
            'pavement_condition_verified': False, 'legal_verdict': None})
        video.append({'video_frame': i, 'native_frame': native, 'time_s': t})
        review.append({'frame': i, 'native_frame': native, 'time_s': t,
            'source_kind': 'synthetic_cpu', 'review_provenance': 'synthetic_cpu',
            'forward_video_sha256': 'synthetic_cpu',
            'overview_video_sha256': 'synthetic_cpu',
            'object_pixel_reviewed': False, 'lane_pixel_reviewed': False})
    write(output/'native-map-readback.json', {'source_kind':'synthetic_cpu',
        'road_sha256': cfg['road_sha256'], 'native_map_sha256':'0'*64,
        'driving_lane_readback': {str(n): {'road_id':210,'lane_id':n}
                                  for n in (-1,-2)},
        'ego_actor_id':1,'lead_actor_id':2,
        'obstruction_actor_id':3 if cfg['right_lane_obstruction_requested'] else None,
        'one_way_designation_verified':False,
        'pavement_condition_verified':False,
        'obstruction_significance_verified':False,'legal_verdict':None})
    write_rows(output/'native-raw-actors.jsonl', raw)
    write_rows(output/'video_frames.jsonl', video)
    write_rows(output/'frame-review.jsonl', review)
    write(output/'native-capture-report.json', {'case_id':cfg['case_id'],
        'candidate_id':cfg['candidate_id'],
        'config_sha256':sha(bundle/'config.json'),
        'requested_frames':240,'observed_frames':240,'error':None,
        'accepted':False,'delivery_ready':False})
    return output


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args()
    print(build(a.bundle,a.output_dir))
