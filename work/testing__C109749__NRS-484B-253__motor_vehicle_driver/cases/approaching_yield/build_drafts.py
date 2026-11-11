"""Build the approaching-opponent primary and three risk-based draft bundles.

These are offline construction drafts. They enter the canonical manifest only
after case planning, saved processing and delivery/comparison proofs exist.
"""
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parents[2]
target = Path(__file__).resolve().parent
case = 'testing__C109749__NRS-484B-253__motor_vehicle_driver__approaching_yield'


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def construction(config):
    base = json.loads((folder / 'construction.json').read_text())
    base['case_id'] = case
    contents = {entry['path']: entry['content'] for entry in base['files']}
    contents.update({'runner.py': (target / 'runner.py').read_text(),
                     'config.json': json.dumps(config, indent=2) + '\n',
                     'finalizer.py': (target / 'finalizer.py').read_text(),
                     'approaching_yield_observation.py': (folder / 'approaching_yield_observation.py').read_text()})
    base['files'] = [{'path': path, 'content': content} for path, content in contents.items()]
    return base


def main():
    config = json.loads((target / 'config.json').read_text())
    primary = target / 'construction.json'
    write(primary, construction(config))
    plans = [
        ('fallback1', 'controller_release_ttc_s', 5.5,
         'subject does not slow while opposing complete body remains outside but approaches the junction'),
        ('fallback2', 'approach_speed_mps', 4.0,
         'subject reaches the approaching-opponent conflict region with excessive measured speed'),
        ('fallback3', 'reciprocal_approach_speed_mps', 1.5,
         'later opposing actor enters the junction before the subject completes the turn'),
    ]
    candidates = []
    for ident, knob, value, failure in plans:
        changed = dict(config, **{knob: value})
        path = target / (ident + '-construction.json')
        write(path, construction(changed))
        candidates.append({'id': ident, 'construction': path.name,
                           'construction_sha256': sha(path),
                           'trigger': {'source': 'interaction_history.jsonl and intersection_geometry.json',
                                       'metric': knob + ' physical-risk observation',
                                       'failure_condition': failure},
                           'changed_knobs': [knob]})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': folder.name,
                'cases': [{'case_id': case, 'construction': primary.name,
                           'construction_sha256': sha(primary),
                           'candidate_risk': {'status': 'physical',
                                              'reason': 'approaching opposing body, subject braking and later actor may fail staged motion'},
                           'candidates': candidates}]}
    write(target / 'draft-manifest.json', manifest)
    print(json.dumps({'case_id': case, 'primary_sha256': sha(primary),
                      'candidate_ids': [item['id'] for item in candidates]}))


if __name__ == '__main__':
    main()
