"""Independent exact-case signed-bicycle source and physical delivery audit."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
AID = HERE.name
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SIZES = {name: ((1920, 1080) if name == 'overview' else (1280, 720)) for name in VIEWS}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    require(root in path.parents and path.is_file(), 'Missing delivery source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def decode(path, size=None):
    run = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                          '-show_entries', 'stream=nb_read_frames,width,height,r_frame_rate',
                          '-of', 'json', str(path)], capture_output=True, text=True, timeout=180)
    require(run.returncode == 0, 'Full video decode failed')
    streams = json.loads(run.stdout).get('streams', [])
    require(len(streams) == 1, 'Full video stream inventory differs')
    meta = streams[0]
    require(meta.get('nb_read_frames') == '600' and meta.get('r_frame_rate') == '20/1',
            'Full video frame count or rate differs')
    if size:
        require((meta.get('width'), meta.get('height')) == tuple(map(str, size)),
                'Full video dimensions differ')
    pixel = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                            '-i', str(path), '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                           capture_output=True, timeout=180)
    require(pixel.returncode == 0 and len(pixel.stdout) == int(meta['width']) * int(meta['height']) * 3,
            'Actual decoded pixels absent')
    return {'frames': 600, 'rate_hz': 20, 'width': int(meta['width']),
            'height': int(meta['height']), 'sha256': sha(path),
            'first_frame_rgb_sha256': hashlib.sha256(pixel.stdout).hexdigest()}


def audit(root, case, diagnostic=False):
    suffix = case.rsplit('__', 1)[-1]
    require(case == AID + '__' + suffix and suffix in ('probe_01', 'probe_02'),
            'Wrong signed-roadway delivery case')
    names = ('video_frames.jsonl', 'bicycle-poses.jsonl', 'restriction-context.json',
             'trace.jsonl', 'road.xodr')
    paths = {name: source(root, name) for name in names}
    frames, poses, trace = (rows(paths[name]) for name in
                            ('video_frames.jsonl', 'bicycle-poses.jsonl', 'trace.jsonl'))
    context = json.loads(paths['restriction-context.json'].read_text())
    require(context.get('case_id') == case and context.get('blueprint_id') == 'vehicle.bh.crossbike',
            'Original bicycle source identity differs')
    require(context.get('target_surface') == ('shoulder' if suffix == 'probe_01' else 'roadway'),
            'Selected surface differs')
    require(len(frames) == len(poses) == len(trace) == 600,
            'Original pose/frame/trace join incomplete')
    actor_ids = {pose.get('rider_actor_id') for pose in poses}
    require(len(actor_ids) == 1 and type(next(iter(actor_ids))) is int,
            'Original cyclist actor identity missing')
    for index, (frame, pose, row) in enumerate(zip(frames, poses, trace)):
        require(frame.get('video_frame') == pose.get('video_frame') == index and
                frame.get('carla_frame') == pose.get('native_frame') == row.get('frame') and
                abs(frame['time_s'] - pose['time_s']) < 1e-6 and
                abs(frame['time_s'] - row['time_s']) < 1e-6 and
                set(frame.get('camera_native_frames', {})) == set(VIEWS) and
                all(frame['camera_native_frames'][view] == frame['carla_frame'] for view in VIEWS),
                'Original bicycle or camera timestamp join differs')
    require(frames[-1]['time_s'] - frames[0]['time_s'] >= 29.9,
            'Full 30-second original source period missing')
    if diagnostic:
        video = decode(source(root, 'diagnostic.mkv'))
        proof = json.loads((HERE / 'physical-proof' / suffix / 'complete_motion.json').read_text())
        require(proof['physical_checks']['maneuver']['status'] == 'met' and
                proof['diagnostic_fixture'] is True, 'Synthetic motion proof differs')
        return {'format': 'worker-signed-bicycle-source-audit-v1', 'case_id': case,
                'diagnostic_fixture': True, 'native_executed': False,
                'source_join_frames': 600, 'synthetic_pixel_decode': video,
                'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    videos = {view: decode(source(root, view + '.mkv'), SIZES[view]) for view in VIEWS}
    review_path = source(root, 'original-source-review.json')
    review = json.loads(review_path.read_text())
    require(all(review.get(field) is True for field in
                ('original_pixel_reviewed', 'sign_face_readable_reviewed',
                 'city_designation_source_reviewed', 'bicycle_wheel_subtype_reviewed',
                 'roadway_footprint_reviewed')),
            'Original authority, sign, subtype and occupancy review missing')
    require(review.get('camera_sha256') == {view + '.mkv': videos[view]['sha256'] for view in VIEWS}
            and review.get('source_sha256') == {name: sha(path) for name, path in paths.items()},
            'Original source review hashes differ')
    result = json.loads(source(root, 'result.json').read_text())
    require(result.get('case_id') == case and result.get('maneuver_completed') is True and
            result.get('physical_checks', {}).get('maneuver', {}).get('status') == 'met',
            'Original Native physical completion unverified')
    return {'format': 'worker-signed-bicycle-source-audit-v1', 'case_id': case,
            'passed': True, 'native_executed': True,
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'source_sha256': {name: sha(path) for name, path in paths.items()},
            'video_decode': videos, 'review_sha256': sha(review_path),
            'legal_verdict_claimed': False}


def selftest(case, negative):
    suffix = case.rsplit('__', 1)[-1]
    require(case == AID + '__' + suffix, 'Wrong exact selftest case')
    diagnostic = json.loads((HERE / 'cases' / suffix / 'diagnostic.json').read_text())
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c230207-audit-') as temporary:
        stage = Path(temporary)
        for name in ('video_frames.jsonl', 'bicycle-poses.jsonl', 'restriction-context.json',
                     'trace.jsonl', 'road.xodr'):
            (stage / name).write_text(diagnostic['files'][name])
        if negative:
            (stage / 'bicycle-poses.jsonl').unlink()
        else:
            subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                            '-f', 'lavfi', '-i', 'color=c=black:s=64x36:r=20',
                            '-frames:v', '600', '-an', '-c:v', 'ffv1', '-threads', '1',
                            str(stage / 'diagnostic.mkv')], check=True, timeout=180)
        return audit(stage, case, diagnostic=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt')
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--negative-selftest', action='store_true')
    args = parser.parse_args()
    result = selftest(args.case, args.negative_selftest) if (args.selftest or args.negative_selftest) else audit(args.attempt, args.case)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
