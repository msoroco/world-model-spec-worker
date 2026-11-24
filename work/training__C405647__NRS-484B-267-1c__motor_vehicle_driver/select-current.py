"""Bind six exact branch cases and eighteen policies to current CPU sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
CASES = ('probe_a', 'probe_b', 'exception_1_1', 'exception_1_2', 'official_1', 'official_2')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = json.loads((HERE / 'draft-native-manifest.json').read_text())
    source['format'] = 'worker-execution-manifest'
    source['status'] = 'delivery_prepared'
    source['runtime_manifest_sha256'] = sha(ROOT / 'runtime/SOURCE-MANIFEST.json')
    source['delivery_ready'] = False
    source['original_native_observed'] = False
    plan = json.loads((HERE / 'case-plan.json').read_text())
    descriptions = {'probe_a': (0, 'wait_until_passed', 'measure_wait'),
                    'probe_b': (0, 'wait_until_passed', 'measure_wait'),
                    'exception_1_1': (1, 'officer_direction_exception', 'measure_officer'),
                    'exception_1_2': (1, 'officer_direction_exception', 'measure_officer'),
                    'official_1': (2, 'official_vehicle_wait', 'measure_official'),
                    'official_2': (2, 'official_vehicle_wait', 'measure_official')}
    finalizer = (HERE / 'native/finalize.py').read_text()
    for case in source['cases']:
        suffix = case['case_id'].removeprefix(AID + '__')
        index, output_key, method = descriptions[suffix]
        case['kind'] = 'delivery'
        case['id'] = 'primary'
        case['measurement_procedure'] = {'entrypoint': 'finalize.py',
                                         'output_schema': 'c405647-1c-saved-analysis-v1'}
        contract = {'format': 'worker-measurement-contract',
                    'requirements': [{'disposition_index': index,
                                      'requirement': plan['requirement_dispositions'][index]['requirement'],
                                      'source': plan['requirement_dispositions'][index]['source'],
                                      'output_key': output_key, 'method': method,
                                      'value_type': 'object', 'kind': 'measured',
                                      'inputs': ['context-scope.json', 'actor-frames.jsonl']}],
                    'negative': {'remove': ['context-scope.json'],
                                 'error_contains': 'Missing required source: context-scope.json'}}
        target_contract = HERE / 'current-contracts' / (suffix + '.json')
        target_contract.parent.mkdir(parents=True, exist_ok=True)
        target_contract.write_text(json.dumps(contract, indent=2) + '\n')
        case['measurement_contract'] = target_contract.relative_to(HERE).as_posix()
        case['fixture_recipe'] = (HERE.relative_to(ROOT) /
                                  f'current-{suffix}-recipe.json').as_posix()
        case['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                  'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        for fallback in case['candidates']:
            fallback['trigger'] = {'source': 'original Native observed-actors.jsonl',
                                   'metric': 'first_whole_body_passage_frame' if fallback['id'] == 'fallback1'
                                             else 'original overview camera full-body visibility',
                                   'failure_condition': 'Primary source-bound whole-body passage is outside the 600-frame capture window'
                                                        if fallback['id'] == 'fallback1' else
                                                        'Original overview frames do not show both complete bodies around passage'}
            fallback['changed_knobs'] = ['approach_initial_position_and_speed'] if fallback['id'] == 'fallback1' else ['subject_lateral_offset_m']
        for item in [case] + case['candidates']:
            construction = json.loads((HERE / item['construction']).read_text())
            construction['files'].append({'path': 'finalize.py', 'content': finalizer})
            template = construction['recording_description']['channels'][0]
            for name in ('rel.same_direction', 'rel.surface_gap'):
                construction['recording_description']['channels'].append({**template, 'name': name})
            construction['recording_description'] = {
                'channels': construction['recording_description']['channels'],
                'context_inputs': [],
                'limitations': ['Synthetic fixture cannot establish physical passage or legal outcome',
                                'Original authority, lamp and officer facts require independent review']}
            construction['status'] = 'selected_cpu_delivery_preparation'
            target = HERE / 'current-bundles' / suffix / item['id'] / 'construction.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(construction, indent=2) + '\n')
            item['construction'] = target.relative_to(HERE).as_posix()
            item['construction_sha256'] = sha(target)
    out = HERE / 'current-execution-manifest.json'
    out.write_text(json.dumps(source, indent=2) + '\n')
    print(json.dumps({'cases': len(source['cases']),
                      'candidates': sum(1 + len(x['candidates']) for x in source['cases']),
                      'manifest_sha256': sha(out)}))


if __name__ == '__main__':
    main()
