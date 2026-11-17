"""Reuse a full decode only when source bytes and frame map match exactly.

Run while a fresh pinned saved process is composing its four-view media. The
first source is left for a fresh decode; later receipts are copied before the
pin reaches those sources. All inputs and outputs stay under .runtime-work.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.media import verify_receipt


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def reuse(prior, output, frames, timeout_s=1800):
    prior, output = Path(prior).resolve(), Path(output).resolve()
    private = REPO / '.runtime-work'
    if private not in prior.parents or private not in output.parents:
        raise ValueError('Source decode reuse belongs under .runtime-work')
    stage = output / 'analysis'
    until = time.monotonic() + timeout_s
    while not (stage / 'result.json').is_file():
        if time.monotonic() > until:
            raise TimeoutError('Pinned selected analysis did not finish')
        time.sleep(.5)
    old = json.loads((prior / 'analysis/result.json').read_text())
    new = json.loads((stage / 'result.json').read_text())
    previous = {view: prior / f'source-{i}.json'
                for i, view in enumerate(old['video_references'])}
    if set(previous) != set(new['video_references']) or len(previous) != 4:
        raise ValueError('Camera references differ')
    mapping_sha = sha(stage / 'video_frames.jsonl')
    if mapping_sha != sha(prior / 'analysis/video_frames.jsonl'):
        raise ValueError('Camera frame map differs')
    copied = []
    for i, view in enumerate(new['video_references']):
        source = previous[view]
        video = stage / view
        verify_receipt(video, source, frames, mapping_sha256=mapping_sha)
        if i == 0:
            continue
        destination = output / f'source-{i}.json'
        if destination.exists():
            raise ValueError('Pinned decoder already reached source ' + str(i))
        shutil.copy2(source, destination)
        verify_receipt(video, destination, frames, mapping_sha256=mapping_sha)
        copied.append({'camera': view, 'receipt': destination.name,
                       'receipt_sha256': sha(destination)})
    return {'source_kind': 'synthetic_native_sample',
            'original_native_observed': False, 'frames': frames,
            'frame_map_sha256': mapping_sha, 'copied': copied,
            'fresh_decoded_camera': new['video_references'][0]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prior', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--frames', type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(reuse(args.prior, args.output, args.frames), sort_keys=True))
