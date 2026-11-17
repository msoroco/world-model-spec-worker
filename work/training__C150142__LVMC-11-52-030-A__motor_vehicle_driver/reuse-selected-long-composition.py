"""Copy a completed synthetic composition to an exact matching selected attempt.

The pinned saved processor will still recheck source decodes, timestamps and the
final rendered video. This helper only avoids recomposing identical camera bytes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


REPO = Path(__file__).resolve().parents[2]
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FRAMES = {36120, 36121, 36122}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(path.read_text())


def reuse(source_stage, target_attempt):
    source_stage = Path(source_stage).resolve()
    target_attempt = Path(target_attempt).resolve()
    if REPO / '.runtime-work' not in source_stage.parents or \
            REPO / '.runtime-work' not in target_attempt.parents:
        raise ValueError('Synthetic compositions must stay under ignored .runtime-work')
    receipt_path = source_stage / 'four-view-receipt.json'
    receipt = read(receipt_path)
    frames = read(target_attempt / 'config.json')['capture_frames']
    if receipt.get('format') != 'synchronized-four-view' or \
            frames not in FRAMES or receipt.get('frames') != frames or \
            read(source_stage / 'config.json')['capture_frames'] != frames:
        raise ValueError('Completed composition frame contract differs')
    for view in VIEWS:
        name = view + '.mkv'
        expected = receipt['sources'][view]
        if sha(source_stage / name) != expected or \
                sha(target_attempt / name) != expected:
            raise ValueError('Source video differs: ' + view)
    frame_map = receipt['frame_map_sha256']
    if sha(source_stage / 'video_frames.jsonl') != frame_map or \
            sha(target_attempt / 'video_frames.jsonl') != frame_map:
        raise ValueError('Frame map differs')
    composed = source_stage / 'raw.mkv'
    if sha(composed) != receipt['primary_sha256']:
        raise ValueError('Composition differs from its completed receipt')
    target = target_attempt / 'raw.mkv'
    if target.exists():
        raise ValueError('Never overwrite an acquisition or prior composition')
    shutil.copy2(composed, target)
    if sha(target) != receipt['primary_sha256']:
        target.unlink()
        raise ValueError('Copied composition differs')
    return {'format': 'c150142-checked-long-composition-reuse-v1',
            'source_stage': str(source_stage),
            'target_attempt': str(target_attempt), 'frames': frames,
            'composed_sha256': receipt['primary_sha256'],
            'source_receipt_sha256': sha(receipt_path),
            'reused_identical_synthetic_sources': True,
            'original_native_observed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source_stage')
    parser.add_argument('target_attempt')
    args = parser.parse_args()
    print(json.dumps(reuse(args.source_stage, args.target_attempt), sort_keys=True))
