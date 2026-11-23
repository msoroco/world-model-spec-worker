"""Assemble one exact eight-case draft from current source-hashed bundles.

The output is deliberately not the canonical execution-manifest.json until
all selected CPU proofs and independent delivery audits pass.
"""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
GROUPS = ('reference', 'contrast', 'conflict', 'clear', 'near_lead',
          'absent_lead', 'device-direction', 'officer-direction')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    runtime_sha = digest(REPO / 'runtime/pipeline/SOURCE-MANIFEST.json')
    plan = json.loads((HERE / 'case-plan.json').read_text())
    planned = {row['case_id'] for row in plan['cases']}
    cases = []
    sources = {}
    for group in GROUPS:
        path = HERE / ('draft-' + group + '-fallback-manifest.json')
        source = json.loads(path.read_text())
        if source['assignment_id'] != HERE.name or len(source['cases']) != 1 or \
                source['runtime_manifest_sha256'] != runtime_sha:
            raise ValueError('Group identity/runtime differs: ' + group)
        entry = source['cases'][0]
        if entry['case_id'] not in planned or len(entry['candidates']) != 3:
            raise ValueError('Group case or fallbacks differ: ' + group)
        if {candidate['id'] for candidate in entry['candidates']} != \
                {'fallback1', 'fallback2', 'fallback3'}:
            raise ValueError('Group candidate IDs differ: ' + group)
        for candidate in [entry] + entry['candidates']:
            construction = HERE / candidate['construction']
            if digest(construction) != candidate['construction_sha256']:
                raise ValueError('Construction changed: ' + group)
        recipe = REPO / entry['fixture_recipe']
        contract = HERE / entry['measurement_contract']
        if not recipe.is_file() or not contract.is_file():
            raise ValueError('Missing exact fixture/measurement contract: ' + group)
        selected = dict(entry)
        selected['kind'] = 'delivery'
        selected['preparation_status'] = 'draft_combined_manifest_requires_reproof'
        selected['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                      'host_env_var': 'CARLA_HOST',
                                      'port_env_var': 'CARLA_PORT'}
        cases.append(selected)
        sources[group] = {'manifest_sha256': digest(path),
                          'fixture_recipe_sha256': digest(recipe),
                          'measurement_contract_sha256': digest(contract)}
    if len({entry['case_id'] for entry in cases}) != len(GROUPS):
        raise ValueError('Combined case set differs')
    return {'format': 'worker-execution-manifest',
            'assignment_id': HERE.name,
            'runtime_manifest_sha256': runtime_sha,
            'status': 'draft_combined_requires_current_manifest_cpu_proofs',
            'cases': cases,
            'source_bindings': sources}


if __name__ == '__main__':
    path = HERE / 'current-combined-delivery-draft.json'
    path.write_text(json.dumps(build(), indent=2, sort_keys=True) + '\n')
