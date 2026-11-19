"""Construct exact employee-exception drafts and explicit synthetic sources."""
import hashlib
import json

from build_variant_exact import PACKAGE, FALLBACKS, KNOBS, build, sha
from build_exact import source_file
from build_variant_diagnostic import variant
from build_diagnostic import REPO
from variant_recording_contract import ASSIGNMENT, config

ROUTES = ('employee_crossing', 'nonemployee_crossing')


def write():
    cases = []
    for route in ROUTES:
        cfg = config('employee_exception', route, 600)
        variants = {}
        for candidate in KNOBS:
            construction = build('barrier', 'crossing', candidate)
            bundle_config = json.loads(next(f['content'] for f in construction['files']
                                            if f['path'] == 'config.json'))
            bundle_config.update(case_id=cfg['case_id'], selected_case_id=cfg['case_id'],
                                 control_kind='employee_exception', case_suffix=route)
            for file in construction['files']:
                if file['path'] == 'config.json':
                    file['content'] = json.dumps(bundle_config, indent=2, sort_keys=True) + '\n'
                elif file['path'] == 'tests/test_bundle.py':
                    file.update(source_file('tests/test_bundle.py',
                                            PACKAGE / 'native/employee_offline_bundle_test.py'))
            construction.update(case_id=cfg['case_id'], status='draft_exact_employee_source_finalization_offline')
            construction['mechanisms']['scene'] = 'source-surveyed live pavement and activity-provenanced pedestrian'
            construction['measurement_plan']['employee_exception'] = 'independent original activity source review required'
            folder = PACKAGE / 'draft-variant-candidates/employee_exception' / route / candidate
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / 'construction.json'
            path.write_text(json.dumps(construction, indent=2, sort_keys=True) + '\n')
            variants[candidate] = {'construction': str(path.relative_to(PACKAGE)),
                                   'construction_sha256': sha(path)}
        diagnostic = variant('crossing')
        files = diagnostic['files']
        readback = json.loads(files['live-readback.json'])
        readback['plan']['control_kind'] = 'employee_exception'
        readback['plan']['cases'] = {
            name: {'requested_pavement_crossing': True,
                   'operator_activity_source': 'synthetic_fixture_only_' + name + '_activity_unverified'}
            for name in ROUTES}
        readback['plan']['source_references'] = {
            'employee_activity_source': 'synthetic_fixture_only_employee_activity_unverified',
            'nonemployee_activity_source': 'synthetic_fixture_only_nonemployee_activity_unverified'}
        readback['control_type_id'] = 'walker.pedestrian.0001'
        files['live-readback.json'] = json.dumps(readback, indent=2) + '\n'
        receipt = json.loads(files['capture-receipt.json'])
        receipt.update(case=route, control_kind='employee_exception',
                       employee_exception_verified=False)
        files['capture-receipt.json'] = json.dumps(receipt, indent=2) + '\n'
        actors = [json.loads(line) for line in files['native-actors.jsonl'].splitlines()]
        for actor in actors:
            actor['control_type_id'] = 'walker.pedestrian.0001'
            actor['employee_exception_verified'] = False
        files['native-actors.jsonl'] = ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in actors)
        fixture_dir = PACKAGE / 'variant-diagnostics/employee_exception' / route
        fixture_dir.mkdir(parents=True, exist_ok=True)
        spec = fixture_dir / 'primary.json'
        spec.write_text(json.dumps(diagnostic, separators=(',', ':')) + '\n')
        source = str(spec.relative_to(REPO))
        digest = hashlib.sha256(spec.read_bytes()).hexdigest()
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-source.json', 'source': source, 'sha256': digest}],
                  'generator': {'source': source, 'sha256': digest}}
        (fixture_dir / 'primary-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
        contract = json.loads((PACKAGE / 'variant-measurement-contracts/barrier-crossing.json').read_text())
        contract['case_id'] = cfg['case_id']
        contract['scope'] = ('Source-derived surveyed contact only; employee activity and legal exception '
                             'require independent original review.')
        (PACKAGE / 'variant-measurement-contracts' / ('employee_exception-' + route + '.json')).write_text(
            json.dumps(contract, indent=2) + '\n')
        fallback_rows = [dict(id=candidate, **variants[candidate], **FALLBACKS[candidate])
                         for candidate in FALLBACKS]
        cases.append({'case_id': cfg['case_id'], 'kind': 'delivery', **variants['primary'],
                      'measurement_contract': 'variant-measurement-contracts/employee_exception-' + route + '.json',
                      'fixture_recipe': 'work/' + ASSIGNMENT + '/variant-diagnostics/employee_exception/' + route + '/primary-recipe.json',
                      'measurement_procedure': {'entrypoint': 'native/variant_finalize.py',
                                                'output_schema': 'c183370-variant-diagnostic-finalization-v1'},
                      'candidate_risk': {'status': 'physical',
                                         'reason': 'Employee activity, surface repair and Native body tracking remain unverified'},
                      'candidates': fallback_rows, 'candidate_offline_status': 'pending',
                      'finalizer_status': 'cpu_unit_tested_not_saved_proven'})
    runtime = PACKAGE.parents[1] / 'runtime/pipeline/SOURCE-MANIFEST.json'
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'status': 'draft_employee_source_finalization_not_delivery_ready',
                'runtime_manifest_sha256': sha(runtime), 'cases': cases}
    path = PACKAGE / 'draft-employee-capture-manifest.json'
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return path


if __name__ == '__main__':
    print(write())
