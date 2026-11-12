"""Materialize four exact, unselected Walk sweep cases and risk alternatives."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from engineering import CANDIDATES, SWEEP_MARGINS_M, TRIGGERS, parameters

UPDATED = ('runner.py', 'engineering.py', 'test_native.py',
           'physical_walk_audit.py', 'finalize.py')


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cases = read(HERE / 'proposals/sweep-stage-candidate.json')
    swept = [c for c in cases['cases'] if c.get('target_type') == 'judgment_sweep']
    if len(swept) != 4:
        raise ValueError('Expected four fixed sweep cases')
    manifest = {'format': 'worker-unselected-sweep-candidates-v1',
                'assignment_id': HERE.name, 'status': 'unselected_cpu_construction',
                'runtime_manifest_sha256': hashlib.sha256(
                    (HERE.parents[1] / 'runtime/pipeline/SOURCE-MANIFEST.json').read_bytes()).hexdigest(),
                'case_stage_sha256': hashlib.sha256(
                    (HERE / 'proposals/sweep-stage-candidate.json').read_bytes()).hexdigest(),
                'cases': []}
    for case in swept:
        case_id = case['case_id']
        suffix = case_id.removeprefix(HERE.name + '__')
        if suffix not in SWEEP_MARGINS_M or case['sweep_point']['crosswalk_hold_margin_m'] != SWEEP_MARGINS_M[suffix]:
            raise ValueError('Sweep case differs from frozen controller grid')
        contract = read(HERE / 'draft-candidates/reference/measurement-contract.json')
        contract['case_id'] = case_id
        contract['sweep_observable'] = {
            'name': 'crosswalk_hold_margin_m', 'unit': 'm',
            'source': 'native_samples.jsonl',
            'method': 'first requested hold bus-front distance to marked crossing; full 480-row source required',
            'legal_verdict_claimed': False}
        contract_path = HERE / 'sweep-candidates' / suffix / 'measurement-contract.json'
        write(contract_path, contract)
        row = {'case_id': case_id, 'status': 'unselected_cpu_construction',
               'setpoint_margin_m': SWEEP_MARGINS_M[suffix],
               'measurement_contract': contract_path.relative_to(HERE).as_posix(),
               'measurement_procedure': {'entrypoint': 'finalize.py',
                                         'output_schema': 'c111256-saved-analysis-v1'},
               'fixture_recipe': (HERE / 'update028-sweep-recipe.json').relative_to(HERE.parents[1]).as_posix(),
               'candidate_risk': {'status': 'physical',
                                  'reason': 'Native bus stopping and original Walk pixel coverage require source review'},
               'candidates': []}
        for candidate in CANDIDATES:
            source = read(HERE / 'draft-candidates/reference' / candidate / 'construction.json')
            source['case_id'] = case_id
            source['recording_description'] = case['recording_description']
            source['status'] = 'unselected_cpu_sweep_construction'
            source['mechanisms'].append('fixed physical hold-margin sweep with saved body/control measurement')
            files = {item['path']: item for item in source['files']}
            for name in UPDATED:
                target = 'tests/test_native.py' if name == 'test_native.py' else name
                files[target]['content'] = (HERE / 'native' / name).read_text()
            files['physical_sweep.py'] = {'path': 'physical_sweep.py',
                                          'content': (HERE / 'native/physical_sweep.py').read_text()}
            config = json.loads(files['config.json']['content'])
            config.update(case_id=case_id, selected_case_id=case_id,
                          case_suffix=suffix, candidate_id=candidate,
                          knobs=parameters(suffix, candidate)['knobs'],
                          supported_case_ids=[case_id], case={'case_id': case_id},
                          recording_description=case['recording_description'])
            files['config.json']['content'] = json.dumps(config, indent=2) + '\n'
            source['files'] = list(files.values())
            path = HERE / 'sweep-candidates' / suffix / candidate / 'construction.json'
            digest = write(path, source)
            item = {'id': candidate, 'construction': path.relative_to(HERE).as_posix(),
                    'construction_sha256': digest,
                    'setpoint_margin_m': SWEEP_MARGINS_M[suffix]}
            if candidate == 'fallback2':
                item['changed_knobs'] = ['target_speed_mps']
            elif candidate == 'fallback1':
                item['changed_knobs'] = ['route_tracking_lookahead_m']
            elif candidate == 'fallback3':
                item['changed_knobs'] = ['overview_fov_deg']
            if candidate != 'primary':
                trigger = TRIGGERS[candidate]
                item['trigger'] = {'source': trigger['source'], 'metric': trigger['metric'],
                                   'failure_condition': f"{trigger['op']} {trigger['threshold']}"}
            if candidate == 'primary':
                row['construction'] = item['construction']
                row['construction_sha256'] = item['construction_sha256']
            else:
                row['candidates'].append(item)
        manifest['cases'].append(row)
    path = HERE / 'sweep-execution-candidate.json'
    digest = write(path, manifest)
    print(json.dumps({'cases': len(swept), 'candidate_bundles': sum(1+len(c['candidates']) for c in manifest['cases']),
                      'manifest_sha256': digest, 'selected': False}, sort_keys=True))


if __name__ == '__main__':
    main()
