"""Independent saved source and full-decode audit for C125763 camera views."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from crossing_timing import measure
from encode_views import _probe
from native_history_capture import CAMERAS, audit_media


PROBES = ('entry_below', 'entry_inside', 'entry_above')


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def audit(attempt, saved_result, videos_dir, encode_receipt, *, probe_id):
    if probe_id not in PROBES:
        raise ValueError('unknown exact timing case')
    attempt, saved_result, videos_dir = map(Path, (attempt, saved_result, videos_dir))
    result = json.loads(saved_result.read_text(encoding='utf-8'))
    receipt = (json.loads(Path(encode_receipt).read_text(encoding='utf-8'))
               if not isinstance(encode_receipt, dict) else encode_receipt)
    if (result.get('probe_id') != probe_id or
            result.get('assignment_id') != 'testing__C125763__NRS-484B-250-2__motor_vehicle_driver'):
        raise ValueError('saved result belongs to another exact case')
    if result.get('source_manifest_sha256') != _sha(attempt / 'source-manifest.json'):
        raise ValueError('saved source manifest differs')
    timing = measure(attempt)
    if result.get('timing') != timing:
        raise ValueError('saved entry timing differs from original')
    site = json.loads((attempt / 'site-context.json').read_text(encoding='utf-8'))
    dimensions = site.get('camera_dimensions')
    if not isinstance(dimensions, dict) or set(dimensions) != set(CAMERAS):
        raise ValueError('four original camera dimensions missing')
    media = audit_media(attempt, camera_dimensions=dimensions)
    if (result.get('camera_audit') != media or
            result.get('camera_coverage_verified') is not True or
            result.get('original_frame_count') != media['joined_original_frames']):
        raise ValueError('saved camera source audit differs')
    count = media['joined_original_frames']
    if (receipt.get('source_frame_count') != count or receipt.get('fps') != 20 or
            receipt.get('encoding') != 'ffv1' or
            not isinstance(receipt.get('videos'), dict) or
            set(receipt['videos']) != set(CAMERAS)):
        raise ValueError('four-view encoded receipt differs')
    decoded = 0
    for name in CAMERAS:
        row = receipt['videos'][name]
        if (row.get('path') != name + '.mkv' or
                row.get('decoded_frames') != count or
                row.get('dimensions') != dimensions[name]):
            raise ValueError('encoded camera identity/profile differs: ' + name)
        path = videos_dir / (name + '.mkv')
        if path.is_symlink() or _sha(path) != row.get('sha256'):
            raise ValueError('encoded camera bytes differ: ' + name)
        stream = _probe(path)
        if (stream.get('codec_name') != 'ffv1' or
                [stream.get('width'), stream.get('height')] != dimensions[name] or
                stream.get('avg_frame_rate') != '20/1' or
                int(stream.get('nb_read_frames', -1)) != count):
            raise ValueError('encoded camera probe differs: ' + name)
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', str(path),
                        '-map', '0:v:0', '-f', 'null', '-'],
                       capture_output=True, text=True, check=True)
        decoded += count
    return {'format': 'c125763-independent-delivery-audit-v1',
            'probe_id': probe_id,
            'source_manifest_sha256': result['source_manifest_sha256'],
            'saved_result_sha256': _sha(saved_result),
            'decoded_view_frames': decoded,
            'original_body_frames': count,
            'full_video_decode': True,
            'diagnostic_fixture': result.get('diagnostic_fixture'),
            'actual_pixels_verified': False,
            'physical_acceptance': False,
            'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--saved-result', type=Path, required=True)
    parser.add_argument('--videos-dir', type=Path, required=True)
    parser.add_argument('--encode-receipt', type=Path, required=True)
    parser.add_argument('--probe', choices=PROBES, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.attempt, args.saved_result, args.videos_dir,
                   args.encode_receipt, probe_id=args.probe)
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
