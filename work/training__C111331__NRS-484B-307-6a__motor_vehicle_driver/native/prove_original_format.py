"""Exercise the unreviewed original-size saved-video decoder on CPU fixtures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from signal_video_cpu import inspect_original_format

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FFMPEG = REPO / '.runtime-work/linux_arm64/ffmpeg'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    results = []
    for case in ('reference', 'contrast'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            receipt = json.loads((HERE / 'portable-receipts' / case / candidate / 'summary.json').read_text())
            fixture = REPO / receipt['fixture_runtime_relative']
            source = HERE / 'synthetic-saved' / case / candidate
            if sha(fixture / 'native_samples.jsonl') != sha(source / 'native_samples.jsonl'):
                raise ValueError('Original-format diagnostic source is stale')
            video = fixture / 'reference_corner.mkv'
            positive = inspect_original_format(fixture, video, FFMPEG)
            if positive['decoded_frames'] != 480 or positive['original_carla_pixels_verified']:
                raise ValueError('Original-format diagnostic promoted to physical evidence')
            wrong_size = False
            try:
                inspect_original_format(fixture, fixture / 'signal_reference.mkv', FFMPEG)
            except ValueError as exc:
                wrong_size = 'dimensions, rate or frame count differ' in str(exc)
            if not wrong_size:
                raise ValueError('Wrong-size original-format negative accepted')
            with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c111331-original-format-') as tmp:
                altered = Path(tmp)
                shutil.copy2(fixture / 'native_samples.jsonl', altered / 'native_samples.jsonl')
                mapping = [json.loads(line) for line in (fixture / 'video_frames.jsonl').read_text().splitlines()]
                mapping[0]['carla_frame'] = -1
                (altered / 'video_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in mapping))
                wrong_join = False
                try:
                    inspect_original_format(altered, video, FFMPEG)
                except ValueError as exc:
                    wrong_join = 'Native frame join differs' in str(exc)
                if not wrong_join:
                    raise ValueError('Wrong-join original-format negative accepted')
            results.append({'case': case, 'candidate': candidate,
                            'synthetic_fixture_manifest_sha256': receipt['fixture_manifest_sha256'],
                            'synthetic_video_sha256': positive['video_sha256'],
                            'native_sha256': positive['native_samples_sha256'],
                            'decoded_frame_count': positive['decoded_frames'],
                            'wrong_size_rejected': True, 'wrong_join_rejected': True})
    output = {'format': 'c111331-original-size-format-cpu-v1', 'rows': results,
              'positive_count': 8, 'negative_count': 16,
              'scope': 'synthetic original-size format and frame-join diagnostic only',
              'original_carla_pixels_or_signal_visibility_verified': False}
    path = HERE / 'original-format-summary.json'
    path.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'passed': True, 'summary_sha256': sha(path),
                      'positives': 8, 'negatives': 16}, sort_keys=True))


if __name__ == '__main__':
    prove()
