"""Build source-bound, capture-stage exact newly laid pair candidates."""
import hashlib
import json
from pathlib import Path

from newly_laid_bundle_runner import KNOBS
from newly_laid_capture import CAMERAS
from newly_laid_recording_contract import ASSIGNMENT, CASES, config as recording_config

PACKAGE = Path(__file__).resolve().parent.parent
NATIVE = PACKAGE / 'native'
MODULES = ('pathing.py', 'route_control.py', 'newly_laid_plan.py',
           'newly_laid_recording_contract.py', 'newly_laid_capture.py')
FALLBACKS = {
    'fallback1': {
        'trigger': {'source': 'native-actors.jsonl',
                    'metric': 'sampled body/route tracking near laid-surface polygon',
                    'failure_condition': 'ego overshoots the surveyed crossing or avoidance route'},
        'changed_knobs': ['lower requested controller speed from 4 to 3 m/s']},
    'fallback2': {
        'trigger': {'source': 'overview.mkv',
                    'metric': 'warning-person and full laid-surface polygon visibility',
                    'failure_condition': 'overview pixels omit the warning person or laid-surface edge'},
        'changed_knobs': ['raise overview camera from 24 to 28 m and pitch from -55 to -62 degrees']},
    'fallback3': {
        'trigger': {'source': 'native-actors.jsonl',
                    'metric': 'sampled lateral route error on surface approach',
                    'failure_condition': 'body footprint leaves the surveyed route corridor'},
        'changed_knobs': ['reduce waypoint reach from 1.5 to 1.0 m',
                          'increase steering response by reducing divisor from 40 to 32 degrees']},
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_file(path, source):
    return {'path': path, 'content': source.read_text(),
            'source': 'work/' + ASSIGNMENT + '/native/' + source.name}


def build(case, candidate='primary'):
    if case not in CASES or candidate not in KNOBS:
        raise ValueError('Unknown newly laid exact case or candidate')
    cfg = recording_config(case, 600)
    controls, overrides = KNOBS[candidate]
    cfg.update(assignment_id=ASSIGNMENT, selected_case_id=cfg['case_id'],
               frames=600, required_atoms=[], source_packets=[],
               original_native_observed=False, physical_success_claimed=False,
               controller_knobs=controls, camera_overrides=overrides,
               candidate_id=candidate,
               cameras=[{'name': name, 'width': width, 'height': height,
                         'fov_deg': fov, 'pose_strategy': 'ego_attached'}
                        for name, width, height, fov, *_ in CAMERAS])
    files = [source_file('runner.py', NATIVE / 'newly_laid_bundle_runner.py'),
             source_file('tests/test_bundle.py', NATIVE / 'newly_laid_offline_bundle_test.py')]
    files.extend(source_file('native/' + name, NATIVE / name) for name in MODULES)
    files.append({'path': 'config.json',
                  'content': json.dumps(cfg, indent=2, sort_keys=True) + '\n'})
    return {'case_id': cfg['case_id'], 'law_id': cfg['law_id'],
            'cell_id': cfg['cell_id'], 'actor': cfg['actor'],
            'entrypoint': 'runner.py', 'files': files,
            'status': 'draft_exact_newly_laid_capture_stage',
            'original_native_observed': False, 'delivery_ready': False,
            'recording_description': cfg['recording_description'],
            'measurement_plan': {
                'selected_variable': 'requested_pavement_crossing',
                'requested_footprint_contact': case == CASES[0],
                'source': 'original actor body vertices and surveyed laid-surface polygon',
                'warning_and_laid_status': 'independent original source review required',
                'employee_exception': 'independent original source review required'},
            'static_checks': ['runner.py --check', 'tests/test_bundle.py'],
            'termination_rules': {'frames': 600, 'capture_rate_hz': 20},
            'mechanisms': {'scene': 'source-surveyed live C183370 map and warning person',
                           'control': 'native/route_control.py',
                           'capture': 'native/newly_laid_capture.py',
                           'finalization': 'pending_source_derived_implementation'}}


def write():
    cases = []
    for case in CASES:
        variants = {}
        for candidate in KNOBS:
            folder = PACKAGE / 'draft-newly-laid-candidates' / case / candidate
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / 'construction.json'
            if path.exists():
                raise ValueError('Retain previous newly laid construction: ' + str(path))
            path.write_text(json.dumps(build(case, candidate), indent=2,
                                       sort_keys=True) + '\n')
            variants[candidate] = {'construction': str(path.relative_to(PACKAGE)),
                                   'construction_sha256': sha(path)}
        candidates = [dict(id=name, **variants[name], **FALLBACKS[name])
                      for name in FALLBACKS]
        cases.append({'case_id': ASSIGNMENT + '__' + case, 'kind': 'delivery',
                      **variants['primary'], 'candidates': candidates,
                      'candidate_risk': {'status': 'physical',
                                         'reason': 'Native body tracking and original warning/surface pixels remain unverified'},
                      'candidate_offline_status': 'pending',
                      'finalizer_status': 'not_yet_constructed'})
    runtime = PACKAGE.parents[1] / 'runtime/pipeline/SOURCE-MANIFEST.json'
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': ASSIGNMENT,
                'status': 'draft_newly_laid_capture_only_not_delivery_ready',
                'runtime_manifest_sha256': sha(runtime),
                'cases': cases}
    path = PACKAGE / 'draft-newly-laid-capture-manifest.json'
    if path.exists():
        raise ValueError('Retain previous newly laid manifest')
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return path


if __name__ == '__main__':
    print(write())
