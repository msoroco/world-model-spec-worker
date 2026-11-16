"""Package the first signed red-curb case without changing ordinary receipts."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
NATIVE = ROOT / 'native'
sys.path.insert(0, str(NATIVE))
import exception_road


def encode(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def build():
    case_id = ROOT.name + '__ordinary_red_signed'
    cases = json.loads((ROOT / 'exception-case-matrix.json').read_text())['cases']
    case = next(item for item in cases if item['case_id'] == case_id)
    if case['requested_stationary_duration_s'] != 12 or case['service_class'] != 'ordinary':
        raise ValueError('Signed-case source definition changed')
    base = json.loads((ROOT / 'selected-primary/reference/construction.json').read_text())
    files = {item['path']: item['content'] for item in base['files']}
    road = exception_road.construct(case)
    if exception_road.readback(road)['sign_readback']['displayed_classes'] != ['no_parking']:
        raise ValueError('Signed road readback differs')
    files['red-curb-road.xodr'] = road
    files['case-plan.json'] = (ROOT / 'case-plan.json').read_text()
    files['tests/test_selected.py'] = files['tests/test_selected.py'].replace(
        "40 if cfg['case_id'].endswith('__reference') else 60", "40")
    files['tests/test_selected.py'] = files['tests/test_selected.py'].replace(
        "self.assertEqual(cfg['requested_target_x_m'],40)",
        "self.assertEqual(cfg['requested_target_x_m'],40)\n"
        "        self.assertEqual(cfg['sign_classes'], ['no_parking'])")
    for target, source in (
        ('runner.py', 'signed_runner.py'),
        ('finalize_selected.py', 'finalize_signed.py'),
        ('measure_exceptions.py', 'measure_exceptions.py'),
        ('exception_road.py', 'exception_road.py')):
        files[target] = (NATIVE / source).read_text()
    cfg = json.loads(files['config.json'])
    cfg.update(case_id=case_id, selected_case_id=case_id,
               supported_case_ids=[case_id], sign_classes=case['sign_classes'],
               service_class=case['service_class'],
               native_blueprint='vehicle.tesla.model3',
               road_sha256=digest(road),
               case_plan_sha256=digest(files['case-plan.json']))
    files['config.json'] = encode(cfg)
    base['case_id'] = case_id
    base['files'] = [{'path': path, 'content': content} for path, content in files.items()]
    base['status'] = 'draft_selected_cpu'
    base['recording_description']['limitations'].append(
        'Sign classes are authored OpenDRIVE; Native signal readback and pixels require separate review.')
    base['recording_description']['context_inputs'][0]['method'] = (
        'source-hashed Native OpenDRIVE parking lane, red paint and signed signal readback')
    base['measurement_plan'] = {
        'source': 'retained Native body, velocity, red paint and signal readback',
        'finalizer': 'finalize_selected.py', 'legal_verdict': None}
    target = ROOT / 'selected-primary/ordinary_red_signed/construction.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(encode(base))
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    row = plan['requirement_dispositions'][3]
    if row['status'] != 'selected_required' or row['case_ids'] != [case_id]:
        raise ValueError('Signed source requirement is not selected')
    contract = {'format': 'worker-measurement-contract',
                'case_id': case_id,
                'requirements': [{'disposition_index': 3,
                    'requirement': row['requirement'], 'source': row['source'],
                    'output_key': 'signed_curb_observation',
                    'method': 'signed_context', 'value_type': 'object',
                    'kind': 'measured',
                    'inputs': ['native-raw-actors.jsonl',
                               'native-map-readback.json']}],
                'negative': {'remove': ['native-map-readback.json'],
                    'error_contains': 'Missing required source: native-map-readback.json'},
                'scope': 'Observed signed red-curb stop and context, without legal verdict'}
    contract_path = target.parent / 'selected-measurement-contracts/ordinary_red_signed.json'
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(encode(contract))
    proposal = {'case_id': case_id, 'target_law_id': 'LVMC-11-52-030-A',
                'target_type': 'attempt',
                'rationale': ('Ordinary vehicle at painted red curb with authored no-parking '
                              'sign, for the sign/no-sign comparison; Native sign and pixels '
                              'remain physically unverified.'),
                'variable_assignments': {
                    'road_and_actors': {'kind': 'world_setup',
                                        'value': 'authored red curb and no-parking signal'},
                    'requested_parking_x_m': {'kind': 'controller', 'value': 40, 'unit': 'm'},
                    'red_curb_stop_or_park': {'kind': 'subject_behavior', 'value': None}},
                'recording_description': base['recording_description'],
                'unresolved_judgment_calls': ['Native sign visibility and statutory exceptions']}
    shared = ROOT / 'proposals/cases.json'
    proposals = json.loads(shared.read_text())
    proposals['cases'] = [p for p in proposals['cases'] if p['case_id'] != case_id] + [proposal]
    proposals['cases'].sort(key=lambda p: p['case_id'])
    shared.write_text(encode(proposals))
    manifest = json.loads((ROOT / 'execution-manifest-diagnostic-reference.json').read_text())
    entry = manifest['cases'][0]
    entry.update(case_id=case_id,
                 construction='selected-primary/ordinary_red_signed/construction.json',
                 construction_sha256=digest(target.read_text()),
                 measurement_contract='selected-primary/ordinary_red_signed/'
                     'selected-measurement-contracts/ordinary_red_signed.json',
                 measurement_procedure={'entrypoint': 'finalize_selected.py',
                     'output_schema': 'c150142-red-curb-saved-analysis-v1'},
                 fixture_recipe=(ROOT / 'selected-diagnostics/ordinary_red_signed/'
                     'primary-recipe.json').relative_to(REPO).as_posix(),
                 candidate_risk={'status': 'physical',
                     'reason': 'Native sign rendering, red paint, parked body and four views unverified'})
    manifest['status'] = 'signed_primary_offline_in_progress'
    manifest_path = ROOT / 'execution-manifest-diagnostic-ordinary_red_signed.json'
    manifest_path.write_text(encode(manifest))
    return {'case_id': case_id, 'construction_sha256': digest(target.read_text()),
            'road_sha256': digest(road), 'files': len(files),
            'manifest': str(manifest_path)}


if __name__ == '__main__':
    print(encode(build()), end='')
