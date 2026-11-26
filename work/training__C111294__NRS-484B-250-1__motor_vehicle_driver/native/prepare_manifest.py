"""Bind two selected entry-order cases and four engineering plans each."""
import json
from pathlib import Path
from build_selected import CASES, CANDIDATES, PACKAGE, REPO, build, put, sha


def main():
    batch = json.loads((REPO / 'batch.json').read_text())
    plan = json.loads((PACKAGE / 'case-plan.json').read_text())
    cases = []
    for suffix in CASES:
        built = {candidate: build(suffix, candidate) for candidate in CANDIDATES}
        cid = built['primary']['case_id']
        sources = ['actor-history.json', 'road-context.json',
            'video_frames.jsonl', 'trace.jsonl', 'crossing_history.jsonl',
            'capture/evidence.jsonl']
        keys = ('priority_entry', 'yield_action', 'device_exclusion',
                'opposite_turn_exclusion')
        requirements = [{'disposition_index': i,
            'requirement': disposition['requirement'],
            'source': disposition['source'], 'kind': 'measured',
            'method': 'measure_entry', 'output_key': keys[i],
            'value_type': 'object', 'inputs': sources}
            for i, disposition in enumerate(plan['requirement_dispositions'])]
        contract = {'format': 'worker-measurement-contract',
            'case_id': cid, 'status': 'selected_cpu_draft',
            'negative': {'remove': ['actor-history.json'],
                'error_contains': 'Missing required source: actor-history.json'},
            'requirements': requirements, 'legal_compliance': 'unassessed'}
        contract_path = PACKAGE / 'native' / f'{suffix}-measurement-contract.json'
        put(contract_path, contract)
        construction = json.loads((PACKAGE / built['primary']['construction']).read_text())
        entry = {'case_id': cid, 'kind': 'delivery',
            'construction': built['primary']['construction'],
            'construction_sha256': built['primary']['construction_sha256'],
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'measurement_contract': str(contract_path.relative_to(PACKAGE)),
            'fixture_recipe': 'work/' + PACKAGE.name + '/native/selected/' + suffix + '/primary/fixture-recipe.json',
            'recording_description': construction['recording_description'],
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
            'candidate_risk': {'status': 'physical',
                'reason': 'Crossroads spawn, other-vehicle timing, or camera visibility may fail on original CARLA'},
            'candidates': []}
        knobs = {'fallback1': ['ego requested speed 5.0 to 4.5 m/s'],
                 'fallback2': ['overview height 35 to 50 m'],
                 'fallback3': ['two-second ego stop before entry']}
        for candidate in CANDIDATES[1:]:
            entry['candidates'].append({'id': candidate,
                'construction': built[candidate]['construction'],
                'construction_sha256': built[candidate]['construction_sha256'],
                'trigger': {'source': 'original Native capture or pixel review',
                    'metric': 'spawn and measured source visibility or entry timing',
                    'failure_condition': 'vehicle spawn fails, entry order differs, or required camera subject absent'},
                'changed_knobs': knobs[candidate]})
        cases.append(entry)
    manifest = {'format': 'worker-execution-manifest',
        'assignment_id': PACKAGE.name, 'status': 'draft',
        'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
        'physical_acceptance_claimed': False, 'cases': cases}
    path = PACKAGE / 'draft-native-manifest.json'
    put(path, manifest)
    return {'cases': len(cases), 'candidate_constructions': len(cases)*4,
            'manifest_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
