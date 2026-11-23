"""Diagnostic positive and changed-source checks for source binding."""
import copy
import hashlib
import json
import shutil
from pathlib import Path

from bind_lighting_sources import VIEWS, bind, sha


HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[2] / '.runtime-work' / 'c230241-source-binding-proof'
MEDIA = HERE.parents[2] / '.runtime-work' / 'c230241-video-compose-proof'


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def expect_reject(label, directory, phrase):
    try:
        bind(directory, 40)
    except ValueError as exc:
        assert phrase in str(exc), (label, str(exc))
        return {'case': label, 'rejected': str(exc)}
    raise AssertionError(label + ' unexpectedly accepted')


def main():
    assert all((MEDIA / (view + '.mkv')).is_file() for view in VIEWS), \
        'Run prove_video_compose.py first'
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    for view in VIEWS:
        shutil.copyfile(MEDIA / (view + '.mkv'), SCRATCH / (view + '.mkv'))
    native = [{'source_kind': 'synthetic_native_sample',
               'video_frame': index, 'native_frame': index + 2000,
               'time_s': index / 20, 'light_state_observed': 3}
              for index in range(40)]
    mapping = [{'video_frame': index, 'native_frame': index + 2000,
                'carla_frame': index + 2000, 'time_s': index / 20}
               for index in range(40)]
    review = [{'source_kind': 'synthetic_native_sample',
               'video_frame': index, 'native_frame': index + 2000,
               'time_s': index / 20} for index in range(40)]
    trace_path = SCRATCH / 'native-lighting-frames.jsonl'
    map_path = SCRATCH / 'video_frames.jsonl'
    review_path = SCRATCH / 'lighting-review.jsonl'
    context_path = SCRATCH / 'lighting-review-context.json'
    write_rows(trace_path, native)
    write_rows(map_path, mapping)
    write_rows(review_path, review)
    hashes = {view: sha(SCRATCH / (view + '.mkv')) for view in VIEWS}
    hashes[trace_path.name] = sha(trace_path)
    hashes[map_path.name] = sha(map_path)
    context = {'source_kind': 'synthetic_native_sample',
               'source_sha256': hashes, 'diagnostic_only': True}
    context_path.write_text(json.dumps(context, indent=2) + '\n')
    positive = bind(SCRATCH, 40)
    assert positive['source_integrity_verified'] and not positive['physical_visibility_verified']
    checks = [{'case': 'short-video-positive', 'frames': positive['frames'],
               'source_hashes': positive['source_sha256']}]
    changed = bytearray((SCRATCH / 'approach.mkv').read_bytes())
    changed[-1] ^= 1
    (SCRATCH / 'approach.mkv').write_bytes(changed)
    checks.append(expect_reject('changed-video', SCRATCH, 'source hashes differ'))
    shutil.copyfile(MEDIA / 'approach.mkv', SCRATCH / 'approach.mkv')
    altered = copy.deepcopy(review)
    altered[17]['native_frame'] += 1
    write_rows(review_path, altered)
    checks.append(expect_reject('review-frame-mismatch', SCRATCH,
                                'Review frame identity differs'))
    write_rows(review_path, review)
    context['source_sha256']['video_frames.jsonl'] = '0' * 64
    context_path.write_text(json.dumps(context, indent=2) + '\n')
    checks.append(expect_reject('changed-map-hash', SCRATCH,
                                'source hashes differ'))
    receipt = {'format': 'c230241-original-video-review-binding-proof-v1',
               'diagnostic_only': True, 'synthetic_frames': 40,
               'full_native_capture_verified': False, 'checks': checks,
               'binder_sha256': sha(HERE / 'bind_lighting_sources.py'),
               'prover_sha256': sha(Path(__file__))}
    output = HERE / 'source-binding-proof.json'
    output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'checks_passed': len(checks),
                      'receipt_sha256': sha(output)}))


if __name__ == '__main__':
    main()
