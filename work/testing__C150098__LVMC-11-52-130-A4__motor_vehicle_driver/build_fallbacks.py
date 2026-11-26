"""Build measurable, source-gated alternate approach plans for every hydrant case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hydrant import CASES

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    entries = {row['case_id']: row for row in manifest['cases']}
    for case in CASES:
        entry = entries[HERE.name + '__' + case.suffix]
        original = json.loads((HERE / entry['construction']).read_text(encoding='utf-8'))
        alternate = json.loads(json.dumps(original))
        runner = next(item for item in alternate['files'] if item['path'] == 'runner.py')
        anchor = '    try:\n        print(capture_original('
        replacement = (
            '    try:\n'
            '        if not callable(getattr(adapter, "configure_recovery", None)):\n'
            '            raise ValueError("reviewed Native recovery controller required")\n'
            '        adapter.configure_recovery(approach_speed_mps=1.0, '
            'braking_buffer_m=2.0, camera_sightline_sweep=True)\n'
            '        print(capture_original(')
        if runner['content'].count(anchor) != 1:
            raise ValueError('runner recovery insertion point changed')
        runner['content'] = runner['content'].replace(anchor, replacement)
        alternate['measurement_plan'] = (
            original['measurement_plan'] +
            '; alternate low-speed approach and source-reviewed camera sightline sweep')
        alternate['mechanisms'].append(
            'source-gated recovery adapter lowers approach speed and widens sightline sweep')
        target = HERE / ('construction-' + case.suffix + '-fallback1.json')
        target.write_text(json.dumps(alternate, indent=2) + '\n', encoding='utf-8')
        entry['candidates'] = [{
            'id': 'fallback1',
            'construction': target.name,
            'construction_sha256': sha(target),
            'trigger': {
                'source': 'original Native body-hydrant history and four original camera decodes',
                'metric': 'target activity body-edge longitudinal gap or hydrant/body pixel visibility',
                'failure_condition': 'target gap outside 0.15 m tolerance or hydrant and vehicle edge not visible throughout target activity'},
            'changed_knobs': ['approach speed 1.0 m/s', 'braking buffer 2.0 m',
                              'source-reviewed camera sightline sweep'],
        }]
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
