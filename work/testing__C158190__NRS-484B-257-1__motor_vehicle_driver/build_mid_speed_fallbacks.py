"""Build three physical-risk alternatives for the 4 m/s through-traffic case."""

import copy
import hashlib
import json
from pathlib import Path

from build_fallbacks import CHANGES

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'mid-speed-compatibility-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    if len(manifest['cases']) != 1 or not manifest['cases'][0]['case_id'].endswith('__yield_nearest_view_mid_speed'):
        raise ValueError('Expected the exact 4 m/s diagnostic case')
    entry = manifest['cases'][0]
    primary = json.loads((HERE / entry['construction']).read_text())
    folder = HERE / 'cases/through_mid/fallbacks'
    folder.mkdir(parents=True, exist_ok=True)
    candidates = []
    for ident, plan in CHANGES.items():
        candidate = copy.deepcopy(primary)
        for file in candidate['files']:
            if file['path'] in plan['files']:
                old, new = plan['files'][file['path']]
                if file['content'].count(old) != 1:
                    raise ValueError(f'{ident} missing unique anchor {old}')
                file['content'] = file['content'].replace(old, new)
                file.pop('source', None)
        path = folder / f'{ident}-construction.json'
        path.write_text(json.dumps(candidate, indent=2) + '\n')
        candidates.append({'id': ident,
                           'construction': str(path.relative_to(HERE)),
                           'construction_sha256': sha(path),
                           'trigger': plan['trigger'],
                           'changed_knobs': plan['changed_knobs']})
    entry['candidates'] = candidates
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': entry['case_id'],
                      'fallbacks': [item['id'] for item in candidates]}))


if __name__ == '__main__':
    main()
