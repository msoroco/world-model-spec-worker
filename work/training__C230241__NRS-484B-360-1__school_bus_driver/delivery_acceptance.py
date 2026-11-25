"""Independent school-bus source audit; diagnostics assert no physical delivery."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')


def need(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing delivery source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(root, case, diagnostic):
    root = Path(root)
    config = json.loads(need(root, 'config.json').read_text())
    if config['case_id'] != case:
        raise ValueError('Wrong exact delivery case')
    if not diagnostic:
        need(root, 'capture-seal.json')
        need(root, 'native-capture-report.json')
    names = ('bus_motion.jsonl', 'passenger_trip_review.json', 'trace.jsonl',
             'video_frames.jsonl', 'capture/evidence.jsonl')
    evidence = {name: sha(need(root, name)) for name in names}
    motion, trace, frames, capture = (rows(root / name) for name in
                                      (names[0], names[2], names[3], names[4]))
    if any(len(stream) != 600 for stream in (motion, trace, frames, capture)):
        raise ValueError('Incomplete 600-frame delivery source')
    review = json.loads((root / 'passenger_trip_review.json').read_text())
    if review.get('review_kind') != ('synthetic_diagnostic' if diagnostic else 'original_video_review'):
        raise ValueError('Passenger review provenance differs')
    if review.get('assignment_id') != case.rsplit('__', 1)[0] or review.get('pupils_aboard') is not True:
        raise ValueError('Pupil-trip source absent or mismatched')
    if review.get('trip_purpose') != 'transporting pupils to or from school':
        raise ValueError('School trip purpose source absent')
    for index, (row, state, frame, event) in enumerate(zip(motion, trace, frames, capture)):
        native = row['native_frame']
        if (row['video_frame'] != index or state['frame'] != native or
                frame['native_frame'] != native or event['original_frame'] != native or
                any(frame['camera_native_frames'][name] != native for name in NAMES)):
            raise ValueError('Delivery bus motion and camera time join failed')
        if row['source_kind'] != ('synthetic_native_sample' if diagnostic else 'original_native_velocity'):
            raise ValueError('Delivery velocity provenance differs')
    for name in NAMES:
        path = need(root, name + '.mkv')
        run = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                              '-count_frames', '-show_entries', 'stream=nb_read_frames',
                              '-of', 'default=nw=1:nk=1', str(path)],
                             capture_output=True, text=True, check=True)
        if int(run.stdout.strip()) != 600:
            raise ValueError('Incomplete delivery video: ' + name)
        evidence[name + '.mkv'] = sha(path)
        if review['camera_sha256'][name] != evidence[name + '.mkv']:
            raise ValueError('Passenger review camera binding stale')
    return {'format': 'c230241-independent-delivery-audit-v1', 'case_id': case,
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'source_hashes': evidence, 'frames': 600,
            'diagnostic_fixture': diagnostic, 'original_native_observed': not diagnostic,
            'display_pixels_reviewed': False, 'school_bus_and_pupils_reviewed': False,
            'physical_acceptance': False, 'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('attempt', 'case', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    result = audit(args.attempt, args.case, args.diagnostic)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': args.case, 'frames': 600,
                      'diagnostic_fixture': args.diagnostic,
                      'physical_acceptance': False}))
