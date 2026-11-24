"""Bind explicit synthetic diagnostic traces to the selected compatibility recipes.

The added velocity is derived from the authored diagnostic speed and heading.
It is never represented as an original Native observation.
"""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for suffix in ('reference', 'contrast'):
    old = HERE / f'v2-{suffix}-primary-fixture'
    trace = HERE / f'selected-{suffix}-synthetic-trace.jsonl'
    with trace.open('w') as output:
        for line in (old / 'trace.jsonl').read_text().splitlines():
            row = json.loads(line)
            angle = math.radians(row['heading_deg'])
            speed = row['speed_mps']
            row['velocity_mps'] = [speed * math.cos(angle), speed * math.sin(angle), 0.0]
            output.write(json.dumps(row, sort_keys=True) + '\n')
    capture = json.loads((old / 'capture/manifest.json').read_text())
    capture['sources']['trace.jsonl'] = sha(trace)
    selected_capture = HERE / f'selected-{suffix}-synthetic-capture-manifest.json'
    selected_capture.write_text(json.dumps(capture, indent=2, sort_keys=True) + '\n')
    recipe = json.loads((HERE / f'v2-{suffix}-primary-fixture-recipe.json').read_text())
    for item in recipe['sources']:
        if item['path'] == 'trace.jsonl':
            item['source'] = str(trace.relative_to(REPO))
            item['sha256'] = sha(trace)
        if item['path'] == 'capture/manifest.json':
            item['source'] = str(selected_capture.relative_to(REPO))
            item['sha256'] = sha(selected_capture)
    (HERE / f'selected-{suffix}-fixture-recipe.json').write_text(
        json.dumps(recipe, indent=2, sort_keys=True) + '\n')
