"""Create a corrected limousine draft manifest without changing prior receipts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'execution-manifest-diagnostic-limo_below-draft.json'
OUTPUT = ROOT / 'execution-manifest-diagnostic-limo_below-draft-v2.json'


def build():
    manifest = json.loads(SOURCE.read_text())
    if OUTPUT.exists():
        raise ValueError('Use the existing v2 manifest; do not overwrite it')
    if len(manifest['cases']) != 4:
        raise ValueError('Expected four limousine boundaries')
    changes = 0
    for case in manifest['cases']:
        if not case['case_id'].endswith(('__limo_below', '__limo_at',
                                         '__limo_above', '__limo_no_loading')):
            raise ValueError('Unexpected limousine case')
        for candidate in case['candidates']:
            trigger = candidate['trigger']
            for field in ('source', 'metric'):
                before = trigger[field]
                after = before.replace('bus body', 'provisional limo-service sedan body')
                changes += before != after
                trigger[field] = after
            if 'bus body' in json.dumps(trigger):
                raise ValueError('Stale bus-body risk wording')
    if changes != 12:
        raise ValueError('Unexpected risk metadata changes')
    OUTPUT.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    return {'source': SOURCE.name, 'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            'manifest': OUTPUT.name, 'sha256': hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
            'changed_risk_fields': changes, 'case_count': len(manifest['cases'])}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
