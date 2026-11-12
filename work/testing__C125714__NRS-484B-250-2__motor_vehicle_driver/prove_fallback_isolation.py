"""Independently check declared engineering changes across all 24 fallbacks."""

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def files(construction):
    return {row['path']: row['content'] for row in construction['files']}


def audit():
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    checked = []
    for entry in manifest['cases']:
        primary = files(json.loads((ROOT / entry['construction']).read_text()))
        config = json.loads(primary['config.json'])
        for candidate in entry['candidates']:
            ident = candidate['id']
            alternative = files(json.loads((ROOT / candidate['construction']).read_text()))
            changed = {path for path in primary if primary[path] != alternative[path]}
            alt_config = json.loads(alternative['config.json'])
            if ident == 'fallback1':
                if changed != {'config.json', 'site-review.json'}:
                    raise ValueError('Spawn fallback changed unrelated files: ' + entry['case_id'])
                before, after = copy.deepcopy(config), copy.deepcopy(alt_config)
                before['site_review'] = after['site_review']
                before['site']['other_approach'][:2] = after['site']['other_approach'][:2]
                before['site']['routes']['other'][0] = after['site']['routes']['other'][0]
                if before != after:
                    raise ValueError('Spawn fallback changed comparison variables: ' + entry['case_id'])
                pose = config['site']['other_approach']
                new = alt_config['site']['other_approach']
                if pose[2:] != new[2:] or config['site']['other_entry'] != alt_config['site']['other_entry']:
                    raise ValueError('Spawn fallback changed heading or entry')
            elif ident == 'fallback2':
                if changed != {'runner.py'} or alt_config != config:
                    raise ValueError('Steering fallback changed case configuration')
                expected = primary['runner.py'].replace(
                    'site["routes"][role], progress[role])',
                    'site["routes"][role], progress[role],\n'
                    '                                        lookahead_m=(4.0 if role == "other" else 5.0))')
                if expected == primary['runner.py'] or alternative['runner.py'] != expected:
                    raise ValueError('Steering fallback changed unrelated control')
            elif ident == 'fallback3':
                if changed != {'config.json', 'site-review.json'}:
                    raise ValueError('Camera fallback changed unrelated files')
                before, after = copy.deepcopy(config), copy.deepcopy(alt_config)
                before['site_review'] = after['site_review']
                before['site']['cameras'] = after['site']['cameras']
                if before != after:
                    raise ValueError('Camera fallback changed comparison variables')
                if (after['site']['cameras']['overview'][2] != config['site']['cameras']['overview'][2] + 3 or
                    after['site']['cameras']['approach'][0] != config['site']['cameras']['approach'][0] - 3):
                    raise ValueError('Camera fallback lacks declared framing change')
            else:
                raise ValueError('Unsupported candidate: ' + ident)
            checked.append({'case_id': entry['case_id'], 'candidate': ident,
                            'changed_files': sorted(changed)})
    if len(checked) != 24:
        raise ValueError('All eight cases need three candidates')
    return {'format': 'worker-fallback-isolation-audit', 'passed': True,
            'checked': checked, 'physical_acceptance_claimed': False}


def main():
    receipt = audit()
    (ROOT / 'fallback-isolation-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'candidates': len(receipt['checked'])}))


if __name__ == '__main__':
    main()
