"""Independent saved-source and full-decode audit for 250(1) precedence views."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from saved_crossing import ASSIGNMENT, measure
from encode_views import _probe
from native_history_capture import CAMERAS, _retained_file, audit_media


PROBES = ('precedence', 'advance')


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def audit(attempt, saved_result, videos_dir, encode_receipt, *, probe_id,
          primary_path=None, composition_receipt=None):
    if probe_id not in PROBES:
        raise ValueError('unknown exact timing case')
    attempt, saved_result, videos_dir = map(Path, (attempt, saved_result, videos_dir))
    result = json.loads(saved_result.read_text(encoding='utf-8'))
    receipt = (json.loads(Path(encode_receipt).read_text(encoding='utf-8'))
               if not isinstance(encode_receipt, dict) else encode_receipt)
    if (result.get('case_id') != ASSIGNMENT + '__' + probe_id or
            result.get('assignment_id') != ASSIGNMENT or
            result.get('format') != 'worker-c125745-2501-saved-v1'):
        raise ValueError('saved result belongs to another exact case')
    if result.get('source_manifest_sha256') != _sha(_retained_file(attempt, 'source-manifest.json')):
        raise ValueError('saved source manifest differs')
    timing = measure(attempt)
    if result.get('crossing_measurement') != timing:
        raise ValueError('saved entry timing differs from original')
    if not timing['other_entered_before_ego']:
        raise ValueError('other vehicle did not enter before ego')
    intended_clearance = probe_id == 'precedence'
    if timing['other_cleared_before_ego_entry'] != intended_clearance:
        raise ValueError('original ego response did not realize requested clearance order')
    site = json.loads(_retained_file(attempt, 'site-context.json').read_text(
        encoding='utf-8'))
    dimensions = site.get('camera_dimensions')
    if not isinstance(dimensions, dict) or set(dimensions) != set(CAMERAS):
        raise ValueError('four original camera dimensions missing')
    media = audit_media(attempt, camera_dimensions=dimensions)
    if (result.get('camera_audit') != media or
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
    if (primary_path is None) != (composition_receipt is None):
        raise ValueError('primary and composition receipt required together')
    primary_audit = None
    if primary_path is not None:
        primary_path = Path(primary_path)
        composed = (json.loads(Path(composition_receipt).read_text(encoding='utf-8'))
                    if not isinstance(composition_receipt, dict) else composition_receipt)
        sources = {name: receipt['videos'][name]['sha256'] for name in CAMERAS}
        if (primary_path.is_symlink() or not primary_path.is_file() or
                composed.get('format') != 'synchronized-four-view' or
                composed.get('sources') != sources or
                composed.get('frame_map_sha256') != _sha(_retained_file(attempt, 'video_frames.jsonl')) or
                composed.get('primary_sha256') != _sha(primary_path) or
                composed.get('frames') != count or
                composed.get('dimensions') != [3840, 1800]):
            raise ValueError('composed primary source binding differs')
        stream = _probe(primary_path)
        if (stream.get('codec_name') != 'ffv1' or
                stream.get('avg_frame_rate') != '20/1' or
                int(stream.get('nb_read_frames', -1)) != count or
                [stream.get('width'), stream.get('height')] != [3840, 1800]):
            raise ValueError('composed primary decode/profile differs')
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i',
                        str(primary_path), '-map', '0:v:0', '-f', 'null', '-'],
                       capture_output=True, text=True, check=True)
        primary_audit = {'sha256': _sha(primary_path), 'decoded_frames': count,
                         'dimensions': [3840, 1800], 'full_decode': True}
    return {'format': 'c125745-2501-independent-delivery-audit-v1',
            'case_id': ASSIGNMENT + '__' + probe_id,
            'source_manifest_sha256': result['source_manifest_sha256'],
            'saved_result_sha256': _sha(saved_result),
            'decoded_view_frames': decoded,
            'composed_primary': primary_audit,
            'original_body_frames': count,
            'requested_clearance_order_observed': True,
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
    parser.add_argument('--case-id', required=True)
    parser.add_argument('--primary', type=Path)
    parser.add_argument('--composition-receipt', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.case_id != ASSIGNMENT + '__' + args.probe:
        raise ValueError('exact delivery audit case differs')
    result = audit(args.attempt, args.saved_result, args.videos_dir,
                   args.encode_receipt, probe_id=args.probe,
                   primary_path=args.primary,
                   composition_receipt=args.composition_receipt)
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
