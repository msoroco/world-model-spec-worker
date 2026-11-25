"""Build one near-side-crosswalk exact Native construction without changing old cases."""
import hashlib
import json
from pathlib import Path

from route import requested_rows

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parents[1]
REPO = HERE.parents[3]
CASE = ASSIGNMENT.name + '__controlled_4'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    source = REPO / 'inputs' / ASSIGNMENT.name / 'assignment.json'
    base = json.loads((ASSIGNMENT / 'native/native-bundles/controlled_1/construction.json').read_text())
    request = HERE / 'request-controlled_4.jsonl'
    request.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n'
                               for row in requested_rows('controlled_4')))
    base['case_id'] = CASE
    files = {item['path']: item for item in base['files']}
    for name in ('runner.py', 'crossroads.xodr', 'road.xodr', 'finalize.py',
                 'measure_saved.py', 'route.py', 'check.py'):
        actual = HERE / ('crossroads.xodr' if name == 'road.xodr' else name)
        files[name]['content'] = actual.read_text()
    files['request.jsonl']['content'] = request.read_text()
    config = json.loads(files['config.json']['content'])
    config.update({'case_id': CASE, 'case_suffix': 'controlled_4',
                   'selected_case_id': CASE, 'case': {'case_id': CASE},
                   'supported_case_ids': [CASE], 'request_sha256': sha(request),
                   'assignment_sha256': sha(source), 'candidate_id': 'primary'})
    files['config.json']['content'] = json.dumps(config, indent=2) + '\n'
    base['status'] = 'selected_native_cpu_draft_not_delivery_prepared'
    base['recording_description']['limitations'].append(
        'Imported near-side crosswalk pixels and position require original image review')
    path = ASSIGNMENT / 'native/native-bundles/controlled_4/construction.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(base, indent=2) + '\n')
    manifest_path = ASSIGNMENT / 'draft-native-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['cases'] = [item for item in manifest['cases'] if item['case_id'] != CASE]
    manifest['cases'].append({
        'case_id': CASE, 'kind': 'delivery',
        'construction': str(path.relative_to(ASSIGNMENT)),
        'construction_sha256': sha(path),
        'fixture_recipe': str((HERE / 'diagnostic-controlled_4-fixture-recipe.json').relative_to(REPO)),
        'measurement_contract': 'native/controlled_4-measurement-contract.json',
        'candidate_risk': {'status': 'physical',
                           'reason': 'Imported crosswalk object may not appear in retained pixels'},
        'measurement_procedure': {'entrypoint': 'finalize.py'},
        'candidates': [], 'delivery_readiness': 'incomplete'})
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    return {'case_id': CASE, 'construction_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(build()))
