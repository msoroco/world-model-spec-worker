"""Independent saved-source audit for the C111294 backup-lamp cases.

Diagnostic fixtures exercise the joins and media decoder. Native acceptance also
needs sealed originals, independent equipment authority and original pixel review.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from lamp_pixel_audit import CAMERAS, audit as audit_pixels


SOURCES = ('motion.jsonl', 'equipment.json', 'video_frames.jsonl',
           'other_vehicle.jsonl', 'intersection_context.json', 'trace.jsonl')


def digest(path):
    path = Path(path)
    if not path.is_file() or not path.stat().st_size:
        raise ValueError('Missing original source: ' + path.name)
    return sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def decode_camera(path, count):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams',
                            'v:0', '-show_entries', 'stream=nb_read_frames', '-of',
                            'json', str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout).get('streams', [])
    if len(streams) != 1 or int(streams[0].get('nb_read_frames', -1)) != count:
        raise ValueError('Original camera frame count differs: ' + path.name)
    decoded = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path),
                              '-f', 'null', '-'], capture_output=True, text=True)
    if decoded.returncode:
        raise ValueError('Original camera full decode failed: ' + path.name)
    return digest(path)


def audit(case_id, attempt, *, diagnostic_fixture=False):
    root = Path(attempt)
    config = read(root / 'config.json')
    report = read(root / 'analysis-report.json')
    result = read(root / 'result.json')
    if any(item.get('case_id') != case_id for item in (report, result)) or config.get('selected_case_id') != case_id:
        raise ValueError('Exact delivery case identity differs')
    if result.get('physical_acceptance_claimed') is not False or result.get('legal_acceptance_claimed') is not False:
        raise ValueError('Unsupported physical or legal acceptance claim')
    measurement = report['measurements']['backup_lamp_forward']
    if measurement['value'] != result['measured_values']['backup_lamp_forward']:
        raise ValueError('Saved result and analysis measurement differ')
    for name in SOURCES:
        if measurement['sources'].get(name) != digest(root / name):
            raise ValueError('Original source hash differs: ' + name)
    frames = rows(root / 'video_frames.jsonl')
    motion = rows(root / 'motion.jsonl')
    other = rows(root / 'other_vehicle.jsonl')
    trace = rows(root / 'trace.jsonl')
    if len(frames) < 2 or not (len(frames) == len(motion) == len(other) == len(trace)):
        raise ValueError('Original participant/time join is incomplete')
    for frame, body, participant, state in zip(frames, motion, other, trace):
        identity = (frame['carla_frame'], frame['time_s'])
        if ((body.get('frame'), body.get('time_s')) != identity or
                (participant.get('frame'), participant.get('time_s')) != identity or
                (state.get('frame'), state.get('time_s')) != identity):
            raise ValueError('Original participant/time join differs')
    camera_paths = {name: root / (name + '.mkv') for name in CAMERAS}
    camera_sha = {name: decode_camera(path, len(frames)) for name, path in camera_paths.items()}
    if diagnostic_fixture:
        if not (root / 'fixture-provenance.json').is_file() or (root / 'capture-seal.json').exists():
            raise ValueError('Diagnostic audit needs a marked unsealed fixture')
        scope = 'synthetic source and full-camera-decode audit only'
    else:
        if (root / 'fixture-provenance.json').exists():
            raise ValueError('Native audit rejects diagnostic fixture')
        seal = read(root / 'capture-seal.json')
        owner_exit = read(root / 'native-exit.json')
        if (owner_exit.get('event') != 'native_exit' or
                owner_exit.get('capture_seal_sha256') != digest(root / 'capture-seal.json') or
                seal.get('restoration', {}).get('restored') is not True):
            raise ValueError('Native capture closure or owner exit is unverified')
        if any(seal.get('sources', {}).get(name) != digest(root / name) for name in SOURCES):
            raise ValueError('Sealed original source hash differs')
        if len(frames) != config['frames']:
            raise ValueError('Native original duration is incomplete')
        equipment = read(root / 'equipment.json')
        if not equipment.get('inspection_reference') or not equipment.get('reviewer'):
            raise ValueError('Independent equipment inspection is missing')
        pixel = audit_pixels(measurement['value'], read(root / 'lamp-pixel-review.json'),
                             camera_paths, read(root / 'camera-full-decode-receipt.json'))
        if not pixel['pixel_review_complete']:
            raise ValueError('Original backup-lamp pixel review is incomplete')
        scope = 'sealed Native originals and independently reviewed lamp pixels'
    return {'format': 'worker-delivery-audit', 'case_id': case_id,
            'scope': scope, 'source_sha256': {name: digest(root / name) for name in SOURCES},
            'camera_sha256': camera_sha, 'frame_count': len(frames),
            'all_participants_checked': True, 'time_join_checked': True,
            'full_video_decode_checked': True, 'actual_pixels_reviewed': not diagnostic_fixture,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, diagnostic_fixture=args.diagnostic_fixture), indent=2))


if __name__ == '__main__':
    main()
