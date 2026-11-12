"""Build three engineering fallbacks for the near-time right-hand entry case."""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FOLDER = ROOT / 'cases/source_verified_other_right_near_time'
CASE = ROOT.name + '__source_verified_other_right_near_time'


def dump(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


TRIGGERS = {
    'fallback1': {
        'source': 'native-exit-feedback.json and capture/evidence.jsonl',
        'metric': 'other spawn success and first visible approach frame',
        'failure_condition': 'Other spawn fails at the primary approach or first approach frame is absent',
    },
    'fallback2': {
        'source': 'controller_history.jsonl and crossing_history.jsonl',
        'metric': 'other route target progress and lateral distance from sourced route',
        'failure_condition': 'Other route target stalls or lateral error exceeds 1 m before entering the crossing',
    },
    'fallback3': {
        'source': 'capture/manifest.json and four source-camera frame streams',
        'metric': 'visible complete body bounding boxes in overview and approach cameras',
        'failure_condition': 'Either complete body leaves the planned overview or approach image during entry',
    },
}


def build():
    FOLDER.mkdir(parents=True, exist_ok=True)
    primary = json.loads((ROOT / 'construction.json').read_text())
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(row for row in manifest['cases'] if row['case_id'] == CASE)
    previous = {row['id']: row for row in entry.get('candidates', [])}
    candidates = []
    for ident in ('fallback1', 'fallback2', 'fallback3'):
        construction = copy.deepcopy(primary)
        files = {row['path']: row for row in construction['files']}
        config = json.loads(files['config.json']['content'])
        changes = []
        if ident == 'fallback1':
            config['site']['other_approach'] = [0, -12, 0, 90]
            config['site']['routes']['other'][0] = [0, -12]
            changes = ['site.other_approach y: -10 -> -12 m',
                       'site.routes.other first waypoint y: -10 -> -12 m']
        elif ident == 'fallback2':
            runner = files['runner.py']['content']
            old = 'site["routes"][role], progress[role])'
            if runner.count(old) != 1:
                raise ValueError('Primary steering call changed')
            files['runner.py']['content'] = runner.replace(
                old, 'site["routes"][role], progress[role],\n'
                     '                                        lookahead_m=(4.0 if role == "other" else 5.0))')
            changes = ['other steering lookahead: 5.0 -> 4.0 m; ego remains at 5.0 m']
        else:
            config['site']['cameras']['overview'][2] = 28
            config['site']['cameras']['approach'][0] = -18
            changes = ['overview pose height: 25 -> 28 m',
                       'approach pose x: -15 -> -18 m']
        if ident in ('fallback1', 'fallback3'):
            packet = json.loads(files['site-review.json']['content'])
            packet['site'] = config['site']
            files['site-review.json']['content'] = dump(packet)
            config['site_review']['sha256'] = hashlib.sha256(files['site-review.json']['content'].encode()).hexdigest()
            files['config.json']['content'] = dump(config)
        construction['candidate_id'] = ident
        path = FOLDER / (ident + '-construction.json')
        path.write_text(dump(construction))
        candidate = {'id': ident, 'construction': str(path.relative_to(ROOT)),
                     'construction_sha256': sha(path), 'trigger': TRIGGERS[ident],
                     'changed_knobs': changes}
        if previous.get(ident, {}).get('construction_sha256') == candidate['construction_sha256']:
            for key in ('offline', 'compatibility', 'saved_processing'):
                if key in previous[ident]:
                    candidate[key] = previous[ident][key]
        candidates.append(candidate)
    entry['candidate_risk'] = {'status': 'physical',
        'reason': 'Native other spawn, route tracking or four-camera body coverage may fail'}
    entry['candidates'] = candidates
    manifest_path.write_text(dump(manifest))
    print(json.dumps({'case_id': CASE,
                      'candidates': {c['id']: c['construction_sha256'] for c in candidates}}))


if __name__ == '__main__':
    build()
