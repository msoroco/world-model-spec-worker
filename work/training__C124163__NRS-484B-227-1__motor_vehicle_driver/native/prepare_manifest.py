"""Prepare exact two-case median-turn manifest and measurement contracts."""
import hashlib
import json
from pathlib import Path
from build_selected import build
from median_scene import CASES

PKG = Path(__file__).resolve().parents[1]
A = PKG.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch = json.loads(Path('batch.json').read_text())
    plan = json.loads((PKG/'case-plan.json').read_text())
    cases = []
    for suffix in CASES:
        primary = build(suffix)
        fallback = build(suffix, 'fallback1')
        cid = primary['case_id']
        construction = json.loads((PKG/primary['construction']).read_text())
        requirements = []
        keys = ('roadway_duty', 'divider_prohibition', 'turn_event',
                'opening_exception', 'authority_context')
        for index, disposition in enumerate(plan['requirement_dispositions']):
            if disposition['status'] == 'selected_required' and cid in disposition['case_ids']:
                requirements.append({'disposition_index': index,
                    'requirement': disposition['requirement'],
                    'source': disposition['source'], 'kind': 'measured',
                    'method': 'measure_reference', 'output_key': keys[index],
                    'value_type': 'object',
                    'inputs': ['median-context.json', 'native-median.jsonl',
                               'video_frames.jsonl']})
        contract = {'format': 'worker-measurement-contract',
            'case_id': cid, 'status': 'selected_cpu_draft',
            'negative': {'remove': ['median-context.json'],
                'error_contains': 'Missing required source: median-context.json'},
            'requirements': requirements,
            'source_cameras': ['overview', 'approach',
                               'reference_corner', 'driver_reference'],
            'legal_compliance': 'unassessed'}
        contract_path = PKG/'native'/f'{suffix}-measurement-contract.json'
        contract_path.write_text(json.dumps(contract, indent=2)+'\n')
        entry = {'case_id': cid, 'kind': 'delivery',
            'construction': primary['construction'],
            'construction_sha256': primary['construction_sha256'],
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'measurement_contract': str(contract_path.relative_to(PKG)),
            'fixture_recipe': str(Path('work')/A/'native'/f'diagnostic-{suffix}-fixture-recipe.json'),
            'recording_description': construction['recording_description'],
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
            'candidate_risk': {'status': 'physical',
                'reason': 'Median-route vehicle spawn may intersect authored road surface'},
            'candidates': [{'id': 'fallback1',
                'construction': fallback['construction'],
                'construction_sha256': fallback['construction_sha256'],
                'trigger': {'source': 'Native try_spawn_actor',
                    'metric': 'actor spawn result',
                    'failure_condition': 'spawn returns None'},
                'changed_knobs': ['spawn height from 1.5m to 1.8m']}]}
        cases.append(entry)
    manifest = {'format': 'worker-execution-manifest',
        'assignment_id': A, 'status': 'draft',
        'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
        'physical_acceptance_claimed': False, 'cases': cases}
    path = PKG/'draft-native-manifest.json'
    path.write_text(json.dumps(manifest, indent=2)+'\n')
    return {'cases': len(cases), 'candidates': 4,
            'manifest_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
