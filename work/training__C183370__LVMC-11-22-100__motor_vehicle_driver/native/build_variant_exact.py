"""Build draft exact barrier crossing/avoidance constructions for CPU proof."""
import hashlib
import json
from pathlib import Path

from build_exact import source_file
from capture import CAMERAS
from variant_bundle_runner import KNOBS
from variant_recording_contract import ASSIGNMENT, config as variant_config

PACKAGE = Path(__file__).resolve().parents[1]
NATIVE = PACKAGE / 'native'
MODULES = ('pathing.py', 'scene_plan.py', 'live_readback.py',
           'recording_contract.py', 'route_control.py', 'capture.py',
           'statutory_variants.py', 'variant_recording_contract.py',
           'variant_capture.py', 'analyze.py', 'variant_analyze.py',
           'variant_finalize.py')

FALLBACKS = {
    'fallback1': {
        'trigger': {'source': 'native-actors.jsonl',
                    'metric': 'sampled body/route tracking near surveyed pavement',
                    'failure_condition': 'ego overshoots the requested crossing or avoidance route'},
        'changed_knobs': ['lower requested controller speed from 4 to 3 m/s']},
    'fallback2': {
        'trigger': {'source': 'overview.mkv',
                    'metric': 'visibility of barrier actor and full surveyed pavement region',
                    'failure_condition': 'overview pixels omit the barrier or a pavement edge'},
        'changed_knobs': ['raise overview camera from 24 to 28 m and pitch from -55 to -62 degrees']},
    'fallback3': {
        'trigger': {'source': 'native-actors.jsonl',
                    'metric': 'sampled lateral route error on barrier approach',
                    'failure_condition': 'body footprint leaves the intended route corridor'},
        'changed_knobs': ['reduce waypoint reach from 1.5 to 1.0 m',
                          'increase steering response by reducing divisor from 40 to 32 degrees']},
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(kind, route, candidate='primary'):
    if kind != 'barrier' or route not in ('crossing', 'avoidance'):
        raise ValueError('Only the barrier pair is constructed in this draft')
    if candidate not in KNOBS:
        raise ValueError('Unknown variant candidate')
    cfg = variant_config(kind, route, 600)
    cfg.update(assignment_id=ASSIGNMENT, selected_case_id=cfg['case_id'],
               required_atoms=[], source_packets=[],
               original_native_observed=False, physical_success_claimed=False,
               cameras=[{'name': name, 'width': width, 'height': height,
                         'fov_deg': fov, 'pose_strategy': 'ego_attached'}
                        for name, width, height, fov, *_ in CAMERAS])
    controls, cameras = KNOBS[candidate]
    cfg.update(candidate_id=candidate, controller_knobs=controls,
               camera_overrides=cameras)
    files = [source_file('runner.py', NATIVE / 'variant_bundle_runner.py'),
             source_file('tests/test_bundle.py', NATIVE / 'variant_offline_bundle_test.py')]
    files.extend(source_file('native/' + name, NATIVE / name) for name in MODULES)
    files.append({'path': 'config.json',
                  'content': json.dumps(cfg, indent=2, sort_keys=True) + '\n'})
    return {'case_id': cfg['case_id'], 'law_id': cfg['law_id'],
            'cell_id': cfg['cell_id'], 'actor': cfg['actor'],
            'entrypoint': 'runner.py', 'files': files,
            'status': 'draft_exact_barrier_source_finalization_offline',
            'original_native_observed': False, 'delivery_ready': False,
            'recording_description': cfg['recording_description'],
            'measurement_plan': {'selected_variable': 'requested_pavement_crossing',
                                 'requested_footprint_contact': route == 'crossing',
                                 'source': 'original actor body vertices and surveyed pavement polygon',
                                 'barrier_and_repair': 'independent original source review required',
                                 'employee_exception': 'independent original source review required'},
            'static_checks': ['runner.py --check', 'tests/test_bundle.py'],
            'termination_rules': {'frames': 600, 'capture_rate_hz': 20},
            'mechanisms': {'scene': 'source-surveyed live map and barrier actor',
                           'control': 'native/route_control.py',
                           'capture': 'native/variant_capture.py',
                           'source_analysis': 'native/variant_analyze.py',
                           'finalization': 'native/variant_finalize.py'}}


def write():
    cases = []
    for route in ('crossing', 'avoidance'):
        variants = {}
        for candidate in KNOBS:
            folder = PACKAGE / 'draft-variant-candidates' / 'barrier' / route / candidate
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / 'construction.json'
            path.write_text(json.dumps(build('barrier', route, candidate), indent=2, sort_keys=True) + '\n')
            variants[candidate] = {'construction': str(path.relative_to(PACKAGE)),
                                   'construction_sha256': sha(path)}
        candidates = [dict(id=candidate, **variants[candidate], **FALLBACKS[candidate])
                      for candidate in FALLBACKS]
        cases.append({'case_id': ASSIGNMENT + '__barrier_' + route,
                      'kind': 'delivery',
                      **variants['primary'],
                      'measurement_contract': 'variant-measurement-contracts/barrier-' + route + '.json',
                      'fixture_recipe': 'work/' + ASSIGNMENT + '/variant-diagnostics/barrier/' + route + '/primary-recipe.json',
                      'measurement_procedure': {
                          'entrypoint': 'native/variant_finalize.py',
                          'output_schema': 'c183370-variant-diagnostic-finalization-v1'},
                      'candidate_risk': {'status': 'physical',
                          'reason': 'Barrier content, surface repair and Native body tracking remain unverified'},
                      'candidates': candidates,
                      'candidate_offline_status': 'pending',
                      'finalizer_status': 'cpu_unit_tested_not_saved_proven'})
    runtime = PACKAGE.parents[1] / 'runtime/pipeline/SOURCE-MANIFEST.json'
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': ASSIGNMENT,
                'status': 'draft_barrier_source_finalization_not_delivery_ready',
                'runtime_manifest_sha256': sha(runtime),
                'cases': cases}
    path = PACKAGE / 'draft-barrier-capture-manifest.json'
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return path


if __name__ == '__main__':
    print(write())
