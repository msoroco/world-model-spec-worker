"""Build three distinct physical-risk alternatives per exact speed case."""

import copy
import hashlib
import json
from pathlib import Path

from build_fallbacks import CHANGES

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / 'through-speed-compatibility-manifest.json'


def main():
    manifest = json.loads(MANIFEST.read_text())
    if len(manifest['cases']) != 3:
        raise ValueError('Three exact through-speed cases required')
    total = 0
    for entry in manifest['cases']:
        primary = json.loads((ROOT / entry['construction']).read_text())
        case_dir = (ROOT / entry['construction']).parent
        folder = case_dir / 'fallbacks'
        folder.mkdir(exist_ok=True)
        candidates = []
        for ident, definition in CHANGES.items():
            plan = copy.deepcopy(definition)
            if ident == 'fallback3':
                plan['trigger'] = {
                    'source': 'interaction_history.jsonl',
                    'metric': 'measured same-actor through-body speed versus commanded scalar target',
                    'failure_condition': 'measured through speed differs from its case target by more than 1 m/s before crossing',
                }
                plan['changed_knobs'] = ['bounded longitudinal speed-control gain from 0.25 to 0.4 for through actor']
            candidate = copy.deepcopy(primary)
            by_path = {item['path']: item for item in candidate['files']}
            for name, (old, new) in plan['files'].items():
                item = by_path[name]
                if item['content'].count(old) != 1:
                    raise ValueError(f'{entry["case_id"]} {ident}: missing unique anchor')
                item['content'] = item['content'].replace(old, new)
                item.pop('source', None)
            path = folder / f'{ident}-construction.json'
            path.write_text(json.dumps(candidate, indent=2) + '\n')
            candidates.append({
                'id': ident,
                'construction': str(path.relative_to(ROOT)),
                'construction_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'trigger': plan['trigger'], 'changed_knobs': plan['changed_knobs']})
            total += 1
        entry['candidates'] = candidates
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'exact_cases': 3, 'fallbacks': total}))


if __name__ == '__main__':
    main()
