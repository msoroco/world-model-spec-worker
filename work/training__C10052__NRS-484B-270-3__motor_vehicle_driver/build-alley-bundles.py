"""Materialize four exact unselected exception-A alley CPU bundles."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
NATIVE = HERE/'native'
NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')
SOURCES = ('alley_geometry.py', 'alley_engineering.py', 'geometry.py',
           'controller.py', 'cameras.py', 'measure_facility.py',
           'measure_alley_transition.py', 'measure_alley_triggers.py',
           'measure_entry.py', 'measure_park_act.py', 'finalize.py', 'finalize_alley.py')
RUNTIME_MANIFEST = '391baee19ccece687c5632aa2cc64ba3b958c8b492045b30e4bfc4caa131c235'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    sys.path.insert(0, str(NATIVE))
    from alley_engineering import TRIGGERS
    template = json.loads((NATIVE/'alley-native-config.json').read_text())
    case_id = template['case_id']
    source = {name: (NATIVE/name).read_text() for name in SOURCES}
    source['runner.py'] = (NATIVE/'alley_runner.py').read_text()
    tests = (HERE/'tests/test_alley_bundle.py').read_text()
    entry = {'case_id': case_id, 'kind': 'draft_not_selected',
             'candidate_risk': {'status': 'physical',
                'reason': 'Runway, turn dynamics, camera visibility and statutory exception observations need original Native evidence'},
             'measurement_procedure': {'entrypoint': 'finalize_alley.py',
                 'output_schema': 'c10052-alley-saved-diagnostic-v1'},
             'measurement_contract': 'draft-alley-measurement-contract.json',
             'candidates': []}
    for ident in NAMES:
        config = dict(template)
        config.update(candidate_id=ident, selected_case_id=case_id,
                      supported_case_ids=[case_id])
        config['cameras'] = [{'name': c['name'], 'width': c['width'],
            'height': c['height'], 'pose_strategy': 'candidate-specific Native mount in cameras.py',
            'fov_deg': '90/105 according to measured framing fallback'}
            for c in template['cameras']]
        config_text = json.dumps(config, indent=2)+'\n'
        files = [{'path': name, 'content': content} for name, content in source.items()]
        files += [{'path': 'config.json', 'content': config_text},
                  {'path': 'alley-native-config.json', 'content': config_text},
                  {'path': 'tests/test_bundle.py', 'content': tests}]
        construction = {'case_id': case_id, 'cell_id': 'C10052',
            'law_id': 'NRS-484B-270-3', 'actor': 'motor_vehicle_driver',
            'entrypoint': 'runner.py', 'files': files,
            'measurement_plan': {'method': 'source-bound moving facility entry before alley footprint with original Native body vertices',
                'status': 'synthetic_cpu_diagnostic_only'},
            'recording_description': config['recording_description'],
            'static_checks': ['authored alley map and continuous routes',
                'candidate-specific four-view runner preflight',
                'measured fallback source and distinct engineering changes'],
            'termination_rules': ['480 original frames', 'preserve failure on capture or restoration error'],
            'mechanisms': ['authored bicycle facility and alley connector',
                'observed-pose path controller', 'four synchronized original source cameras'],
            'status': 'unselected_cpu_draft'}
        relative = f'draft-alley-candidates/probe_c_alley_entry/{ident}/construction.json'
        path = HERE/relative
        write(path, construction)
        ref = {'id': ident, 'construction': relative, 'construction_sha256': sha(path)}
        if ident == 'primary':
            entry.update(ref)
        else:
            ref['trigger'] = {key: TRIGGERS[ident][key] for key in
                              ('source', 'metric', 'failure_condition')}
            ref['changed_knobs'] = TRIGGERS[ident]['changed_knobs']
            entry['candidates'].append(ref)
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
        'assignment_id': HERE.name, 'runtime_manifest_sha256': RUNTIME_MANIFEST,
        'status': 'draft_not_selected', 'cases': [entry]}
    write(HERE/'draft-alley-execution-manifest.json', manifest)
    return {'case_id': case_id, 'candidates': len(NAMES), 'status': manifest['status']}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
