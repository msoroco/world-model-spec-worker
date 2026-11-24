"""Exercise full four-view saved decode on all retained exact diagnostics."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from saved_media_audit import audit_media

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('acquisition-provenance.json', 'acquisition.json', 'scene.json',
           'walker-body-history.jsonl', 'camera-frame-joins.jsonl',
           *(name+'.mkv' for name in CAMERAS))


def prove():
    results = {}
    for scene_path in sorted((ROOT/'cases').glob('*/scene.json')):
        name = scene_path.parent.name
        attempt = REPO/'.runtime-work'/('c227749-compat-'+name+'-v3')
        if not all((attempt/source).is_file() for source in SOURCES):
            raise ValueError(name+': retained exact compatibility attempt missing')
        report = audit_media(attempt)
        if report['case_id'] != json.loads(scene_path.read_text())['case_id']:
            raise ValueError(name+': exact case identity differs')
        if any(value['fully_decoded_frames'] != 5 for value in report['cameras'].values()):
            raise ValueError(name+': expected five fully decoded diagnostic frames')
        results[name] = {'case_id': report['case_id'], 'camera_frames': 5,
                         'camera_count': 4, 'positive': 'passed',
                         'source_sha256': {key: report['source_sha256'][key+'.mkv'] for key in CAMERAS},
                         'physical_visibility': 'unconfirmed'}
    source = REPO/'.runtime-work'/'c227749-compat-outside_right_angle-v3'
    with tempfile.TemporaryDirectory(prefix='c227749-media-negative-', dir=REPO/'.runtime-work') as temp:
        attempt = Path(temp)
        for name in SOURCES:
            shutil.copyfile(source/name, attempt/name)
        short = attempt/'short.mkv'
        command = ['ffmpeg', '-nostdin', '-v', 'error', '-i', str(attempt/'overview.mkv'),
                   '-frames:v', '4', '-c:v', 'ffv1', str(short)]
        subprocess.run(command, check=True, capture_output=True)
        short.replace(attempt/'overview.mkv')
        index_path = attempt/'acquisition.json'
        index = json.loads(index_path.read_text())
        index['overview.mkv']['sha256'] = hashlib.sha256((attempt/'overview.mkv').read_bytes()).hexdigest()
        index_path.write_text(json.dumps(index)+'\n')
        try:
            audit_media(attempt)
        except ValueError as error:
            if 'decoded frame count differs' not in str(error):
                raise
            negative = str(error)
        else:
            raise ValueError('short but source-hashed camera passed full decode audit')
    return {'exact_case_diagnostics': results,
            'source_hashed_short_video_negative': negative,
            'diagnostic_only': True}


if __name__ == '__main__':
    print(json.dumps(prove(), indent=2, sort_keys=True))
