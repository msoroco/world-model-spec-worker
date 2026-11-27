"""Bind exact selected fallback constructions to the public receipt manifest."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    primary = json.loads((ROOT / 'selected-compat-manifest.json').read_text())
    prepared = json.loads((ROOT / 'selected-fallback-prepared.json').read_text())
    alternatives = {item['case_id']: item for item in prepared['alternatives']}
    for entry in primary['cases']:
        entry['candidates'] = [alternatives[entry['case_id']]]
        entry['candidate_risk'] = {'status': 'physical', 'reason':
            'Original vehicle may fail to spawn or meet the surveyed clearance; use source-measured fallback trigger.'}
    path = ROOT / 'selected-fallback-compat-manifest.json'
    path.write_text(json.dumps(primary, indent=2) + '\n')
    (ROOT / 'selected-proof-manifest.json').write_bytes((ROOT / 'selected-compat-manifest.json').read_bytes())
    print(json.dumps({'cases': len(primary['cases']), 'sha256': sha(path)}))


if __name__ == '__main__':
    main()
