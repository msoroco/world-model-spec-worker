"""Small FFV1 CPU decode fixture and damaging source negatives."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from audit_media import audit_media
from measure_original import CAMERAS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    scratch = Path('.runtime-work/c183370-media').resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as folder:
        folder = Path(folder)
        specs = {name: {'width': 64, 'height': 48} for name in CAMERAS}
        hashes = {}
        for name in CAMERAS:
            path = folder / (name + '.mkv')
            command = ['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi',
                       '-i', 'color=c=blue:s=64x48:r=20:d=0.6',
                       '-frames:v', '12', '-c:v', 'ffv1', str(path)]
            if subprocess.run(command, capture_output=True).returncode:
                raise RuntimeError('Synthetic FFV1 source generation failed')
            hashes[path.name] = sha(path)
        seal = folder / 'captured-source-hashes.json'
        seal.write_text(json.dumps({'source_kind': 'original_native_capture',
                                    'sha256': hashes}) + '\n')
        positive = audit_media(folder, specs, 12)
        if len(positive['cameras']) != 4 or positive['actual_pixels_interpreted']:
            raise AssertionError('Four-view decode proof differs')
        wrong = dict(specs)
        wrong['flagger'] = {'width': 80, 'height': 48}
        try:
            audit_media(folder, wrong, 12)
        except ValueError as error:
            if 'profile or duration differs' not in str(error):
                raise
        else:
            raise AssertionError('Wrong camera profile accepted')
        flagger = folder / 'flagger.mkv'
        flagger.write_bytes(flagger.read_bytes()[:-50])
        try:
            audit_media(folder, specs, 12)
        except ValueError as error:
            if 'source missing or changed' not in str(error):
                raise
        else:
            raise AssertionError('Changed camera bytes accepted')
        flagger.write_bytes(b'not a video\n')
        sealed = json.loads(seal.read_text())
        sealed['sha256']['flagger.mkv'] = sha(flagger)
        seal.write_text(json.dumps(sealed) + '\n')
        try:
            audit_media(folder, specs, 12)
        except ValueError as error:
            if 'media probe failed' not in str(error):
                raise
        else:
            raise AssertionError('Resealed nonvideo source accepted')
        flagger.unlink()
        try:
            audit_media(folder, specs, 12)
        except ValueError as error:
            if 'source missing or changed' not in str(error):
                raise
        else:
            raise AssertionError('Missing camera accepted')
    with tempfile.TemporaryDirectory(dir=scratch) as folder:
        folder = Path(folder)
        hashes = {}
        for name in CAMERAS:
            path = folder / (name + '.mkv')
            command = ['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi',
                       '-i', 'color=c=blue:s=64x48:r=20:d=30',
                       '-frames:v', '600', '-c:v', 'ffv1', str(path)]
            if subprocess.run(command, capture_output=True).returncode:
                raise RuntimeError('Synthetic 600-frame FFV1 source generation failed')
            hashes[path.name] = sha(path)
        (folder / 'captured-source-hashes.json').write_text(
            json.dumps({'source_kind': 'original_native_capture', 'sha256': hashes}) + '\n')
        exact_duration = audit_media(folder, specs, 600)
        if len(exact_duration['cameras']) != 4:
            raise AssertionError('600-frame four-view decode differs')
    return {'format': 'c183370-ffv1-media-cpu-proof',
            'synthetic_fixture_frames': [12, 600], 'four_camera_full_decode': True,
            'positive_count': 2, 'negative_count': 4,
            'original_native_observed': False,
            'actual_pixels_interpreted': False,
            'physical_or_legal_outcome_claimed': False}


if __name__ == '__main__':
    print(json.dumps(prove()))
