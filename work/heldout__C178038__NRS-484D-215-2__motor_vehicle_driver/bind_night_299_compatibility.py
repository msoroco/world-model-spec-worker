"""Bind the first exact headlamp case to its measured source contract."""

from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASE = ASSIGNMENT + '__night_299_upper'
SOURCE = f'inputs/{ASSIGNMENT}/assignment.json'
REQUIREMENT = 'NRS 484D.215(2) following within 300 ft during NRS 484D.100 lighting times on traveled highway or adjacent shoulder requires a permissible non-uppermost distribution'


def checksum(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def bind():
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    plan['requirement_dispositions'] = [{
        'requirement': REQUIREMENT, 'source': SOURCE,
        'status': 'selected_required',
        'case_ids': [case['case_id'] for case in plan['cases']],
        'evidence_or_gap': 'No accepted original; body separation, beam bits, road context and civil-time premise require new source capture.'}]
    for case in plan['cases']:
        if case['case_id'] == CASE:
            case['status'] = 'construction_probe_software_proved'
    write(plan_path, plan)
    inputs = ['following_footprints.jsonl', 'headlamp_readbacks.jsonl',
              'lighting_context.json', 'video_frames.jsonl', 'trace.jsonl',
              'roadway_environment.jsonl']
    contract = {'format': 'worker-measurement-contract', 'case_id': CASE,
                'requirements': [{
                    'disposition_index': 0, 'requirement': REQUIREMENT,
                    'source': SOURCE, 'output_key': 'headlamp_following_observation',
                    'method': 'analyze', 'value_type': 'object', 'kind': 'measured',
                    'inputs': inputs}],
                'negative': {'remove': ['headlamp_readbacks.jsonl'],
                             'error_contains': 'Missing required source: headlamp_readbacks.jsonl'}}
    contract_rel = 'night-probes/night_299_upper-measurement-contract.json'
    write(HERE / contract_rel, contract)
    construction_rel = 'night-probes/night_299_upper-construction.json'
    recipe_rel = f'work/{ASSIGNMENT}/night-probes/night_299_upper-diagnostic-recipe.json'
    existing_manifest_path = HERE / 'night-299-execution-manifest.json'
    existing_entry = (json.loads(existing_manifest_path.read_text())['cases'][0]
                      if existing_manifest_path.exists() else {})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': checksum(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'cases': [{'case_id': CASE, 'kind': 'delivery',
                           'construction': construction_rel,
                           'construction_sha256': checksum(HERE / construction_rel),
                           'measurement_contract': contract_rel,
                           'measurement_procedure': {'entrypoint': 'headlamp_finalizer.py'},
                           'fixture_recipe': recipe_rel,
                           'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                              'host_env_var': 'CARLA_HOST',
                                              'port_env_var': 'CARLA_PORT'},
                           'candidate_risk': {'status': 'physical',
                                              'reason': 'Actual body gap or lamp readback may differ from requested setup.'},
                           'candidates': [],
                           'negative': {'log': 'night-probes/night_299_upper-compat-negative.log'},
                           'acquisition': {'headlamp_gap_ft': {
                               'entrypoint': 'headlamp_finalizer.py',
                               'method': 'recompute each frame from retained original Native body polygons',
                               'evidence': 'headlamp_source_capture.py records original actor bodies and light readbacks with Native frame identities; finalizer derives gap after capture.'}},
                           **({'compatibility': existing_entry['compatibility']}
                              if 'compatibility' in existing_entry else {})}]}
    write(HERE / 'night-299-execution-manifest.json', manifest)
    config = json.loads((HERE / 'night-probes/night_299_upper-config.json').read_text())
    proposal = {'format': 'scenario-coverage-cases', 'status': 'draft',
                'cell_id': 'C178038', 'actor': 'motor_vehicle_driver', 'sweep_specs': [],
                'cases': [{'case_id': CASE, 'target_law_id': 'NRS-484D-215-2',
                           'target_type': 'boundary_probe',
                           'rationale': REQUIREMENT,
                           'variable_assignments': {
                               'requested_gap_ft': {'kind': 'controller', 'value': 299},
                               'requested_uppermost_distribution': {'kind': 'controller', 'value': True},
                               'lighting_time_premise': {'kind': 'world_setup', 'value': True}},
                           'unresolved_judgment_calls': [
                               'Civil lighting-time applicability and permissible beam distribution require independent source review.'],
                           'recording_description': config['case']['recording_description']}]}
    write(HERE / 'proposals/cases.json', proposal)


if __name__ == '__main__':
    bind()
