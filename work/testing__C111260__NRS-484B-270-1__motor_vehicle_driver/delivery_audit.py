"""Independent saved bicycle delivery audit with reviewed original pixels.

CPU fixtures exercise this acquisition protocol. No result here decides lawful
riding, intent, interference, or canonical acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from bicycle_encounter import ASSIGNMENT, MODES, SourceError, require, read_source
from delivery_decode import finalize_delivery
from saved_attempt import VIEWS


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare_original_image_to_video(video, frame, png, width, height):
    """Compare a reviewed original PNG with its decoded encoded video frame.

    A four-level RGB tolerance covers ordinary codec color conversion. It is
    an engineering join, not a rider detector or visibility judgment.
    """
    from PIL import Image
    command = ['ffmpeg', '-v', 'error', '-i', str(video), '-vf',
               f'select=eq(n\\,{frame})', '-frames:v', '1', '-pix_fmt', 'rgb24',
               '-f', 'rawvideo', '-']
    completed = subprocess.run(command, capture_output=True, check=False)
    require(completed.returncode == 0 and len(completed.stdout) == width * height * 3,
            'reviewed encoded video frame missing')
    with Image.open(png) as source_image:
        original = source_image.convert('RGB').tobytes()
    require(len(original) == len(completed.stdout) and
            all(abs(a - b) <= 4 for a, b in zip(original, completed.stdout)),
            'original PNG and encoded video frame differ')


def audit(attempt, case_id, pixel_review, *, expected_frames=900):
    root = Path(attempt).resolve()
    require(root.is_dir(), 'saved original attempt missing')
    require(case_id in {ASSIGNMENT + '__' + mode for mode in MODES},
            'wrong exact bicycle case')
    mode = case_id.removeprefix(ASSIGNMENT + '__')
    index_path = root / 'source-index.json'
    require(index_path.is_file(), 'original source index missing')
    index = json.loads(index_path.read_text(encoding='utf-8'))
    require(index.get('format') == 'c111260-original-index-v1' and
            index.get('case_id') == case_id and
            index.get('frame_count') == expected_frames,
            'original source index identity or duration mismatch')
    refs = index.get('sources')
    require(isinstance(refs, dict) and set(refs) ==
            {'site', 'events', 'frame_map', *VIEWS},
            'original site, events, frame map and four cameras required')
    source_paths = {key: read_source(ref, root) for key, ref in refs.items()}
    require(len(set(source_paths.values())) == len(refs), 'original sources must be distinct')
    site = json.loads(source_paths['site'].read_text(encoding='utf-8'))
    require(site.get('assignment_id') == ASSIGNMENT and
            site.get('case_id') == case_id, 'source site exact case mismatch')
    events = json.loads(source_paths['events'].read_text(encoding='utf-8'))
    frame_map = [json.loads(line) for line in
                 source_paths['frame_map'].read_text(encoding='utf-8').splitlines()]
    require(len(events) == len(frame_map) == expected_frames,
            'original frame map duration mismatch')
    first_time = frame_map[0].get('time_s')
    require(isinstance(first_time, (int, float)) and math.isfinite(first_time),
            'first original frame time missing')
    for number, (event, row) in enumerate(zip(events, frame_map)):
        require(row.get('video_frame') == number and
                row.get('carla_frame') == event.get('frame') and
                row.get('native_frame') == event.get('frame') and
                event.get('camera_frame') == event.get('frame') and
                isinstance(row.get('time_s'), (int, float)) and
                math.isfinite(row['time_s']) and
                abs(row['time_s'] - first_time - number / 20) < 1e-4,
                'original frame map/event identity mismatch')
    originals = index.get('camera_originals')
    require(isinstance(originals, dict) and set(originals) == set(VIEWS),
            'four original image inventories missing')
    image_sha = {}
    image_sizes = {}
    image_paths = set()
    for view in VIEWS:
        entries = originals[view]
        require(isinstance(entries, list) and len(entries) == expected_frames,
                'original image sequence incomplete: ' + view)
        image_sha[view] = {}
        image_sizes[view] = set()
        for number, row in enumerate(entries):
            require(row.get('frame') == frame_map[number]['carla_frame'] and
                    row.get('time_s') == frame_map[number]['time_s'],
                    'original image/frame join mismatch: ' + view)
            ref = row.get('image')
            image_path = read_source(ref, root)
            require(image_path not in image_paths,
                    'original camera images must be distinct')
            image_paths.add(image_path)
            require(image_path.suffix.lower() == '.png',
                    'original image must be PNG: ' + view)
            from PIL import Image
            with Image.open(image_path) as image:
                require(image.format == 'PNG' and image.width > 0 and image.height > 0,
                        'original PNG decode failed: ' + view)
                image_sizes[view].add((image.width, image.height))
                image.verify()
            image_sha[view][number] = ref['sha256']
    camera_refs = {view: refs[view] for view in VIEWS}
    receipt = finalize_delivery(site, root, refs['events'], camera_refs,
                                mode, expected_frames)
    for view in VIEWS:
        decoded = receipt['camera_decode_receipts'][view]
        require(image_sizes[view] == {(decoded['width'], decoded['height'])},
                'original PNG/video dimensions differ: ' + view)
    review_path = Path(pixel_review).resolve()
    require(review_path.is_file(), 'independent pixel review missing')
    review = json.loads(review_path.read_text(encoding='utf-8'))
    require(review.get('case_id') == case_id and
            review.get('source_index_sha256') == _sha(index_path) and
            review.get('site_sha256') == refs['site']['sha256'] and
            review.get('events_sha256') == refs['events']['sha256'],
            'stale or wrong-case independent pixel review')
    views = review.get('views')
    require(isinstance(views, dict) and set(views) == set(VIEWS),
            'four-view independent pixel review missing')
    for view in VIEWS:
        item = views[view]
        decoded = receipt['camera_decode_receipts'][view]
        require(item.get('video_sha256') == decoded['source_sha256'] and
                item.get('framemd5_sha256') == decoded['framemd5_sha256'],
                'pixel review video/decode binding differs: ' + view)
        samples = item.get('samples')
        require(isinstance(samples, list) and samples,
                'independent rider pixel samples missing: ' + view)
        require(all(isinstance(row.get('frame'), int) and
                    0 <= row['frame'] < expected_frames and
                    row.get('rider_visible') is True and
                    row.get('rider_kind') == site['rider_kind'] and
                    row.get('original_png_sha256') == image_sha[view][row['frame']] and
                    isinstance(row.get('reviewer'), str) and row['reviewer'].strip()
                    for row in samples),
                'unresolved rider pixel review: ' + view)
        for row in samples:
            image_path = read_source(originals[view][row['frame']]['image'], root)
            compare_original_image_to_video(source_paths[view], row['frame'],
                                            image_path, decoded['width'], decoded['height'])
    require(review.get('lawful_riding_verdict') is None and
            review.get('intent_verdict') is None and
            review.get('interference_verdict') is None,
            'unsupported legal verdict in pixel review')
    physical = review.get('physical_review')
    require(isinstance(physical, dict) and
            physical.get('completed') is True and
            physical.get('first_frame') == receipt['first_frame'] and
            physical.get('last_frame') == receipt['first_frame'] + expected_frames - 1 and
            isinstance(physical.get('reviewer'), str) and physical['reviewer'].strip() and
            receipt['observed_rider_motion_m'] > 0 and
            receipt['observed_ego_motion_m'] > 0,
            'physical encounter review or original movement missing')
    require(all(read_source(ref, root) == source_paths[key]
                for key, ref in refs.items()), 'original source changed during audit')
    return {'format': 'c111260-independent-delivery-audit-v1',
            'case_id': case_id, 'original_source_index_sha256': _sha(index_path),
            'original_event_sha256': refs['events']['sha256'],
            'pixel_review_sha256': _sha(review_path), 'frame_count': expected_frames,
            'checks': {'native_source': True, 'all_participants': True,
                       'time_join': True, 'full_video_decode': True,
                       'actual_pixels': True, 'physical_completion': True},
            'legal_verdict': None, 'canonical_acceptance': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--pixel-review', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, args.pixel_review), indent=2))


if __name__ == '__main__':
    main()
