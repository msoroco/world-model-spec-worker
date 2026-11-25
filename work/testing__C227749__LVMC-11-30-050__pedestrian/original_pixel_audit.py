"""Independent original-pixel review gate for a saved pedestrian crossing.

Diagnostic fixtures exercise the source joins but never pass physical delivery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from saved_media_audit import audit_media
from saved_measurement import read_attempt
from physical_geometry_audit import evaluate_crossing_completion
from reviewed_site import audit_reviewed_site

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def crop_bytes(video, frame_index, rectangle):
    x, y, width, height = rectangle
    command = ['ffmpeg', '-nostdin', '-v', 'error', '-i', str(video), '-vf',
               f'select=eq(n\\,{frame_index}),crop={width}:{height}:{x}:{y},format=rgb24',
               '-frames:v', '1', '-f', 'rawvideo', '-']
    completed = subprocess.run(command, capture_output=True, check=False)
    if completed.returncode or len(completed.stdout) != width * height * 3:
        raise ValueError('original pixel crop decode failed')
    return completed.stdout


def audit(attempt, review_path, case_id, *, diagnostic=False, media_auditor=audit_media,
          crop_decoder=crop_bytes):
    root = Path(attempt).resolve()
    review_path = Path(review_path).resolve()
    saved = read_attempt(root)
    media = media_auditor(root)
    packet = json.loads(review_path.read_text())
    if saved['case_id'] != case_id or packet.get('case_id') != case_id or packet.get('reviewer') in (None, ''):
        raise ValueError('independent pixel review identity missing')
    if packet.get('source_sha256') != saved['sources_sha256']:
        raise ValueError('independent pixel review source binding differs')
    expected = media['expected_frames']
    if media.get('case_id') != case_id or media.get('diagnostic_fixture') != saved['diagnostic_fixture']:
        raise ValueError('full-decode identity differs')
    if set(media.get('cameras', {})) != set(CAMERAS) or any(
            item.get('fully_decoded_frames') != expected for item in media['cameras'].values()):
        raise ValueError('four full original video decodes missing')
    observations = packet.get('observations')
    if not isinstance(observations, list) or len(observations) < len(CAMERAS):
        raise ValueError('independent camera observations missing')
    seen = set()
    visible = []
    for item in observations:
        name = item.get('camera')
        frame = item.get('frame_index')
        rectangle = item.get('crop_xywh')
        if name not in CAMERAS or type(frame) is not int or not 0 <= frame < expected:
            raise ValueError('reviewed camera or original frame differs')
        dimensions = media['cameras'][name]
        if (not isinstance(rectangle, list) or len(rectangle) != 4 or
                any(type(value) is not int for value in rectangle)):
            raise ValueError('reviewed crop rectangle missing')
        x, y, width, height = rectangle
        if (x < 0 or y < 0 or width < 8 or height < 8 or
                x + width > dimensions['width'] or y + height > dimensions['height']):
            raise ValueError('reviewed crop outside original camera')
        pixels = crop_decoder(root / (name + '.mkv'), frame, rectangle)
        if hashlib.sha256(pixels).hexdigest() != item.get('rgb24_sha256'):
            raise ValueError('reviewed original pixel hash differs')
        if not diagnostic and len(set(pixels)) <= 1:
            raise ValueError('uniform original pixel crop cannot verify walker')
        if item.get('walker_body_visible') not in (True, False, 'unknown'):
            raise ValueError('independent walker visibility observation missing')
        seen.add(name)
        if item['walker_body_visible'] is True:
            visible.append((name, frame))
    if seen != set(CAMERAS):
        raise ValueError('independent four-camera review incomplete')
    if diagnostic:
        if saved['diagnostic_fixture'] is not True or packet.get('diagnostic_fixture') is not True:
            raise ValueError('diagnostic proof provenance differs')
        status = 'software_diagnostic_only'
    else:
        if saved['diagnostic_fixture'] is not False or packet.get('diagnostic_fixture') is not False:
            raise ValueError('physical original-pixel review required')
        if packet.get('actual_original_pixels') is not True or expected != 400:
            raise ValueError('physical original-pixel review required')
        seal_path = root / 'capture-seal.json'
        seal = json.loads(seal_path.read_text())
        if (seal.get('format') != 'worker-sealed-capture' or seal.get('provenance_kind') != 'native' or
                seal.get('frames') != 400 or seal.get('restoration', {}).get('restored') is not True or
                seal.get('events') != ['capture_finished', 'encoders_closed', 'restoration_verified']):
            raise ValueError('Native capture lifecycle incomplete')
        for name, digest in seal.get('sources', {}).items():
            source = (root / name).resolve()
            if not source.is_relative_to(root) or not source.is_file() or sha(source) != digest:
                raise ValueError('sealed original source differs')
        if not {'reviewed-site-audit.json', 'native-crosswalk-readback.json'} <= set(seal['sources']):
            raise ValueError('reviewed Native site and crosswalk sources missing')
        required_sources = {'scene.json', 'reviewed-site.json', 'reviewed-site-audit.json',
                            'native-crosswalk-readback.json', 'walker-body-history.jsonl',
                            'camera-frame-joins.jsonl', *(name + '.mkv' for name in CAMERAS)}
        if not required_sources <= set(seal['sources']):
            raise ValueError('sealed original source inventory incomplete')
        if any(seal['sources'][name] != digest for name, digest in saved['sources_sha256'].items()):
            raise ValueError('sealed source differs from original acquisition index')
        scene = json.loads((root / 'scene.json').read_text())
        if json.loads((root / 'reviewed-site-audit.json').read_text()) != audit_reviewed_site(scene, root):
            raise ValueError('reviewed original site receipt differs from source documents')
        readback = json.loads((root / 'native-crosswalk-readback.json').read_text())
        if (readback.get('case_id') != case_id or
                readback.get('loaded_map_sha256') != scene.get('map_source_sha256') or
                not readback.get('authored_polygon_readbacks')):
            raise ValueError('Native crosswalk readback differs from exact scene')
        rows = [json.loads(line) for line in (root / 'walker-body-history.jsonl').read_text().splitlines()]
        completion = evaluate_crossing_completion(scene, rows)
        if completion['physical_checks']['maneuver']['status'] != 'met':
            raise ValueError('original walker physical completion missing')
        if len({frame for _, frame in visible}) < 2 or not {'overview', 'reference_corner'} <= {name for name, _ in visible}:
            raise ValueError('independent original walker pixel visibility missing')
        status = 'native_sources_reviewed'
    return {'format': 'worker-pedestrian-original-pixel-audit', 'case_id': case_id,
            'status': status, 'passed': not diagnostic, 'source_review_sha256': sha(review_path),
            'original_camera_frames': expected, 'observed_cameras': sorted(seen),
            'legal_verdict': 'unresolved', 'physical_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--review', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    result = audit(args.attempt, args.review, args.case, diagnostic=args.diagnostic)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case_id': args.case, 'status': result['status'], 'passed': result['passed']}))


if __name__ == '__main__':
    main()
