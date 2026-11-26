"""Independent source, motion, and four-view audit for one walking-surface case."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

CAMERAS = {'overview': (1920, 1080), 'approach': (1280, 720),
           'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def video(path, size):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-count_frames', '-show_entries', 'stream=width,height,nb_read_frames',
        '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    stream = json.loads(probe.stdout)['streams'][0]
    require((stream['width'], stream['height']) == size and
            int(stream['nb_read_frames']) == 600, 'Four-view source dimensions or frames differ')
    decoded = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path),
        '-f', 'framemd5', '-'], capture_output=True, text=True)
    require(decoded.returncode == 0, 'Original camera pixels could not decode')
    require(sum(line and not line.startswith('#') for line in decoded.stdout.splitlines()) == 600,
            'Full original camera pixel decode differs')
    return sha(path)


def audit(case, attempt, diagnostic):
    root = Path(attempt).resolve()
    config = read(root / 'config.json')
    require(config.get('case_id') == case and config.get('selected_case_id') == case
            and config.get('actor') == 'pedestrian' and config.get('cell_id') == 'C190631'
            and config.get('law_id') == 'LVMC-11-30-090', 'Wrong exact pedestrian case')
    require(config.get('rate_hz') == 20 and config.get('duration_s') == 30,
            'Full original duration differs')
    suffix = case.rsplit('__', 1)[-1]
    require(config.get('walking_surface') == {'probe_01': 'sidewalk',
            'probe_02': 'roadway'}.get(suffix), 'Wrong walking surface')
    require(read(root / 'construction.json')['case_id'] == case,
            'Original construction identity differs')
    geometry = read(root / 'surface-geometry.json')
    require(geometry.get('sidewalk_provided') is True and geometry.get('adjacent') is True
            and set(geometry.get('native_readback', {})) == {'roadway', 'sidewalk', 'lower_road'},
            'Provided adjacent sidewalk source missing')
    if not diagnostic:
        require((root / 'acquisition-provenance.json').is_file(),
                'Synthetic fixture cannot establish original Native delivery')
        source = read(root / 'acquisition-provenance.json')
        require(source.get('provenance_kind') == 'native' and
                source.get('diagnostic_fixture') is False and
                geometry.get('source_status') == 'original_native_map_readback',
                'Synthetic fixture cannot establish original Native delivery')
        review = read(root / 'independent-source-review.json')
        require(review.get('sidewalk_provision_reviewed') is True and
                review.get('adjacent_roadway_reviewed') is True and
                review.get('pedestrian_pixels_reviewed') is True and
                review.get('frame_count') == 600 and review.get('reviewer'),
                'Independent original sidewalk, roadway and pixel review missing')
        require(all(sha(root / p) == digest for p, digest in review['source_hashes'].items()),
                'Independent source review hashes differ')
        result = read(root / 'result.json')
        require(result.get('physical_checks', {}).get('maneuver', {}).get('status') == 'met',
                'Original pedestrian motion not completed')
    pose = rows(root / 'pedestrian-poses.jsonl')
    trace = rows(root / 'trace.jsonl')
    frames = rows(root / 'video_frames.jsonl')
    evidence = rows(root / 'capture/evidence.jsonl')
    require(all(len(stream) == 600 for stream in (pose, trace, frames, evidence)),
            'Full original pedestrian history missing')
    actor = pose[0]['walker_actor_id']
    require(all(p['video_frame'] == i == m['video_frame'] and
                p['native_frame'] == m['native_frame'] == m['carla_frame'] ==
                t['frame'] == e['original_frame'] and
                abs(p['time_s'] - m['time_s']) < 1e-4 and
                abs(p['time_s'] - t['time_s']) < 1e-4 and
                p['walker_actor_id'] == actor == e['actor_id'] and
                set(m['camera_native_frames']) == set(CAMERAS) and
                all(m['camera_native_frames'][name] == m['native_frame'] for name in CAMERAS)
                for i, (p, m, t, e) in enumerate(zip(pose, frames, trace, evidence))),
            'Original participant, frame, time or camera join differs')
    from native.measure import measure
    observed = measure(root / 'pedestrian-poses.jsonl', root / 'surface-geometry.json')
    surface = config['walking_surface']
    require(observed[surface + '_occupied_frames'] == 600 and
            observed[('roadway' if surface == 'sidewalk' else 'sidewalk') + '_occupied_frames'] == 0,
            'Pedestrian surface occupancy differs')
    media = {name: video(root / (name + '.mkv'), dimensions)
             for name, dimensions in CAMERAS.items()}
    return {'format': 'worker-walking-surface-delivery-audit', 'case_id': case,
            'diagnostic': diagnostic, 'passed': True, 'frames': 600,
            'original_native_accepted': not diagnostic, 'legal_verdict_claimed': False,
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'source_hashes': {'pedestrian-poses.jsonl': sha(root / 'pedestrian-poses.jsonl'),
                              'surface-geometry.json': sha(root / 'surface-geometry.json'),
                              **{name + '.mkv': digest for name, digest in media.items()}}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.diagnostic)))
