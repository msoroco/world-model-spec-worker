"""Bind exact C179799 cases, source requirements, measurements, and CPU probes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
SUFFIXES = ('condition_a', 'condition_b')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def main():
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    ids = [ASSIGNMENT+'__selected_ce719cfa__'+suffix for suffix in SUFFIXES]
    for disposition in plan['requirement_dispositions']:
        disposition['status'] = 'selected_required'
        disposition['case_ids'] = ids
        disposition['evidence_or_gap'] = (
            'Both exact selected Native bundles and 600-frame CPU fixtures exercise the cited source topic; '
            'original physical realization, public-access status and willful or wanton mental state remain unverified.')
    for case in plan['cases']:
        case['target_type'] = 'delivery'
        case['planning_status'] = 'selected_cpu_preparing'
        case['gap_ids'] = ['original-person-encounter']
        case['physical_risk'] = {
            'status': 'physical',
            'reason': 'A roadside walker outside the driving lane may fall, disappear, or leave a camera view in original CARLA.',
            'fallback_trigger': 'Original walker pose or four-camera body-visibility audit fails',
            'not_a_legal_threshold': True}
    plan['evidence_review'] = {
        'method': 'Reviewed frozen local_snapshot full-train membership and exact witness; no accepted recording in supplied inventory',
        'reviewer': 'worker CPU preparation', 'facts': [],
        'gaps': [{'id': 'original-person-encounter',
                  'requirement': 'NRS-484B-653-1a paved-route driving with roadside-worker interaction',
                  'source': 'inputs/'+ASSIGNMENT+'/assignment.json',
                  'why_existing_insufficient': 'Frozen full-train membership is empty; no accepted original source demonstrates the selected scope.'}]}
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'paved road, vehicle and roadside worker', 'interval': 'all 600 frames'},
            {'view': 'approach', 'subject': 'vehicle and worker approach', 'interval': 'all 600 frames'},
            {'view': 'reference_corner', 'subject': 'worker route-side separation and property', 'interval': 'all 600 frames'},
            {'view': 'driver_reference', 'subject': 'driver-forward road and sight line', 'interval': 'all 600 frames'}],
        'limitation': 'Actual person body visibility and highway/public-access classification need original independent review.'}
    for observation in plan['observations']:
        observation['status'] = 'source_bound_native_and_saved_cpu_preparing'
    for name, mapping in plan['source_observation_mapping'].items():
        mapping['evidence'] = ('Original Native actor/frame-map/context sources plus saved-only derived channel; '
                               'synthetic fixture tests software joins only; no legal or physical inference.')
        mapping['channels'] = [name]
    plan['comparisons'][0]['status'] = 'cpu_construction_preparing'
    plan['comparisons'][0]['audit_gap'] = 'Independent comparison audit and original physical encounters still pending.'
    plan['readiness'] = 'cpu_construction_preparing'
    write(plan_path, plan)
    recording = json.loads((HERE/'config.json').read_text())['recording_description']
    proposals = {'cell_id': 'C179799', 'actor': 'motor_vehicle_driver',
                 'status': 'draft', 'sweep_specs': [], 'sweeps_expanded': True,
                 'cases': []}
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': sha(REPO/'runtime/SOURCE-MANIFEST.json'),
                'cases': []}
    for suffix, case_id in zip(SUFFIXES, ids):
        config = json.loads((HERE/'cases'/suffix/'config.json').read_text())
        proposals['cases'].append({
            'case_id': case_id, 'target_law_id': 'NRS-484B-653-1a',
            'target_type': 'delivery',
            'rationale': 'Controlled earlier versus later original driver response to the same distinct roadside worker; no legal result.',
            'variable_assignments': {'observable_driving_interaction': {
                'kind': 'vehicle_control', 'value': config['interaction_mode'],
                'unit': 'engineering mode', 'source': 'selected exact Native config'}},
            'unresolved_judgment_calls': [
                'Highway/public access, role, complete visibility and willful or wanton mental state require independent review.'],
            'paired_probe_id': ASSIGNMENT+'__selected_ce719cfa__comparison',
            'deliberate_differences': ['observable_driving_interaction'],
            'recording_description': recording})
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
                    'requirements': [
                        {'disposition_index': 0, 'requirement': plan['requirement_dispositions'][0]['requirement'],
                         'source': plan['requirement_dispositions'][0]['source'],
                         'output_key': 'intro', 'method': 'measure_intro',
                         'value_type': 'object', 'kind': 'sourced_context',
                         'inputs': ['native-person-interaction.jsonl', 'original-context-packet.json']},
                        {'disposition_index': 1, 'requirement': plan['requirement_dispositions'][1]['requirement'],
                         'source': plan['requirement_dispositions'][1]['source'],
                         'output_key': 'clause', 'method': 'measure_clause',
                         'value_type': 'object', 'kind': 'measured',
                         'inputs': ['native-person-interaction.jsonl', 'original-context-packet.json',
                                    'video_frames.jsonl', 'native-road-readback.json']},
                        {'disposition_index': 2, 'requirement': plan['requirement_dispositions'][2]['requirement'],
                         'source': plan['requirement_dispositions'][2]['source'],
                         'output_key': 'scope', 'method': 'measure_scope',
                         'value_type': 'object', 'kind': 'sourced_context',
                         'inputs': ['native-person-interaction.jsonl', 'original-context-packet.json']}],
                    'negative': {'remove': ['original-context-packet.json'],
                                 'error_contains': 'Missing required source: original-context-packet.json'}}
        write(HERE/'cases'/suffix/'measurement-contract.json', contract)
        construction_path = HERE/'cases'/suffix/'construction.json'
        manifest['cases'].append({
            'case_id': case_id, 'kind': 'delivery',
            'construction': 'cases/'+suffix+'/construction.json',
            'construction_sha256': sha(construction_path),
            'measurement_contract': 'cases/'+suffix+'/measurement-contract.json',
            'measurement_procedure': {'entrypoint': 'finalize.py',
                                      'output_schema': 'c179799-saved-interaction-analysis-v1'},
            'fixture_recipe': 'work/'+ASSIGNMENT+'/cases/'+suffix+'/fixture-recipe.json',
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
            'candidate_risk': {'status': 'physical',
                               'reason': 'Walker may fail to remain visible or stable outside the driving lane.'},
            'candidates': [{
                'id': 'fallback1',
                'construction': 'cases/'+suffix+'/construction-fallback1.json',
                'construction_sha256': sha(HERE/'cases'/suffix/'construction-fallback1.json'),
                'trigger': {'source': 'original Native actor/body and four-camera audit',
                            'metric': 'worker visibility or stable roadside pose',
                            'failure_condition': 'worker missing from full encounter or source pixels'},
                'changed_knobs': ['worker_y_m shifted from -5.2 m to -4.8 m while still outside lane']}]})
    write(HERE/'proposals/cases.json', proposals)
    write(HERE/'selected-probe-manifest.json', manifest)
    print(json.dumps({'cases': ids, 'runtime_manifest_sha256': manifest['runtime_manifest_sha256']}))


if __name__ == '__main__':
    main()
