"""Bind a shared lateral-correction fallback for the linked exact cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / 'v2-selected-pair-manifest.json').read_text())
    for number, entry in enumerate(manifest['cases'], 1):
        primary = json.loads((HERE / entry['construction']).read_text())
        fallback = json.loads(json.dumps(primary))
        for file in fallback['files']:
            if file['path'] == 'runner.py':
                old = 'max(-0.2, min(0.2, x_error))'
                if file['content'].count(old) != 1:
                    raise ValueError('Primary lateral correction changed')
                file['content'] = file['content'].replace(old, 'max(-0.4, min(0.4, x_error))')
            elif file['path'] == 'config.json':
                config = json.loads(file['content'])
                config['candidate_id'] = 'fallback1'
                file['content'] = json.dumps(config, indent=2) + '\n'
        path = HERE / f'draft-exact/probe_{number}/fallback1/construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fallback, indent=2) + '\n')
        entry['candidates'] = [{'id': 'fallback1', 'construction': str(path.relative_to(HERE)),
            'construction_sha256': sha(path),
            'trigger': {'source': 'original Native actor-poses.jsonl and requested_path',
                'metric': 'lateral_error_at_roadway_entry_m',
                'failure_condition': 'Original physical primary drift puts body outside its requested crosswalk relation at roadway entry'},
            'changed_knobs': ['Walker lateral correction clamp 0.2 to 0.4; same policy in both linked cases']}]
    manifest['status'] = 'partial_fallback1_cpu'
    (HERE / 'v2-fallback1-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps([e['candidates'][0]['construction_sha256'] for e in manifest['cases']]))


if __name__ == '__main__':
    main()
