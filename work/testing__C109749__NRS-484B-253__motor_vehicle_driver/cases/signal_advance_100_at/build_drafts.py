"""Build the exact 30.48 m signal-advance runner and three risk fallbacks.

This is an isolated construction draft. It is not a canonical selected case
until source-bound diagnostic, saved-processing and audit proofs are complete.
"""
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parents[2]
target = Path(__file__).resolve().parent
case = folder.name + '__signal_advance_100_at'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def construction(config):
    base = json.loads((folder / 'construction.json').read_text())
    base['case_id'] = case
    base['recording_description'] = config['recording_description']
    content = {item['path']: item['content'] for item in base['files']}
    content.update({
        'runner.py': (target / 'runner.py').read_text(),
        'config.json': json.dumps(config, indent=2) + '\n',
        'finalizer.py': (target / 'finalizer.py').read_text(),
        'inside_oncoming_setup.py': (folder / 'inside_oncoming_setup.py').read_text(),
        'inside_yield_observation.py': (folder / 'inside_yield_observation.py').read_text(),
        'advance_signal_setup.py': (folder / 'advance_signal_setup.py').read_text(),
        'signal_advance_native_probe.py': (folder / 'signal_advance_native_probe.py').read_text(),
        'signal_advance_audit.py': (folder / 'signal_advance_audit.py').read_text(),
    })
    base['files'] = [{'path': name, 'content': value} for name, value in content.items()]
    return base


def main():
    config = json.loads((target / 'config.json').read_text())
    primary = target / 'construction.json'
    write(primary, construction(config))
    plans = (
        ('fallback1', 'signal_onset_margin_m', 12.0,
         'original signal onset has insufficient continuous preturn distance'),
        ('fallback2', 'approach_speed_mps', 4.0,
         'subject reaches the occupied junction at excessive measured speed'),
        ('fallback3', 'inside_oncoming_travel_m', 8.0,
         'initial opposing complete body does not fit in the selected junction'),
    )
    candidates = []
    for ident, knob, value, failure in plans:
        changed = dict(config, **{knob: value})
        path = target / (ident + '-construction.json')
        write(path, construction(changed))
        candidates.append({
            'id': ident, 'construction': path.name, 'construction_sha256': sha(path),
            'trigger': {'source': 'interaction_history.jsonl and intersection_geometry.json',
                        'metric': knob + ' original-source physical-risk check',
                        'failure_condition': failure},
            'changed_knobs': [knob],
        })
    manifest = {
        'format': 'worker-execution-manifest', 'assignment_id': folder.name,
        'cases': [{'case_id': case, 'construction': primary.name,
                   'construction_sha256': sha(primary),
                   'candidate_risk': {
                       'status': 'physical',
                       'reason': 'upstream lane extent, signalled path length, occupied junction and subject speed may not realize in Native motion'},
                   'candidates': candidates}],
    }
    write(target / 'draft-manifest.json', manifest)
    print(json.dumps({'case_id': case, 'construction_sha256': sha(primary),
                      'fallbacks': [x['id'] for x in candidates]}))


if __name__ == '__main__':
    main()
