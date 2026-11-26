"""Independent original lamp source, video and physical delivery audit."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from saved_audit import audit_saved
from source_packet import ASSIGNMENT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def audit(attempt, processing, case_id, *, diagnostic=False):
    if not case_id.startswith(ASSIGNMENT + '__'):
        raise ValueError('wrong lamp assignment identity')
    key = case_id.removeprefix(ASSIGNMENT + '__')
    attempt = Path(attempt).resolve()
    if not (attempt / 'lamp-context-packet.json').is_file():
        raise ValueError('original lamp context packet missing')
    saved = audit_saved(attempt, key)
    receipt = read(processing)
    if (receipt.get('format') != 'worker-saved-processing' or receipt.get('passed') is not True or
            receipt.get('recorded_only') is not True or receipt.get('case_id') != case_id or
            receipt.get('originals_preserved') is not True or
            receipt.get('timestamp_joins', {}).get('passed') is not True):
        raise ValueError('saved-only source/time processing incomplete')
    for name in ('lamp-context-packet.json', 'original-lamp-ticks.jsonl',
                 'camera-source-manifest.json', 'native-owner-release.json'):
        if receipt.get('original_source_hashes', {}).get(name) != sha(attempt / name):
            raise ValueError('saved processing original source binding changed: ' + name)
    result_path = Path(receipt.get('result', ''))
    if not result_path.is_file() or receipt.get('result_sha256') != sha(result_path):
        raise ValueError('saved result missing or changed')
    result = read(result_path)
    if result.get('case_id') != case_id or result.get('physical_acceptance_claimed') is not False:
        raise ValueError('saved physical result identity or provenance changed')
    video = Path(receipt.get('analysis_directory', '')) / 'event_review.webm'
    decode = receipt.get('final_video_checks', {})
    if (not video.is_file() or decode.get('passed') is not True or
            decode.get('frames') != saved['frame_count'] or decode.get('video_sha256') != sha(video)):
        raise ValueError('full four-view video decode missing or stale')
    if not diagnostic:
        seal = read(attempt / 'capture-seal.json')
        native_exit = read(attempt / 'native-exit.json')
        owner = read(attempt / 'owner-release.json')
        provenance = read(attempt / 'acquisition-provenance.json')
        if (seal.get('events') != ['capture_finished', 'encoders_closed', 'restoration_verified'] or
                native_exit.get('capture_seal_sha256') != sha(attempt / 'capture-seal.json') or
                owner.get('operator_attested') is not True or
                owner.get('native_exit_sha256') != sha(attempt / 'native-exit.json') or
                provenance.get('provenance_kind') != 'native' or
                provenance.get('diagnostic_fixture') is not False):
            raise ValueError('original Native capture lifecycle incomplete')
        for name, digest in seal.get('sources', {}).items():
            path = attempt / name
            if not path.is_file() or sha(path) != digest:
                raise ValueError('sealed original missing or changed: ' + name)
        pixel = read(attempt / 'pixel-review.json')
        if (not pixel.get('reviewer') or pixel.get('video_sha256') != sha(video) or
                not all(pixel.get(name) is True for name in
                        ('official_device_visible', 'lamp_state_visible', 'ego_route_visible',
                         'lighting_context_visible'))):
            raise ValueError('independent actual-pixel lamp review missing or stale')
        if not all(result.get(name) is True for name in
                   ('setup_confirmed', 'behavior_attempted', 'maneuver_completed')):
            raise ValueError('physical completion missing in original Native result')
    return {'format': 'lamp-delivery-audit', 'case_id': case_id,
            'diagnostic_fixture_checked': diagnostic, 'passed': not diagnostic,
            'original_frames': saved['frame_count'], 'camera_count': saved['camera_count'],
            'video_sha256': sha(video), 'result_sha256': sha(result_path),
            'physical_acceptance_claimed': not diagnostic, 'legal_judgment': None}


def main():
    parser = argparse.ArgumentParser()
    for name in ('case', 'attempt', 'processing'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--negative-missing-packet', action='store_true')
    args = parser.parse_args()
    if args.negative_missing_packet:
        with tempfile.TemporaryDirectory(prefix='lamp-negative-', dir=Path('.runtime-work/c230294-owner-nov26')) as temporary:
            clone = Path(temporary)
            for child in Path(args.attempt).iterdir():
                if child.name != 'lamp-context-packet.json':
                    (clone / child.name).symlink_to(child.resolve(), target_is_directory=child.is_dir())
            print(json.dumps(audit(clone, args.processing, args.case, diagnostic=args.diagnostic)))
    else:
        print(json.dumps(audit(args.attempt, args.processing, args.case, diagnostic=args.diagnostic)))


if __name__ == '__main__':
    main()
