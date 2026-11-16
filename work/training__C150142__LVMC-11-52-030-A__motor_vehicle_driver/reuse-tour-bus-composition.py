"""Reuse a completed diagnostic composition only for identical four-view sources."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def reuse(source_stage, target_attempt):
    source_stage, target_attempt = Path(source_stage), Path(target_attempt)
    receipt = json.loads((source_stage / 'four-view-receipt.json').read_text())
    if receipt['format'] != 'synchronized-four-view' or receipt['frames'] != 36120:
        raise ValueError('Only the completed 36,120-frame diagnostic composition can be reused')
    for view in VIEWS:
        name = view + '.mkv'
        if receipt['sources'][view] != sha(source_stage / name) or \
                receipt['sources'][view] != sha(target_attempt / name):
            raise ValueError('Source video differs: ' + view)
    if receipt['frame_map_sha256'] != sha(source_stage / 'video_frames.jsonl') or \
            receipt['frame_map_sha256'] != sha(target_attempt / 'video_frames.jsonl'):
        raise ValueError('Frame map differs')
    composed = source_stage / 'raw.mkv'
    if receipt['primary_sha256'] != sha(composed):
        raise ValueError('Composition differs from the completed receipt')
    target = target_attempt / 'raw.mkv'
    if target.exists():
        raise ValueError('Never overwrite an acquisition or prior composition')
    shutil.copy2(composed, target)
    return {'source_stage': str(source_stage), 'target_attempt': str(target_attempt),
            'composed_sha256': sha(target), 'source_receipt_sha256':
            sha(source_stage / 'four-view-receipt.json'),
            'reused_identical_synthetic_sources': True,
            'original_native_observed': False}


if __name__ == '__main__':
    print(json.dumps(reuse(sys.argv[1], sys.argv[2]), sort_keys=True))
