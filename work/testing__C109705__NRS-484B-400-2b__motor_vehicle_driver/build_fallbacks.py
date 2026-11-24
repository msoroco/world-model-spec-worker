"""Retain a slower exact-case Native controller when primary misses route completion."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAMES = ('near_centerline', 'farther_from_centerline',
         'imaginary_near_centerline', 'imaginary_farther_from_centerline')


def build():
    for name in NAMES:
        source = json.loads((HERE / ('construction-' + name + '.json')).read_text())
        policy = next(item for item in source['files'] if item['path'] == 'construction.py')
        text = policy['content']
        for old, new in (("'target_speed_mps':7.0", "'target_speed_mps':5.0"),
                         ('target_speed_mps=7.0', 'target_speed_mps=5.0')):
            if text.count(old) != 1:
                raise ValueError('Native speed control implementation changed')
            text = text.replace(old, new)
        policy['content'] = text
        path = HERE / 'cases' / name / 'fallback1-construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(source, indent=2) + '\n')
        print(name, 'slower fallback selected for CPU proof')


if __name__ == '__main__':
    build()
