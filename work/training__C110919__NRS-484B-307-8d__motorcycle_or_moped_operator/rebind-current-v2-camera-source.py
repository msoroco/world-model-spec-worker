"""Embed the corrected current four-view camera source in both primaries."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
camera_source = (HERE / 'native/cameras.py').read_text()
for condition in ('condition_a', 'condition_b'):
    path = HERE / f'saved-diagnostic/{condition}/construction.json'
    bundle = json.loads(path.read_text())
    cameras = [item for item in bundle['files'] if item['path'] == 'cameras.py']
    if len(cameras) != 1:
        raise ValueError('One camera source required')
    cameras[0]['content'] = camera_source
    path.write_text(json.dumps(bundle, indent=2, allow_nan=False) + '\n')
    print(condition, hashlib.sha256(path.read_bytes()).hexdigest())
