"""CPU proof that original-review annotations bind every decoded video frame."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from prepare_saved import _decoded_frame_hashes, prepare

spec = importlib.util.spec_from_file_location('bridge_fixture', HERE / 'prove-saved-bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def _write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def _reject(source, output, case, ffmpeg, expected):
    try:
        prepare(source, output, case, ffmpeg)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError('Wrong rejection: ' + str(error)) from error
    else:
        raise AssertionError('Expected rejection: ' + expected)


def prove():
    ffmpeg = HERE.parents[1] / '.runtime-work/linux_arm64/ffmpeg'
    if not ffmpeg.is_file():
        raise ValueError('Pinned local FFmpeg binary absent')
    results = []
    with tempfile.TemporaryDirectory(prefix='c405647-original-framehash-') as temporary:
        scratch = Path(temporary)
        for case in ('witness_1', 'witness_2'):
            source = scratch / (case + '-source')
            bridge._source(source, case)
            rows = _rows(source / 'observed-actors.jsonl')
            for row in rows:
                row['source_kind'] = 'original_native'
            _write_rows(source / 'observed-actors.jsonl', rows)
            (source / 'front_lamp.source').unlink()
            video = source / 'front_lamp.mkv'
            subprocess.run([str(ffmpeg), '-hide_banner', '-loglevel', 'error',
                            '-f', 'lavfi', '-i', 'color=c=red:s=16x16:r=20:d=24',
                            '-c:v', 'ffv1', '-n', str(video)], check=True, timeout=120)
            hashes = _decoded_frame_hashes(video, ffmpeg)
            review_path = source / 'front-lamp-review.json'
            review = json.loads(review_path.read_text())
            review['source_kind'] = 'original_pixel_review'
            review['reviewer'] = 'synthetic CPU test reviewer; no physical observation'
            review['source_video_sha256'] = hashlib.sha256(video.read_bytes()).hexdigest()
            for annotation, frame_hash in zip(review['frames'], hashes):
                annotation['pixel_frame_sha256'] = frame_hash
            review_path.write_text(json.dumps(review, sort_keys=True) + '\n')
            result = prepare(source, scratch / (case + '-positive'), case, ffmpeg)
            assert result['frames'] == 480 and result['physical_success_claimed'] is False
            changed = scratch / (case + '-wrong-frame')
            shutil.copytree(source, changed)
            bad = json.loads((changed / 'front-lamp-review.json').read_text())
            bad['frames'][120]['pixel_frame_sha256'] = '0' * 64
            (changed / 'front-lamp-review.json').write_text(json.dumps(bad) + '\n')
            _reject(changed, scratch / (case + '-wrong-frame-out'), case, ffmpeg,
                    'Lamp review decoded pixel frame hash differs')
            changed = scratch / (case + '-missing-reviewer')
            shutil.copytree(source, changed)
            bad = json.loads((changed / 'front-lamp-review.json').read_text())
            bad.pop('reviewer')
            (changed / 'front-lamp-review.json').write_text(json.dumps(bad) + '\n')
            _reject(changed, scratch / (case + '-missing-reviewer-out'), case, ffmpeg,
                    'Original lamp review attribution absent')
            changed = scratch / (case + '-short-video')
            shutil.copytree(source, changed)
            (changed / 'front_lamp.mkv').unlink()
            subprocess.run([str(ffmpeg), '-hide_banner', '-loglevel', 'error',
                            '-f', 'lavfi', '-i', 'color=c=red:s=16x16:r=20:d=24',
                            '-frames:v', '479', '-c:v', 'ffv1', '-n',
                            str(changed / 'front_lamp.mkv')], check=True, timeout=120)
            bad = json.loads((changed / 'front-lamp-review.json').read_text())
            bad['source_video_sha256'] = hashlib.sha256(
                (changed / 'front_lamp.mkv').read_bytes()).hexdigest()
            (changed / 'front-lamp-review.json').write_text(json.dumps(bad) + '\n')
            _reject(changed, scratch / (case + '-short-video-out'), case, ffmpeg,
                    'Original lamp video decoded frame count differs')
            results.append({'case_suffix': case, 'decoded_frames': len(hashes),
                            'frame_hash_bound': True,
                            'wrong_frame_reviewer_and_short_video_rejected': True,
                            'physical_success_claimed': False})
    return {'passed': True, 'results': results,
            'scope': 'synthetic CPU FFV1 decode and review-frame binding only; no original pixels or physical observation'}


if __name__ == '__main__':
    print(json.dumps(prove(), indent=2))
