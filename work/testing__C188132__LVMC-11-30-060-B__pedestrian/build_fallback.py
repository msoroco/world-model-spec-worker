"""Author a fixed alternate four-camera placement for occlusion risk."""
from __future__ import annotations

import json
from pathlib import Path
from overpass_source import sha

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    first = '''    sites = {"overview": (-18.0, -15.0, 22.0),
             "approach": (-12.0, -3.0, 4.0),
             "reference_corner": (8.0, 11.0, 10.0),
             "driver_reference": (-8.0, -2.0, 2.2)}'''
    second = '''    sites = {"overview": (-14.0, 16.0, 23.0),
             "approach": (-20.0, 5.0, 7.0),
             "reference_corner": (13.0, -12.0, 11.0),
             "driver_reference": (-10.0, 4.0, 2.8)}'''
    for entry in manifest['cases']:
        variant = entry['case_id'].split('__')[-1]
        primary = json.loads((ROOT / entry['construction']).read_text())
        candidate = json.loads(json.dumps(primary))
        modified = False
        for file in candidate['files']:
            if file['path'] == 'native_capture.py':
                if first not in file['content']:
                    raise ValueError('primary camera placement changed')
                file['content'] = file['content'].replace(first, second)
                file.pop('source', None)
                modified = True
        if not modified:
            raise ValueError('Native camera source absent')
        path = ROOT / 'cases' / variant / 'fallback1' / 'construction.json'
        write(path, candidate)
        entry['candidates'] = [{'id': 'fallback1',
            'construction': str(path.relative_to(ROOT)),
            'construction_sha256': sha(path),
            'trigger': {'source': 'original-pixel-review.json',
                        'metric': 'overpass_structure_visible and participant visibility in all four camera views',
                        'failure_condition': 'any required original view has false visibility after primary capture'},
            'changed_knobs': ['four fixed camera world poses while retaining the same camera names, resolutions, FOV, rate and duration']}]
    write(manifest_path, manifest)


if __name__ == '__main__':
    main()
