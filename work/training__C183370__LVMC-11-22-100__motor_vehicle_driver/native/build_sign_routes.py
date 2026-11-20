"""Construct exact sign-route drafts and explicit synthetic CPU sources."""
import hashlib
import json
from pathlib import Path

from build_variant_exact import PACKAGE, FALLBACKS, KNOBS, build, sha
from build_exact import source_file
from build_variant_diagnostic import variant
from build_diagnostic import REPO
from variant_recording_contract import ASSIGNMENT, config

KINDS = ('warning_sign', 'highway_closed_sign')
ROUTES = ('crossing', 'avoidance')


def write():
    cases = []
    for kind in KINDS:
        for route in ROUTES:
            cfg = config(kind, route, 600)
            variants = {}
            for candidate in KNOBS:
                construction = build('barrier', route, candidate)
                bundle_config = json.loads(next(f['content'] for f in construction['files']
                                                if f['path'] == 'config.json'))
                bundle_config.update(case_id=cfg['case_id'], selected_case_id=cfg['case_id'],
                                     control_kind=kind)
                for file in construction['files']:
                    if file['path'] == 'config.json':
                        file['content'] = json.dumps(bundle_config, indent=2, sort_keys=True) + '\n'
                    elif file['path'] == 'tests/test_bundle.py':
                        file.update(source_file('tests/test_bundle.py',
                                                PACKAGE / 'native/sign_offline_bundle_test.py'))
                construction.update(case_id=cfg['case_id'],
                                    status='draft_exact_sign_source_finalization_offline')
                construction['mechanisms']['scene'] = (
                    'C183370 fixed flagger plus separately source-surveyed ' + kind + ' actor')
                construction['measurement_plan']['barrier_and_repair'] = (
                    'original sign-face content and pavement repair review required')
                folder = PACKAGE / 'draft-variant-candidates' / kind / route / candidate
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / 'construction.json'
                path.write_text(json.dumps(construction, indent=2, sort_keys=True) + '\n')
                variants[candidate] = {'construction': str(path.relative_to(PACKAGE)),
                                       'construction_sha256': sha(path)}
            diagnostic = variant(route)
            files = diagnostic['files']
            readback = json.loads(files['live-readback.json'])
            readback['plan']['control_kind'] = kind
            readback['plan']['source_references'] = {
                'sign_face_source': 'synthetic_fixture_only_original_sign_face_unverified'}
            readback['control_type_id'] = 'static.prop.trafficwarning'
            files['live-readback.json'] = json.dumps(readback, indent=2) + '\n'
            receipt = json.loads(files['capture-receipt.json'])
            receipt['control_kind'] = kind
            receipt['control_content_verified'] = False
            files['capture-receipt.json'] = json.dumps(receipt, indent=2) + '\n'
            fixture_dir = PACKAGE / 'variant-diagnostics' / kind / route
            fixture_dir.mkdir(parents=True, exist_ok=True)
            spec = fixture_dir / 'primary.json'
            spec.write_text(json.dumps(diagnostic, separators=(',', ':')) + '\n')
            source = str(spec.relative_to(REPO))
            digest = hashlib.sha256(spec.read_bytes()).hexdigest()
            recipe = {'format': 'worker-fixture-recipe',
                      'sources': [{'path': 'diagnostic-source.json', 'source': source,
                                   'sha256': digest}],
                      'generator': {'source': source, 'sha256': digest}}
            (fixture_dir / 'primary-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
            contract = json.loads((PACKAGE / 'variant-measurement-contracts' /
                                   ('barrier-' + route + '.json')).read_text())
            contract['case_id'] = cfg['case_id']
            contract['scope'] = ('Source-derived surveyed contact and sign actor vicinity only; '
                                 'sign-face content, repair status, employee exception and legal verdict '
                                 'require original review.')
            (PACKAGE / 'variant-measurement-contracts' / (kind + '-' + route + '.json')).write_text(
                json.dumps(contract, indent=2) + '\n')
            fallback_rows = []
            for candidate, fallback in FALLBACKS.items():
                amended = json.loads(json.dumps(fallback))
                amended['trigger']['metric'] = amended['trigger']['metric'].replace('barrier', 'sign')
                amended['trigger']['failure_condition'] = amended['trigger']['failure_condition'].replace('barrier', 'sign')
                fallback_rows.append(dict(id=candidate, **variants[candidate], **amended))
            cases.append({'case_id': cfg['case_id'], 'kind': 'delivery', **variants['primary'],
                          'measurement_contract': 'variant-measurement-contracts/' + kind + '-' + route + '.json',
                          'fixture_recipe': 'work/' + ASSIGNMENT + '/variant-diagnostics/' + kind + '/' + route + '/primary-recipe.json',
                          'measurement_procedure': {'entrypoint': 'native/variant_finalize.py',
                                                    'output_schema': 'c183370-variant-diagnostic-finalization-v1'},
                          'candidate_risk': {'status': 'physical', 'reason':
                                             'Sign-face content, surface repair and Native body tracking remain unverified'},
                          'candidates': fallback_rows,
                          'candidate_offline_status': 'pending',
                          'finalizer_status': 'cpu_unit_tested_not_saved_proven'})
    runtime = PACKAGE.parents[1] / 'runtime/pipeline/SOURCE-MANIFEST.json'
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'status': 'draft_sign_source_finalization_not_delivery_ready',
                'runtime_manifest_sha256': sha(runtime), 'cases': cases}
    path = PACKAGE / 'draft-sign-capture-manifest.json'
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return path


if __name__ == '__main__':
    print(write())
