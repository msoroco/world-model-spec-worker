"""Join raw Native one-way capture with frame review and designation source."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from measure_saved import FILES, measure

REQUIRED = ('native-raw-ego.jsonl', 'native-map-readback.json', 'video_frames.jsonl')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def verify_video(path, count):
    try:
        result = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
            '-select_streams', 'v:0', '-show_entries',
            'stream=codec_name,nb_read_frames', '-of', 'json', str(path)],
            capture_output=True, text=True, check=True, timeout=180)
        streams = json.loads(result.stdout)['streams']
        if (len(streams) != 1 or streams[0].get('codec_name') != 'ffv1' or
                int(streams[0].get('nb_read_frames', 0)) != count):
            raise ValueError('Forward video codec or frame count differs')
    except (OSError, subprocess.CalledProcessError, KeyError, TypeError,
            json.JSONDecodeError) as error:
        raise ValueError('Forward FFV1 video could not be verified') from error


def prepare(raw_folder, review_path, designation_path, config_path, output):
    raw_folder, review_path, designation_path, config_path, output = map(Path,
        (raw_folder, review_path, designation_path, config_path, output))
    if output.exists():
        raise ValueError('Saved one-way destination must be fresh')
    config = json.loads(config_path.read_text())
    if (config.get('format') != 'c150916-native-request-v1' or
            config.get('status') != 'unselected_native_request' or
            config.get('requested_direction') not in ('designated', 'opposite')):
        raise ValueError('Exact one-way case configuration differs')
    paths = {name: raw_folder/name for name in REQUIRED}
    video = raw_folder/'forward.mkv' if (raw_folder/'forward.mkv').exists() else raw_folder/'forward-video-stub.txt'
    paths['forward_video'] = video
    if any(not path.is_file() for path in paths.values()) or not designation_path.is_file():
        raise ValueError('Raw, review or designation source absent')
    hashes = {name: sha(path) for name, path in paths.items()}
    review = json.loads(review_path.read_text())
    designation = json.loads(designation_path.read_text())
    if (review.get('format') != 'c150916-sign-frame-review-v1' or
            review.get('source_hashes') != hashes or
            not isinstance(review.get('rows'), list) or len(review['rows']) != 240 or
            designation.get('format') != 'c150916-designation-source-v1' or
            designation.get('designated_direction_x') != 1 or
            designation.get('road_sha256') != config.get('road_sha256')):
        raise ValueError('Sign review or designation source binding differs')
    map_info = json.loads(paths['native-map-readback.json'].read_text())
    if (map_info.get('road_sha256') != config.get('road_sha256') or
            map_info.get('driving_lane_ids') != {'-1': -1, '-2': -2} or
            map_info.get('authored_sign_request_ids') != [101, 102] or
            not isinstance(map_info.get('native_map_sha256'), str) or
            len(map_info['native_map_sha256']) != 64 or
            map_info.get('physical_sign_verified') is not False or
            map_info.get('designation_authority_verified') is not False):
        raise ValueError('Native one-way map readback differs')
    raw, frames = lines(paths['native-raw-ego.jsonl']), lines(paths['video_frames.jsonl'])
    if len(raw) != 240 or len(frames) != 240:
        raise ValueError('Raw one-way frame coverage differs')
    kind = raw[0].get('source_kind')
    if kind not in ('synthetic_cpu', 'original_native') or review.get('source_kind') != kind:
        raise ValueError('One-way source provenance differs')
    if kind == 'original_native':
        if (video.name != 'forward.mkv' or
                review.get('review_provenance') != 'human_frame_review' or
                designation.get('source_provenance') != 'government_record' or
                not designation.get('record_reference')):
            raise ValueError('Original sign review or government designation source absent')
        verify_video(video, 240)
    elif (review.get('review_provenance') != 'synthetic_cpu' or
          designation.get('source_provenance') != 'synthetic_cpu'):
        raise ValueError('Synthetic review provenance differs')
    first_frame = raw[0].get('native_frame')
    first_time = raw[0].get('time_s')
    if type(first_frame) is not int or not finite(first_time):
        raise ValueError('Initial Native frame/time differs')
    observed, sign_rows = [], []
    actor_id = None
    for i, (row, frame, sight) in enumerate(zip(raw, frames, review['rows'])):
        if (row.get('frame') != i or row.get('native_frame') != first_frame+i or
                row.get('source_kind') != kind or not finite(row.get('time_s')) or
                abs(row['time_s']-first_time-i/20) > 1e-4 or
                frame.get('video_frame') != i or frame.get('native_frame') != row['native_frame'] or
                not finite(frame.get('time_s')) or abs(frame['time_s']-row['time_s']) > 1e-4 or
                sight.get('frame') != i or sight.get('native_frame') != row['native_frame'] or
                sight.get('camera_frame') != row['native_frame'] or
                not finite(sight.get('time_s')) or abs(sight['time_s']-row['time_s']) > 1e-4 or
                not isinstance(sight.get('visible_sign_ids'), list) or
                any(type(value) is not int or value not in (101, 102)
                    for value in sight['visible_sign_ids']) or
                row.get('native_lane_id') not in (-2, -1)):
            raise ValueError('Raw ego, video, lane or sign frame join differs')
        ego = row.get('ego')
        if not isinstance(ego, dict) or ego.get('blueprint') != 'vehicle.tesla.model3':
            raise ValueError('Native ego blueprint differs')
        if actor_id is None:
            actor_id = ego.get('actor_id')
        if type(actor_id) is not int or ego.get('actor_id') != actor_id:
            raise ValueError('Native ego identity differs')
        center, velocity, body = (ego.get(name) for name in
                                  ('center_native_xyz_m','velocity_native_xyz_mps','body_native_xyz_m'))
        if (not isinstance(center, list) or len(center) != 3 or
                not isinstance(velocity, list) or len(velocity) != 3 or
                not all(finite(value) for value in center+velocity) or
                not isinstance(body, list) or len(body) < 4 or
                any(not isinstance(point, list) or len(point) != 3 or
                    not all(finite(value) for value in point) for point in body) or
                not finite(ego.get('yaw_deg')) or not finite(ego.get('speed_mps')) or
                abs(ego['speed_mps']-math.sqrt(sum(value*value for value in velocity))) > .1):
            raise ValueError('Native ego pose, body or velocity differs')
        saved = {'frame':i, 'time_s':(i+1)/20, 'native_frame':row['native_frame'],
                 'source_kind':kind, 'case':config['requested_direction'],
                 'ego_x_m':center[0], 'ego_y_m':-center[1],
                 'ego_speed_mps':ego['speed_mps'],
                 'ego_velocity_x_mps':velocity[0],
                 'ego_heading_deg':ego['yaw_deg']%360,
                 'lane_id':row['native_lane_id']}
        if kind == 'original_native':
            saved['ego_body_vertices_m'] = [[point[0], -point[1], point[2]] for point in body]
        observed.append(saved)
        sign_rows.append({'frame':i, 'time_s':(i+1)/20,
                          'native_frame':row['native_frame'],
                          'camera_frame':sight['camera_frame'],
                          'visible_sign_ids':sight['visible_sign_ids'],
                          'source_kind':kind})
    output.mkdir(parents=True)
    def write(name, data):
        (output/name).write_text(json.dumps(data, indent=2)+'\n')
    (output/'native-observed.jsonl').write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in observed))
    (output/'sign-frames.jsonl').write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in sign_rows))
    write('road-readback.json', {'source_kind':kind, 'driving_lane_ids':[-2,-1],
        'lane_direction_x':1,
        'sign_requests':{'101':{'type':'R6-1','direction_x':1},
                         '102':{'type':'R6-1','direction_x':1}},
        'raw_source_hashes':hashes, 'native_map_sha256':map_info['native_map_sha256'],
        'config_sha256':sha(config_path), 'sign_review_sha256':sha(review_path)})
    write('designation-record.json', {'source_kind':kind,
        'designated_direction_x':1,
        'status':'review_pending' if kind == 'original_native' else 'synthetic_unverified',
        'source_sha256':sha(designation_path),
        'record_reference':designation.get('record_reference')})
    measured = measure(output)
    receipt = {'format':'c150916-prepared-saved-one-way-v1',
        'case_id':config['case_id'], 'candidate_id':config['candidate_id'],
        'source_kind':kind, 'raw_source_hashes':hashes,
        'review_sha256':sha(review_path),
        'designation_source_sha256':sha(designation_path),
        'config_sha256':sha(config_path),
        'saved_hashes':{name:sha(output/name) for name in FILES},
        'measurement':measured, 'physical_sign_verified':False,
        'designation_authority_verified':False,
        'legal_verdict':None, 'delivery_ready':False}
    write('preparation-receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw-folder',type=Path,required=True)
    parser.add_argument('--review',type=Path,required=True)
    parser.add_argument('--designation',type=Path,required=True)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.raw_folder,args.review,args.designation,args.config,args.output),indent=2))
