"""Build three case-preserving physical-risk alternatives for the other exact cases."""

import copy
import hashlib
import json
import math
from pathlib import Path

from build_primary_fallbacks import TRIGGERS, dump, sha

ROOT = Path(__file__).resolve().parent


def build():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases'][1:]:
        case = entry['case_id']
        suffix = case.split('__source_verified_', 1)[1]
        folder = ROOT / 'cases' / ('source_verified_' + suffix)
        primary = json.loads((ROOT / entry['construction']).read_text())
        previous = {row['id']: row for row in entry.get('candidates', [])}
        candidates = []
        for ident in ('fallback1', 'fallback2', 'fallback3'):
            construction = copy.deepcopy(primary)
            files = {row['path']: row for row in construction['files']}
            config = json.loads(files['config.json']['content'])
            changes = []
            if ident == 'fallback1':
                approach = config['site']['other_approach']
                heading = math.radians(approach[3])
                x = round(approach[0] - 2*math.cos(heading), 6)
                y = round(approach[1] - 2*math.sin(heading), 6)
                config['site']['other_approach'][:2] = [x, y]
                config['site']['routes']['other'][0] = [x, y]
                changes = ['other Native approach spawn and first waypoint move 2 m upstream along its declared heading']
            elif ident == 'fallback2':
                runner = files['runner.py']['content']
                old = 'site["routes"][role], progress[role])'
                if runner.count(old) != 1:
                    raise ValueError('Steering call changed for ' + case)
                files['runner.py']['content'] = runner.replace(
                    old, 'site["routes"][role], progress[role],\n'
                         '                                        lookahead_m=(4.0 if role == "other" else 5.0))')
                changes = ['other steering lookahead 5.0 -> 4.0 m; ego remains 5.0 m']
            else:
                config['site']['cameras']['overview'][2] += 3
                config['site']['cameras']['approach'][0] -= 3
                changes = ['overview camera height +3 m', 'approach camera x -3 m']
            if ident in ('fallback1', 'fallback3'):
                packet = json.loads(files['site-review.json']['content'])
                packet['site'] = config['site']
                files['site-review.json']['content'] = dump(packet)
                config['site_review']['sha256'] = hashlib.sha256(files['site-review.json']['content'].encode()).hexdigest()
                files['config.json']['content'] = dump(config)
            construction['candidate_id'] = ident
            path = folder / (ident + '-construction.json')
            path.write_text(dump(construction))
            candidate = {'id': ident, 'construction': str(path.relative_to(ROOT)),
                         'construction_sha256': sha(path), 'trigger': TRIGGERS[ident],
                         'changed_knobs': changes}
            if previous.get(ident, {}).get('construction_sha256') == candidate['construction_sha256']:
                for key in ('offline', 'compatibility', 'saved_processing'):
                    if key in previous[ident]:
                        candidate[key] = previous[ident][key]
            candidates.append(candidate)
        entry['candidates'] = candidates
        entry['candidate_risk'] = {'status': 'physical',
            'reason': 'Native other spawn, route tracking or four-camera body coverage may fail'}
    manifest_path.write_text(dump(manifest))
    print(json.dumps({'cases': len(manifest['cases']),
                      'candidates_per_case': [len(e['candidates']) for e in manifest['cases']]}))


if __name__ == '__main__':
    build()
