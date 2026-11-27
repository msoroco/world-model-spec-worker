"""Stage an exact B(3) CPU request while retaining source eligibility checks."""

import copy
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE_ID = HERE.name + '__mobility_device'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    source = next(item for item in plan['cases'] if item['case_id'].endswith('__emergency'))
    target = copy.deepcopy(source)
    target['case_id'] = CASE_ID
    target['physical_target'] = 'source-eligible mobility device within trail right-of-way'
    target['source_context_request']['exception_kind'] = 'mobility_device'
    if not any(item['case_id'] == CASE_ID for item in plan['cases']):
        plan['cases'].append(target)
    disposition = next(item for item in plan['requirement_dispositions']
                       if item['branch'] == 'mobility_device_exception')
    disposition['status'] = 'selected_required'
    disposition['case_ids'] = [HERE.name + '__all_present', CASE_ID]
    disposition['evidence_or_gap'] = (
        'Source-conditional CPU request only: a matching asset name and synthetic fixture '
        'do not establish device design, impaired-person use, frozen actor eligibility, '
        'physical realization, or legal outcome. Original records and independent '
        'review are required before local acceptance.')
    comparison = copy.deepcopy(next(item for item in plan['comparisons']
                                    if item['comparison_id'].endswith('__emergency')))
    comparison['comparison_id'] = CASE_ID
    comparison['case_ids'][1] = CASE_ID
    comparison['deliberate_differences'] = ['mobility_device_design_and_use']
    if not any(item['comparison_id'] == CASE_ID for item in plan['comparisons']):
        plan['comparisons'].append(comparison)
    plan['blockers'] = [item for item in plan['blockers']
                        if 'Selected exact cases' not in item and
                           'Mobility-device exception actor/asset eligibility' not in item]
    plan['unverified_physical_assumptions'].append(
        'The B(3) Native mobility-device blueprint and operator can satisfy the '
        'frozen motor_vehicle_driver identity only after original actor review.')
    write(plan_path, plan)

    draft = json.loads((HERE / 'draft-exact/mobility_device/primary/construction.json').read_text())
    draft['status'] = 'selected_source_conditional_cpu_request'
    for item in draft['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config['status'] = 'selected_source_conditional_cpu_request'
            item['content'] = json.dumps(config, indent=2) + '\n'
        elif item['path'] == 'measurement-contract.json':
            (HERE / 'measurement-mobility_device.json').write_text(item['content'])
    primary = HERE / 'draft-exact/mobility_device/selected/construction.json'
    write(primary, draft)
    fallback = copy.deepcopy(draft)
    fallback['status'] = 'selected_source_conditional_cpu_fallback'
    for item in fallback['files']:
        if item['path'] == 'runner.py':
            old = 'for y in (-4.0, 4.0):'
            if item['content'].count(old) != 1:
                raise ValueError('Primary barrier setup changed')
            item['content'] = item['content'].replace(old, 'for y in (-5.0, 5.0):')
        elif item['path'] == 'config.json':
            config = json.loads(item['content'])
            config['candidate_id'] = 'fallback1'
            item['content'] = json.dumps(config, indent=2) + '\n'
    secondary = HERE / 'draft-exact/mobility_device/fallback1/construction.json'
    write(secondary, fallback)
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = {
        'case_id': CASE_ID, 'kind': 'delivery',
        'construction': str(primary.relative_to(HERE)),
        'construction_sha256': sha(primary),
        'measurement_contract': 'measurement-mobility_device.json',
        'fixture_recipe': 'work/' + HERE.name + '/diagnostic-recipe-mobility_device.json',
        'candidate_risk': {'status': 'physical',
                           'reason': 'Original mobility-device asset, actor eligibility and barrier passage require independent review'},
        'candidates': [{
            'id': 'fallback1', 'construction': str(secondary.relative_to(HERE)),
            'construction_sha256': sha(secondary),
            'trigger': {'source': 'original Native trail-inventory.json and vehicle-poses.jsonl',
                        'metric': 'barrier_clear_gap_m minus subject width and observed passage',
                        'failure_condition': 'primary opening lacks positive Native body clearance or passage fails'},
            'changed_knobs': ['barrier lateral centers move from -4/+4 m to -5/+5 m; subject, route, context and camera plan stay fixed'],
        }],
        'measurement_procedure': {'entrypoint': 'finalize_trail.py'},
        'preparation_status': 'incomplete',
        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                           'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
    }
    if not any(item['case_id'] == CASE_ID for item in manifest['cases']):
        manifest['cases'].append(entry)
    write(manifest_path, manifest)
    print(json.dumps({'case_id': CASE_ID, 'primary_sha256': sha(primary),
                      'fallback_sha256': sha(secondary), 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
