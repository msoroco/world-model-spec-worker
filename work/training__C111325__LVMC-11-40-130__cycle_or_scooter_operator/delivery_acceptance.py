"""Independent exact-case source audit with diagnostic/physical separation."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing delivery source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(attempt, case_id, diagnostic):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text())
    if config.get('case_id') != case_id:
        raise ValueError('Wrong exact delivery case')
    if not diagnostic:
        required(root, 'capture-seal.json')
        required(root, 'native-capture-report.json')
    sources = ('native-bicycle-trace.jsonl', 'trace.jsonl', 'video_frames.jsonl',
               'capture/evidence.jsonl', 'context.json')
    evidence = {name: sha(required(root, name)) for name in sources}
    bicycle, trace, frames, capture = [rows(root / name) for name in sources[:4]]
    if any(len(stream) != 600 for stream in (bicycle, trace, frames, capture)):
        raise ValueError('Incomplete 600-frame delivery source')
    context = json.loads((root / 'context.json').read_text())
    if context.get('legal_prudence_verdict') is not None:
        raise ValueError('Legal prudence must remain unresolved')
    for index, (b, t, f, c) in enumerate(zip(bicycle, trace, frames, capture)):
        frame = b['native_frame']
        if (b['sample_index'] != index or t['frame'] != frame or
                f['native_frame'] != frame or c['original_frame'] != frame or
                abs(b['time_s'] - f['time_s']) > 1e-4 or
                any(f['camera_native_frames'][name] != frame for name in NAMES)):
            raise ValueError('Delivery source time join failed')
        if b['source_kind'] != context['source_kind'] or b['legal_verdict'] is not None:
            raise ValueError('Delivery source provenance or judgment changed')
    if diagnostic and context['source_kind'] != 'synthetic_native_mock':
        raise ValueError('Diagnostic source must identify synthetic provenance')
    if not diagnostic and context['source_kind'] != 'original_native_actor_readback':
        raise ValueError('Physical delivery requires original Native provenance')
    for name in NAMES:
        path = required(root, name + '.mkv')
        probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                '-count_frames', '-show_entries', 'stream=nb_read_frames',
                                '-of', 'default=nw=1:nk=1', str(path)],
                               capture_output=True, text=True, check=True)
        if int(probe.stdout.strip()) != 600:
            raise ValueError('Incomplete delivery video: ' + name)
        evidence[name + '.mkv'] = sha(path)
    return {'format': 'c111325-independent-delivery-audit-v1', 'case_id': case_id,
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'source_hashes': evidence, 'frames': 600, 'diagnostic_fixture': diagnostic,
            'original_native_observed': not diagnostic, 'display_pixels_reviewed': False,
            'bicycle_identity_reviewed': False, 'physical_acceptance': False,
            'legal_prudence_verdict': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.attempt, args.case, args.diagnostic)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': args.case, 'diagnostic_fixture': args.diagnostic,
                      'frames': result['frames'], 'physical_acceptance': False}))


if __name__ == '__main__':
    main()
