"""Build exact unselected C10052 primary and three fallback constructions."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
NATIVE = HERE/'native'
ASSIGNMENT = HERE.name
NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')
RUNTIME_MANIFEST = '391baee19ccece687c5632aa2cc64ba3b958c8b492045b30e4bfc4caa131c235'
SOURCES = ('runner.py', 'geometry.py', 'controller.py', 'engineering.py',
           'cameras.py', 'measure_facility.py', 'measure_entry.py',
           'measure_park_act.py',
           'fallback_triggers.py', 'finalize.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n')


def build():
    sys.path.insert(0, str(NATIVE))
    from engineering import TRIGGERS
    plan = json.loads((HERE/'case-plan.json').read_text())
    template = json.loads((NATIVE/'config.json').read_text())
    shared = {name: (NATIVE/name).read_text() for name in SOURCES}
    test = (HERE/'tests/test_bundle.py').read_text()
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': RUNTIME_MANIFEST,
                'status': 'draft_not_selected', 'cases': []}
    for draft in plan['cases']:
        suffix = draft['case_id'].rsplit('__', 1)[-1]
        entry = {'case_id': draft['case_id'], 'kind': 'draft_not_selected',
                 'candidate_risk': {'status': 'physical',
                     'reason': 'Native bicycle designation, lateral route tracking, stop placement, exception observations and source framing require original evidence'},
                 'measurement_contract': f'draft-facility/{suffix}/measurement-contract.json',
                 'measurement_procedure': {'entrypoint': 'finalize.py',
                     'output_schema': 'c10052-synthetic-saved-occupancy-diagnostic-v1'},
                 'candidates': []}
        for candidate in NAMES:
            config = dict(template)
            config.update(case_id=draft['case_id'], case_suffix=suffix,
                          candidate_id=candidate, selected_case_id=draft['case_id'],
                          supported_case_ids=[draft['case_id']],
                          case={'case_id': draft['case_id']})
            config['cameras'] = [{'name': c['name'], 'width': c['width'],
                'height': c['height'], 'pose_strategy': 'candidate-specific Native mount in cameras.py',
                'fov_deg': '90/105 according to measured framing fallback'}
                for c in template['cameras']]
            files = [{'path': name, 'content': content} for name, content in shared.items()]
            files.append({'path': 'tests/test_bundle.py', 'content': test})
            files.append({'path': 'config.json', 'content': json.dumps(config, indent=2)+'\n'})
            construction = {'case_id': draft['case_id'], 'cell_id': 'C10052',
                'law_id': 'NRS-484B-270-3', 'actor': 'motor_vehicle_driver',
                'entrypoint': 'runner.py', 'files': files,
                'measurement_plan': {'method': 'original Native stationary full-body overlap with surveyed bicycle facility, with six separate unresolved exception fields',
                                     'status': 'prototype_not_runtime_compatible'},
                'recording_description': config['recording_description'],
                'static_checks': ['authored map and route continuity',
                    'controlled outside/inside stop setting', 'candidate parameter distinctness',
                    'source-bound body overlap and missing-exception-source negative'],
                'termination_rules': ['480 original frames',
                    'retain failure on capture or restoration error'],
                'mechanisms': ['authored alley and bicycle facility',
                    'observed-pose path controller', 'four synchronized lossless source cameras'],
                'status': 'unselected_cpu_draft'}
            relative = f'draft-candidates/{suffix}/{candidate}/construction.json'
            path = HERE/relative
            write(path, construction)
            ref = {'id': candidate, 'construction': relative,
                   'construction_sha256': sha(path)}
            if candidate == 'primary':
                entry.update(ref)
            else:
                trigger = TRIGGERS[candidate]
                ref.update(trigger={key: trigger[key] for key in
                           ('source', 'metric', 'failure_condition')},
                           changed_knobs=trigger['changed_knobs'])
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    write(HERE/'draft-execution-manifest.json', manifest)
    return {'cases': len(manifest['cases']),
            'candidates': sum(1+len(c['candidates']) for c in manifest['cases']),
            'status': manifest['status']}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
