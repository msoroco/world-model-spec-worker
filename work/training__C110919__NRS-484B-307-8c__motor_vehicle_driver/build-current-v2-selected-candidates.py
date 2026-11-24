"""Bind the retained two primary cases and two physical-risk fallbacks each."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def config(bundle):
    return json.loads(next(item['content'] for item in bundle['files'] if item['path'] == 'config.json'))


def main():
    draft = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    cases = []
    for suffix in ('probe_a', 'probe_b'):
        old = next(item for item in draft['cases'] if item['case_id'] == HERE.name + '__' + suffix)
        primary_path = HERE / old['construction']
        primary = json.loads(primary_path.read_text())
        base_config = config(primary)
        entry = copy.deepcopy(old)
        entry['measurement_contract'] = f'current-v2-{suffix}-measurement-contract.json'
        entry['fixture_recipe'] = f'work/{HERE.name}/current-v2-{suffix}-fixture-recipe.json'
        entry['candidates'] = []
        for historic in old['candidates'][:2]:
            candidate = historic['id']
            original = json.loads((HERE / historic['construction']).read_text())
            altered = config(original)
            differences = [name for name, value in altered['knobs'].items()
                           if base_config['knobs'].get(name) != value]
            if len(differences) != 1 or differences != historic['changed_knobs']:
                raise ValueError('Fallback must change one declared engineering knob')
            bundle = copy.deepcopy(primary)
            for item in bundle['files']:
                if item['path'] == 'config.json':
                    item['content'] = json.dumps(altered, indent=2, allow_nan=False) + '\n'
            if bundle['recording_description'] != primary['recording_description']:
                raise ValueError('Fallback recording changed')
            target = HERE / 'current-v2-candidates' / suffix / candidate / 'construction.json'
            write(target, bundle)
            entry['candidates'].append({**historic, 'construction': target.relative_to(HERE).as_posix(),
                                        'construction_sha256': sha(target)})
        cases.append(entry)
    manifest = {'format': 'worker-unselected-current-v2-candidate-manifest',
                'assignment_id': HERE.name, 'status': 'draft_not_selected',
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'), 'cases': cases}
    target = HERE / 'current-v2-candidate-manifest.json'
    write(target, manifest)
    print(json.dumps({'manifest_sha256': sha(target), 'cases': len(cases), 'fallbacks': 4}))


if __name__ == '__main__':
    main()
