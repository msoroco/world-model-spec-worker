"""Bind two exact approach cases and risk variants to current runtime sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CHANNELS = ('drv.responding_emergency', 'drv.approaching', 'rel.visible',
            'drv.stopped', 'rel.bearing', 'kin.velocity', 'dev.human_direction')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    draft = json.loads((HERE / 'draft-approach-manifest.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': HERE.name, 'status': 'delivery_prepared',
                'runtime_manifest_sha256': digest(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'original_native_observed': False, 'delivery_ready': False,
                'cases': []}
    recording = {'channels': [
        {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
         'method': 'Original Native pose, emergency context and camera frame join',
         'time_window': 'all 600 frames', 'reference_frame': 'original Native frame',
         'uncertainty': '50 ms frame bracket; visual and legal qualification separate'}
        for name in CHANNELS],
        'context_inputs': [],
        'limitations': ['Synthetic fixture proves software path only',
                        'Original authorization, qualifying lamp pixels, visibility and officer direction require review']}
    finalizer = (HERE / 'native/finalize.py').read_text()
    for case in draft['cases']:
        suffix = case['case_id'].removeprefix(HERE.name + '__')
        item = {'case_id': case['case_id'], 'kind': 'delivery', 'id': 'primary',
                'candidate_risk': case['candidate_risk'], 'candidates': [],
                'measurement_procedure': {'entrypoint': 'finalize.py',
                                          'output_schema': 'c405647-2f-saved-analysis-v1'},
                'measurement_contract': f'current-contracts/{suffix}.json',
                'fixture_recipe': f'work/{HERE.name}/current-{suffix}-recipe.json',
                'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}}
        contract = {'format': 'worker-measurement-contract',
                    'requirements': [{'disposition_index': 0,
                                      'requirement': plan['requirement_dispositions'][0]['requirement'],
                                      'source': plan['requirement_dispositions'][0]['source'],
                                      'output_key': 'approach_response',
                                      'method': 'measure_approach_response',
                                      'value_type': 'object', 'kind': 'measured',
                                      'inputs': ['video_frames.jsonl', 'vehicle_poses.jsonl',
                                                 'emergency_context.json']}],
                    'negative': {'remove': ['emergency_context.json'],
                                 'error_contains': 'Missing required source: emergency_context.json'}}
        write(HERE / item['measurement_contract'], contract)
        for candidate in ('primary', 'fallback1', 'fallback2'):
            old = case if candidate == 'primary' else next(
                c for c in case['candidates'] if c['id'] == candidate)
            bundle = json.loads((HERE / old['construction']).read_text())
            bundle['files'].append({'path': 'finalize.py', 'content': finalizer})
            bundle['recording_description'] = recording
            bundle['measurement_plan'] = {
                'source': 'vehicle_poses.jsonl, video_frames.jsonl, emergency_context.json',
                'method': 'Join original two-phase opposing actor motion and reviewed context; preserve subsection 1 and 607 source boundaries',
                'legal_verdict': None}
            bundle['static_checks'] = ['exact law, cell, actor and 600-frame identity',
                                       'opposing lane geometry, four camera profile and original source requirements']
            bundle['termination_rules'] = ['capture 600 joined Native frames or fail without acceptance']
            bundle['mechanisms'] = ['opposing Native actor pose controller',
                                    'four original FFV1 camera streams',
                                    'source-bound saved two-phase approach measurement']
            bundle['status'] = 'selected_cpu_delivery_preparation'
            path = HERE / 'current-bundles' / suffix / candidate / 'construction.json'
            write(path, bundle)
            bind = {'construction': path.relative_to(HERE).as_posix(),
                    'construction_sha256': digest(path)}
            if candidate == 'primary':
                item.update(bind)
            else:
                trigger = ({'source': 'original vehicle_poses.jsonl',
                            'metric': 'emergency closing distance in full 600-frame span',
                            'failure_condition': 'Original emergency approach remains outside camera window'}
                           if candidate == 'fallback1' else
                           {'source': 'original overview.mkv and vehicle_poses.jsonl',
                            'metric': 'subject whole-body visibility',
                            'failure_condition': 'Original subject body overlaps lane edge or leaves frame'})
                item['candidates'].append({'id': candidate, **bind,
                                           'trigger': trigger,
                                           'changed_knobs': ['requested_subsequent_emergency_speed_mps']
                                           if candidate == 'fallback1' else
                                           ['requested_ego_lane_center_y_m']})
        manifest['cases'].append(item)
    write(HERE / 'current-execution-manifest.json', manifest)
    primary = json.loads((HERE / manifest['cases'][0]['construction']).read_text())
    write(HERE / 'construction.json', primary)
    for name in ('runner.py', 'config.json'):
        target = next(row['content'] for row in primary['files'] if row['path'] == name)
        (HERE / name).write_text(target)
    print(json.dumps({'cases': len(manifest['cases']), 'candidates': 6,
                      'manifest_sha256': digest(HERE / 'current-execution-manifest.json')}))


if __name__ == '__main__':
    main()
