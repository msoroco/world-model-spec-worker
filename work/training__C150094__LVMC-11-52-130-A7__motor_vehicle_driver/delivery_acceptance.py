"""Independent saved Native driveway source audit; no legal or physical verdict."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('native_parking_trace.jsonl', 'trace.jsonl', 'video_frames.jsonl',
           'driveway_context.json', 'capture/evidence.jsonl',
           'capture/native/frames.jsonl', 'road.xodr')


def need(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing delivery source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(root, case, diagnostic):
    root = Path(root).resolve()
    config = json.loads(need(root, 'config.json').read_text())
    if config.get('case_id') != case or config.get('selected_case_id') != case:
        raise ValueError('Wrong exact delivery case')
    if not diagnostic:
        need(root, 'capture-seal.json')
        need(root, 'native-capture-report.json')
    sources = {name: sha(need(root, name)) for name in SOURCES}
    parking, core, frames, evidence, native = (rows(root / name) for name in
        ('native_parking_trace.jsonl', 'trace.jsonl', 'video_frames.jsonl',
         'capture/evidence.jsonl', 'capture/native/frames.jsonl'))
    if any(len(stream) != 600 for stream in (parking, core, frames, evidence, native)):
        raise ValueError('Incomplete 600-frame delivery source')
    context = json.loads((root / 'driveway_context.json').read_text())
    if context.get('case_id') != case or context.get('assignment_id') != config.get('assignment_id'):
        raise ValueError('Driveway context identity differs')
    if context.get('review_kind') != ('synthetic_diagnostic' if diagnostic else 'original_source_review'):
        raise ValueError('Driveway context provenance differs')
    expected = 'synthetic_native_sample' if diagnostic else 'original_native_pose'
    for index, (park, state, frame, event, raw) in enumerate(zip(parking, core, frames, evidence, native)):
        original_frame = frame.get('native_frame')
        if (park.get('video_frame') != index or park.get('native_frame') != original_frame or
                park.get('source_kind') != expected or state.get('frame') != original_frame or
                event.get('original_frame') != original_frame or raw.get('frame') != original_frame or
                frame.get('video_frame') != index or
                any(frame.get('camera_native_frames', {}).get(name) != original_frame for name in CAMERAS) or
                abs(state.get('time_s', -100) - frame.get('time_s', 100)) > 1e-5 or
                abs(event.get('recording_time_s', -100) - frame.get('time_s', 100)) > 1e-5 or
                abs(raw.get('time_s', -100) - frame.get('time_s', 100)) > 1e-5 or
                abs(state.get('speed_mps', -100) - park.get('ego_speed_mps', 100)) > 1e-4):
            raise ValueError('Delivery source and camera time join failed')
    if context.get('camera_sha256') != {name + '.mkv': sha(need(root, name + '.mkv')) for name in CAMERAS}:
        raise ValueError('Driveway context camera source binding differs')
    for name in CAMERAS:
        path = need(root, name + '.mkv')
        proc = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                               '-count_frames', '-show_entries', 'stream=nb_read_frames',
                               '-of', 'default=nw=1:nk=1', str(path)],
                              capture_output=True, text=True, check=True)
        if proc.stdout.strip() != '600':
            raise ValueError('Incomplete delivery video: ' + name)
        sources[name + '.mkv'] = sha(path)
    return {'format': 'c150094-independent-delivery-audit-v1', 'case_id': case,
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'source_hashes': sources, 'frames': 600,
            'diagnostic_fixture': diagnostic, 'original_native_observed': not diagnostic,
            'display_pixels_reviewed': False, 'private_authority_reviewed': False,
            'physical_acceptance': False, 'legal_verdict': None}


def main():
    parser = argparse.ArgumentParser()
    for name in ('attempt', 'case', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    result = audit(args.attempt, args.case, args.diagnostic)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case_id': args.case, 'frames': 600,
                      'diagnostic_fixture': args.diagnostic, 'physical_acceptance': False}))


if __name__ == '__main__':
    main()
