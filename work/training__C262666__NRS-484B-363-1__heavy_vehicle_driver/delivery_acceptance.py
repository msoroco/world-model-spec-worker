"""Independent saved-source availability and time-join audit for school-zone delivery."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('native_motion.jsonl', 'trace.jsonl', 'video_frames.jsonl',
           'school_zone_context.json', 'capture/evidence.jsonl')


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
    sources = {name: sha(need(root, name)) for name in SOURCES}
    native, trace, frames, evidence = (rows(root / name) for name in
        ('native_motion.jsonl', 'trace.jsonl', 'video_frames.jsonl', 'capture/evidence.jsonl'))
    if any(len(stream) != 600 for stream in (native, trace, frames, evidence)):
        raise ValueError('Incomplete 600-frame delivery source')
    context = json.loads((root / 'school_zone_context.json').read_text())
    if context['case_id'] != case or context.get('legal_verdict') is not None:
        raise ValueError('School-zone context identity or unresolved judgment changed')
    expected = 'synthetic_native_sample' if diagnostic else 'original_native'
    for index, (motion, state, frame, event) in enumerate(zip(native, trace, frames, evidence)):
        n = motion['native_frame']
        if (motion['video_frame'] != index or motion['source_kind'] != expected or
                state['frame'] != n or frame['native_frame'] != n or
                event['original_frame'] != n or
                motion['ego_actor_id'] != context['ego_actor_id'] or
                any(frame['camera_native_frames'][name] != n for name in CAMERAS) or
                abs(state['time_s'] - frame['time_s']) > 1e-4):
            raise ValueError('Delivery source actor/camera time join failed')
    if context['review_kind'] != ('synthetic_diagnostic' if diagnostic else 'original_native'):
        raise ValueError('Delivery context provenance differs')
    for name in CAMERAS:
        path = need(root, name + '.mkv')
        run = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                              '-count_frames', '-show_entries', 'stream=nb_read_frames',
                              '-of', 'default=nw=1:nk=1', str(path)],
                             capture_output=True, text=True, check=True)
        if int(run.stdout.strip()) != 600:
            raise ValueError('Incomplete delivery video: ' + name)
        sources[name + '.mkv'] = sha(path)
    return {'format': 'c262666-independent-delivery-audit-v1', 'case_id': case,
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'source_hashes': sources, 'frames': 600,
            'diagnostic_fixture': diagnostic, 'original_native_observed': not diagnostic,
            'display_pixels_reviewed': False, 'school_authority_reviewed': False,
            'physical_acceptance': False, 'legal_verdict': None}


def main():
    parser = argparse.ArgumentParser()
    for name in ('attempt', 'case', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    result = audit(args.attempt, args.case, args.diagnostic)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': args.case, 'frames': 600,
                      'diagnostic_fixture': args.diagnostic, 'physical_acceptance': False}))


if __name__ == '__main__':
    main()
