"""Build selected same-cell yielding constructions from the proven base shape."""
import copy
import hashlib
import json
from pathlib import Path

from route import requested_rows

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parents[1]
REPO = HERE.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    base = json.loads((ASSIGNMENT / 'native/native-bundles/controlled_1/construction.json').read_text())
    manifest_path = ASSIGNMENT / 'draft-native-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['cases'] = [entry for entry in manifest['cases']
                         if not entry['case_id'].endswith(('controlled_5', 'controlled_6'))]
    built = []
    for suffix in ('controlled_5', 'controlled_6'):
        case_id = ASSIGNMENT.name + '__' + suffix
        request = HERE / ('request-' + suffix + '.jsonl')
        request.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n'
                                   for row in requested_rows(suffix)))
        construction = copy.deepcopy(base)
        construction['case_id'] = case_id
        construction['status'] = 'selected_native_cpu_draft_not_delivery_prepared'
        files = {item['path']: item for item in construction['files']}
        for name in ('runner.py', 'crossroads.xodr', 'road.xodr', 'finalize.py',
                     'measure_saved.py', 'route.py', 'check.py'):
            actual = HERE / ('crossroads.xodr' if name == 'road.xodr' else name)
            files[name]['content'] = actual.read_text()
        files['assess_statutory.py'] = {'path': 'assess_statutory.py',
                                        'content': (HERE.parent / 'assess_statutory.py').read_text()}
        construction['files'] = list(files.values())
        files['request.jsonl']['content'] = request.read_text()
        config = json.loads(files['config.json']['content'])
        config.update({'case_id': case_id, 'selected_case_id': case_id,
                       'case_suffix': suffix, 'case': {'case_id': case_id},
                       'supported_case_ids': [case_id],
                       'request_sha256': sha(request),
                       'assignment_sha256': sha(REPO / 'inputs' / ASSIGNMENT.name / 'assignment.json'),
                       'candidate_id': 'primary'})
        files['config.json']['content'] = json.dumps(config, indent=2) + '\n'
        construction['recording_description']['limitations'].append(
            'Other-vehicle prior stop or intersection occupancy needs original full-body Native review')
        path = ASSIGNMENT / 'native/native-bundles' / suffix / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(construction, indent=2) + '\n')
        manifest['cases'].append({'case_id': case_id, 'kind': 'delivery',
            'construction': str(path.relative_to(ASSIGNMENT)),
            'construction_sha256': sha(path),
            'fixture_recipe': str((HERE / f'diagnostic-{suffix}-fixture-recipe.json').relative_to(REPO)),
            'measurement_contract': f'native/{suffix}-measurement-contract.json',
            'candidate_risk': {'status': 'physical',
                'reason': 'Native other-vehicle stop or occupancy may differ from requested track'},
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'candidates': [], 'delivery_readiness': 'incomplete'})
        built.append({'case_id': case_id, 'construction_sha256': sha(path)})
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    return built


if __name__ == '__main__':
    print(json.dumps(build()))
