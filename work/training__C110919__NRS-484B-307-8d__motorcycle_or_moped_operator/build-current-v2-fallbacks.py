"""Carry six historical one-knob alternatives into the current four-view bundle."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def config(bundle):
    return json.loads(next(item['content'] for item in bundle['files'] if item['path'] == 'config.json'))


def main():
    legacy = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    entries = []
    for condition in ('condition_a', 'condition_b'):
        primary_path = HERE / f'saved-diagnostic/{condition}/construction.json'
        primary = json.loads(primary_path.read_text())
        original = config(primary)
        old_entry = next(x for x in legacy['cases'] if x['case_id'] == primary['case_id'])
        entry = {
            'case_id': primary['case_id'],
            'kind': 'draft_not_selected',
            'candidate_risk': old_entry['candidate_risk'],
            'construction': primary_path.relative_to(HERE).as_posix(),
            'construction_sha256': digest(primary_path),
            'measurement_contract': f'current-v2-{condition}-measurement-contract.json',
            'measurement_procedure': old_entry['measurement_procedure'],
            'fixture_recipe': f'work/{HERE.name}/current-v2-{condition}-fixture-recipe.json',
            'candidates': [],
        }
        for old in old_entry['candidates']:
            name = old['id']
            old_bundle = json.loads((HERE / old['construction']).read_text())
            old_config = config(old_bundle)
            bundle = copy.deepcopy(primary)
            modified = copy.deepcopy(original)
            modified['candidate_id'] = name
            changes = [key for key in old_config['knobs']
                       if key != 'camera_profile' and old_config['knobs'][key]
                       != config(json.loads((HERE / f'draft-candidates/{condition}/primary/construction.json').read_text()))['knobs'][key]]
            if len(changes) != 1:
                raise ValueError(f'{condition}/{name}: expected one changed knob, got {changes}')
            knob = changes[0]
            modified['knobs'][knob] = old_config['knobs'][knob]
            for item in bundle['files']:
                if item['path'] == 'config.json':
                    item['content'] = json.dumps(modified, indent=2, allow_nan=False) + '\n'
            if bundle['recording_description'] != primary['recording_description']:
                raise ValueError('Recording contract changed')
            target = HERE / f'current-v2-candidates/{condition}/{name}/construction.json'
            write(target, bundle)
            entry['candidates'].append({**{k: old[k] for k in ('id', 'trigger', 'changed_knobs')},
                                        'construction': target.relative_to(HERE).as_posix(),
                                        'construction_sha256': digest(target)})
        entries.append(entry)
    manifest = {
        'format': 'worker-unselected-current-v2-candidate-manifest',
        'assignment_id': HERE.name,
        'status': 'draft_not_selected',
        'runtime_manifest_sha256': digest(ROOT / 'runtime/SOURCE-MANIFEST.json'),
        'cases': entries,
    }
    target = HERE / 'current-v2-candidate-manifest.json'
    write(target, manifest)
    print(json.dumps({'manifest_sha256': digest(target), 'candidates': sum(len(x['candidates']) for x in entries)}))


if __name__ == '__main__':
    main()
