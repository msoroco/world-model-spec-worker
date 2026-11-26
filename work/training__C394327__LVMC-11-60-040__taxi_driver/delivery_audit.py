"""Independent source and pixel audit for a taxi stop request."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

VIEWS = {'overview': (1920, 1080), 'approach': (1280, 720),
         'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}
REVIEWS = ('taxi-license-review.json', 'stand-designation-review.json',
           'participant-activity-review.json', 'other-regulations-review.json')


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode(path, dimensions):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                            '-count_frames', '-show_entries',
                            'stream=width,height,nb_read_frames', '-of', 'json',
                            str(path)], text=True, capture_output=True, check=True)
    stream = json.loads(probe.stdout)['streams'][0]
    require((stream['width'], stream['height']) == dimensions and
            int(stream['nb_read_frames']) == 600,
            'Original taxi camera dimensions or duration differ')
    frames = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path),
                             '-f', 'framemd5', '-'], text=True, capture_output=True)
    require(frames.returncode == 0 and
            sum(bool(line) and not line.startswith('#')
                for line in frames.stdout.splitlines()) == 600,
            'Original taxi camera pixel decode differs')
    return sha(path)


def audit(case, attempt, diagnostic=False, omit_source=None):
    root = Path(attempt).resolve()
    config = read(root / 'config.json')
    require(config.get('selected_case_id') == case and
            config.get('actor') == 'taxi_driver' and
            config.get('cell_id') == 'C394327' and
            config.get('law_id') == 'LVMC-11-60-040' and
            config.get('rate_hz') == 20 and config.get('duration_s') == 30,
            'Wrong exact taxi capture identity or duration')
    require(read(root / 'construction.json')['case_id'] == case,
            'Original taxi construction identity differs')
    sources = ('trace.jsonl', 'video_frames.jsonl',
               'observed-activity.jsonl', *REVIEWS)
    for source in sources:
        require(source != omit_source and (root / source).is_file(),
                'Missing source: ' + source)
    trace, mapping, activity = (rows(root / name) for name in sources[:3])
    require(len(trace) == len(mapping) == len(activity) == 600,
            'Original taxi trace, frame map or activity is incomplete')
    require(all(t['frame'] == m['carla_frame'] == a['native_frame'] and
                m['video_frame'] == a['video_frame'] == i and
                abs(t['time_s'] - m['time_s']) < 1e-4 and
                abs(t['time_s'] - a['time_s']) < 1e-4
                for i, (t, m, a) in enumerate(zip(trace, mapping, activity))),
            'Original taxi participant/frame/time join differs')
    require(all(abs(a['observed_speed_mps']) <= 0.1 for a in activity) and
            any(a['observed_activity'] != 'no_activity' for a in activity),
            'Original taxi stationary activity episode not completed')
    reviews = {name: read(root / name) for name in REVIEWS}
    require(all(item.get('source_basis') for item in reviews.values()),
            'Taxi authority or activity review lacks source basis')
    if not diagnostic:
        provenance = read(root / 'acquisition-provenance.json')
        require(provenance.get('provenance_kind') == 'native' and
                provenance.get('diagnostic_fixture') is False,
                'Synthetic taxi fixture cannot establish original Native delivery')
        independent = read(root / 'independent-taxi-review.json')
        require(independent.get('reviewer') and
                independent.get('taxi_identity_reviewed') is True and
                independent.get('stand_designation_reviewed') is True and
                independent.get('other_regulations_reviewed') is True and
                independent.get('participant_activity_reviewed') is True and
                independent.get('pixels_reviewed') is True and
                independent.get('frame_count') == 600,
                'Independent original taxi source and pixel review missing')
        require(all(sha(root / name) == value
                    for name, value in independent.get('source_hashes', {}).items()),
                'Independent taxi review source hashes differ')
    media = {name + '.mkv': decode(root / (name + '.mkv'), dimensions)
             for name, dimensions in VIEWS.items()}
    return {'format': 'worker-taxi-delivery-audit', 'case_id': case,
            'diagnostic': diagnostic, 'passed': True, 'frames': 600,
            'original_native_accepted': not diagnostic,
            'legal_verdict_claimed': False,
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'source_hashes': {name: sha(root / name) for name in sources} | media}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--omit-source')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.diagnostic,
                           args.omit_source), allow_nan=False))
