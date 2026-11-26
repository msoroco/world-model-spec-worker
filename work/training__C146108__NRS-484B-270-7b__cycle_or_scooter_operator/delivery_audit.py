"""Independent complete-pass, source-join, and four-view delivery audit."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from native.pass_measure import measure

CAMERAS = {'overview': (1920, 1080), 'approach': (1280, 720),
           'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def video(path, dimensions):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-count_frames', '-show_entries', 'stream=width,height,nb_read_frames',
        '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    stream = json.loads(probe.stdout)['streams'][0]
    require((stream['width'], stream['height']) == dimensions and
            int(stream['nb_read_frames']) == 600, 'Four-view source dimensions or frames differ')
    decoded = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path),
        '-f', 'framemd5', '-'], capture_output=True, text=True)
    require(decoded.returncode == 0 and
            sum(bool(line) and not line.startswith('#') for line in decoded.stdout.splitlines()) == 600,
            'Full original camera pixel decode differs')
    return sha(path)


def audit(case, attempt, diagnostic):
    root = Path(attempt).resolve()
    config = read(root / 'config.json')
    require(config.get('case_id') == case and config.get('selected_case_id') == case
            and config.get('actor') == 'cycle_or_scooter_operator'
            and config.get('cell_id') == 'C146108' and config.get('law_id') == 'NRS-484B-270-7b',
            'Wrong exact cycle pass case')
    require(config.get('rate_hz') == 20 and config.get('duration_s') == 30,
            'Full original duration differs')
    require(read(root / 'construction.json')['case_id'] == case,
            'Original construction identity differs')
    provenance = read(root / 'acquisition-provenance.json')
    if not diagnostic:
        require(provenance.get('provenance_kind') == 'native' and
                provenance.get('diagnostic_fixture') is False,
                'Synthetic fixture cannot establish original Native delivery')
        review = read(root / 'independent-source-review.json')
        require(review.get('rider_class_reviewed') and review.get('motor_vehicle_reviewed') and
                review.get('occupants_reviewed') and review.get('four_view_pixels_reviewed') and
                review.get('frame_count') == 600 and review.get('reviewer'),
                'Independent original class, occupant and pixel review missing')
        require(all(sha(root / path) == digest for path, digest in review['source_hashes'].items()),
                'Independent source review hashes differ')
    pose, trace, frames, evidence = (rows(root / name) for name in
        ('participant-poses.jsonl', 'trace.jsonl', 'video_frames.jsonl',
         'capture/evidence.jsonl'))
    require(all(len(stream) == 600 for stream in (pose, trace, frames, evidence)),
            'Full original rider and motor history missing')
    rider, motor = pose[0]['rider_actor_id'], pose[0]['motor_actor_id']
    require(rider != motor and all(
        p['video_frame'] == i == m['video_frame'] and
        p['frame'] == p['native_frame'] == m['native_frame'] == m['carla_frame'] ==
        t['frame'] == e['original_frame'] and
        abs(p['time_s'] - m['time_s']) < 1e-4 and
        abs(p['time_s'] - t['time_s']) < 1e-4 and
        p['rider_actor_id'] == rider and p['motor_actor_id'] == motor and
        set(m['camera_native_frames']) == set(CAMERAS) and
        all(m['camera_native_frames'][name] == m['native_frame'] for name in CAMERAS)
        for i, (p, t, m, e) in enumerate(zip(pose, trace, frames, evidence))),
        'Original rider, motor, frame, time or camera join differs')
    measurement = measure(root)
    require(measurement['frames'] == 600 and
            measurement['first_behind_frame'] < measurement['pass_start_frame'] <
            measurement['pass_clear_frame'] and
            measurement['minimum_surface_gap_m'] > 0,
            'Full-body rider pass not physically completed in sampled evidence')
    media = {name: video(root / (name + '.mkv'), dimensions)
             for name, dimensions in CAMERAS.items()}
    return {'format': 'c146108-independent-delivery-audit-v1', 'case_id': case,
        'diagnostic': diagnostic, 'passed': True, 'frames': 600,
        'original_native_accepted': not diagnostic, 'legal_verdict_claimed': False,
        'checks': ['native_source', 'all_participants', 'time_join',
                   'full_video_decode', 'actual_pixels', 'physical_completion'],
        'pass_start_frame': measurement['pass_start_frame'],
        'pass_clear_frame': measurement['pass_clear_frame'],
        'minimum_surface_gap_m': measurement['minimum_surface_gap_m'],
        'source_hashes': {'participant-poses.jsonl': sha(root / 'participant-poses.jsonl'),
                          'pass-context.json': sha(root / 'pass-context.json'),
                          **{name + '.mkv': digest for name, digest in media.items()}}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.diagnostic), sort_keys=True))
