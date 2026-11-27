"""Bind eight source-limited rail exception cases to the public CPU probe."""

import hashlib
import json
from pathlib import Path

from rail_exception_context import BRANCHES


PACKAGE = Path(__file__).resolve().parents[1]
NATIVE = PACKAGE / 'native'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    plan = json.loads((PACKAGE / 'case-plan.json').read_text())
    manifest_path = PACKAGE / 'public-probe-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    kept = [entry for entry in manifest['cases']
            if entry['case_id'].split('__')[-1] not in
            {name + '_' + str(i) for name in BRANCHES for i in (1, 2)}]
    for branch in BRANCHES:
        for index in (1, 2):
            suffix = branch + '_' + str(index)
            case_id = PACKAGE.name + '__' + suffix
            primary = NATIVE / suffix / 'construction.json'
            fallback = NATIVE / suffix / 'fallback1/construction.json'
            if not primary.is_file() or not fallback.is_file():
                raise ValueError('Build exact exception construction first: ' + suffix)
            requirements = [
                {'disposition_index': 0,
                 'requirement': plan['requirement_dispositions'][0]['requirement'],
                 'source': plan['requirement_dispositions'][0]['source'],
                 'output_key': 'exception_context',
                 'method': 'sealed_exception_request_source_review',
                 'value_type': 'object', 'kind': 'sourced_context',
                 'inputs': ['exception-context.json', 'capture-seal.json']},
                {'disposition_index': 1,
                 'requirement': plan['requirement_dispositions'][1]['requirement'],
                 'source': plan['requirement_dispositions'][1]['source'],
                 'output_key': 'nearest_rail_gap',
                 'method': 'original_native_source_contract',
                 'value_type': 'object', 'kind': 'measured',
                 'inputs': ['original-rail-survey.json', 'original-native-rows.jsonl',
                            'video_frames.jsonl', 'capture-seal.json']}]
            write(PACKAGE / ('measurement-' + suffix + '.json'),
                  {'format': 'worker-measurement-contract', 'case_id': case_id,
                   'requirements': requirements,
                   'negative': {'remove': ['exception-context.json'],
                                'error_contains': 'Missing required source: exception-context.json'}})
            kept.append({'case_id': case_id, 'kind': 'delivery',
                'construction': str(primary.relative_to(PACKAGE)),
                'construction_sha256': sha(primary),
                'measurement_contract': 'measurement-' + suffix + '.json',
                'measurement_procedure': {'entrypoint': 'rail_exception_finalize.py',
                                          'output_schema': 'worker-analysis-report'},
                'fixture_recipe': 'work/' + PACKAGE.name + '/selected-recipe-' + suffix + '.json',
                'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
                'candidate_risk': {'status': 'physical',
                    'reason': 'Original approach may overshoot or fail to settle; slower approach preserves requested context and gap.'},
                'candidates': [{'id': 'fallback1',
                    'construction': str(fallback.relative_to(PACKAGE)),
                    'construction_sha256': sha(fallback),
                    'trigger': {'source': 'original Native speed and pose',
                        'metric': 'approach overshoot or missing rest',
                        'failure_condition': 'vehicle passes requested rail target or fails to rest'},
                    'changed_knobs': ['approach_distance_m: 10.0 -> 7.0',
                                      'approach_speed_cap_mps: 1.5 -> 1.0']} ]})
    manifest['cases'] = kept
    manifest['status'] = 'partial_public_probe_only'
    write(manifest_path, manifest)
    print(json.dumps({'cases': len(kept), 'exception_cases': 8}))


if __name__ == '__main__':
    main()
