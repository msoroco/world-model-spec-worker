"""Independent source and frame audit; fixture mode makes no physical claim."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('native_motion.jsonl', 'trace.jsonl', 'conditions.jsonl',
           'video_frames.jsonl', 'capture/evidence.jsonl', 'road_context.json')


def require_file(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing delivery source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(attempt, case, diagnostic):
    root = Path(attempt)
    config = json.loads(require_file(root, 'config.json').read_text())
    context = json.loads(require_file(root, 'road_context.json').read_text())
    if config['case_id'] != case or context['case_id'] != case:
        raise ValueError('Wrong exact delivery case')
    if not diagnostic:
        require_file(root, 'capture-seal.json')
        require_file(root, 'native-capture-report.json')
    expected_source = 'synthetic_native_sample' if diagnostic else 'original_native_velocity'
    expected_review = 'synthetic_diagnostic' if diagnostic else 'original_source_review'
    if context['review_kind'] != expected_review:
        raise ValueError('Delivery source provenance differs')
    native, trace, conditions, frames, evidence = [rows(require_file(root, name)) for name in SOURCES[:5]]
    if any(len(stream) != config['frames'] for stream in (native, trace, conditions, frames, evidence)):
        raise ValueError('Incomplete delivery source frames')
    for index, (motion, state, condition, frame, event) in enumerate(zip(native, trace, conditions, frames, evidence)):
        frame_id = motion['native_frame']
        if (motion['source_kind'] != expected_source or motion['video_frame'] != index
                or state['frame'] != frame_id or condition['native_frame'] != frame_id
                or frame['native_frame'] != frame_id or event['original_frame'] != frame_id
                or motion['ego_actor_id'] != context['ego_actor_id']
                or motion['other_actor_id'] != context['other_actor_id']
                or not any(actor.get('actor_id') == context['other_actor_id'] for actor in event['other_actors'])
                or not condition['traffic'] or not condition['road'] or not condition['weather']
                or any(frame['camera_native_frames'][name] != frame_id for name in CAMERAS)
                or any(condition['camera_frames'][name] != frame_id for name in CAMERAS)
                or abs(state['time_s'] - frame['time_s']) > 1e-4):
            raise ValueError('Delivery source participant/condition/camera time join failed')
    hashes = {name: digest(require_file(root, name)) for name in SOURCES}
    for name in CAMERAS:
        video = require_file(root, name + '.mkv')
        result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                 '-count_frames', '-show_entries', 'stream=nb_read_frames',
                                 '-of', 'default=nw=1:nk=1', str(video)],
                                capture_output=True, text=True, check=True)
        if int(result.stdout.strip()) != config['frames']:
            raise ValueError('Incomplete delivery video: ' + name)
        hashes[name + '.mkv'] = digest(video)
    return {'format': 'c230259-independent-delivery-audit-v1', 'case_id': case,
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'], 'frames': config['frames'],
            'source_hashes': hashes, 'diagnostic_fixture': diagnostic,
            'actual_pixels_reviewed': False, 'physical_acceptance': False,
            'legal_verdict': None}


def main():
    parser = argparse.ArgumentParser()
    for name in ('attempt', 'case', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    result = audit(args.attempt, args.case, args.diagnostic)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': args.case, 'frames': result['frames'],
                      'diagnostic_fixture': args.diagnostic, 'physical_acceptance': False}))


if __name__ == '__main__':
    main()
