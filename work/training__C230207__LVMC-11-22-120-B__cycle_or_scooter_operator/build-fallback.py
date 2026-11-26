"""Freeze a camera-placement fallback for an unreadable sign-face capture."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'draft-signed-roadway-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(SOURCE.read_text())
    manifest['format'] = 'worker-selected-cpu-manifest-v1'
    for entry in manifest['cases']:
        source = HERE / entry['construction']
        construction = json.loads(source.read_text())
        runner = next(item for item in construction['files'] if item['path'] == 'runner.py')
        old = "('reference_corner', 1280, 720, -55, -8, 5, -10)"
        new = "('reference_corner', 1280, 720, -44, -8, 5, -5)"
        if runner['content'].count(old) != 1:
            raise ValueError('Primary reference camera no longer matches frozen fallback source')
        runner['content'] = runner['content'].replace(old, new)
        construction['status'] = 'camera_visibility_fallback_cpu_draft'
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        target = HERE / 'draft-signed-roadway' / suffix / 'fallback1/construction.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(construction, indent=2) + '\n')
        entry['candidates'] = [{
            'id': 'fallback1',
            'construction': str(target.relative_to(HERE)),
            'construction_sha256': sha(target),
            'trigger': {'source': 'reference_corner.mkv',
                        'metric': 'reviewed sign-face readability in original source frames',
                        'failure_condition': 'sign wording cannot be independently read at the approach frames'},
            'changed_knobs': ['reference_corner camera x -55 to -44 m and pitch -10 to -5 degrees'],
        }]
    target = HERE / 'selected-offline-manifest.json'
    target.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest': str(target), 'fallback_hashes': [
        entry['candidates'][0]['construction_sha256'] for entry in manifest['cases']]}))


if __name__ == '__main__':
    main()
