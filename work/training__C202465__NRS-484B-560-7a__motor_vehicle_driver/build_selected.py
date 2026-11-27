"""Materialize six exact, source-gated railroad-crossing Native requests."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
VARIANTS = ('space_clear', 'space_short', 'grade_clear', 'grade_deficit',
            'trailing_exact', 'trailing_just_short')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHANNELS = ('st.railway_crossing', 'drv.crossing_line', 'drv.cleared_line',
            'kin.extent', 'drv.stopped', 'rel.surface_gap', 'drv.following',
            'st.grade', 'kin.velocity')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')


def build():
    description = {'channels': [
        {'name': channel, 'unit': 'structured', 'sampling_rate_hz': 20,
         'time_window': '600 original Native frames',
         'method': 'joined original vehicle, rail-review and camera sources',
         'reference_frame': 'Native frame and independently reviewed crossing',
         'uncertainty': '50 ms cadence; physical stop cause and law outcome require independent review'}
        for channel in CHANNELS], 'context_inputs': [],
        'limitations': ['Requested target and road metadata alone do not establish a stop cause, grounding, or legal verdict.']}
    entries = []
    for suffix in VARIANTS:
        case_id = AID + '__' + suffix
        contract = f'selected-measurements/{suffix}/measurement-contract.json'
        write(HERE / contract, {'format': 'worker-measurement-contract',
            'case_id': case_id, 'requirements': [
                {'disposition_index': 0, 'requirement': 'NRS-484B-560-7a',
                 'source': 'NRS 484B.560(7)(a); with 484B.560(8)', 'output_key': 'opposite_space',
                 'method': 'measure_opposite_space', 'value_type': 'object',
                 'kind': 'measured', 'inputs': ['road.xodr',
                     'rail-review/opposite-space.json', 'rail-review/opposite-space.source.txt',
                     'rail-actors.jsonl', 'video_frames.jsonl']},
                {'disposition_index': 1, 'requirement': 'NRS-484B-560-7a',
                 'source': 'NRS 484B.560(7)(a); with 484B.560(8)', 'output_key': 'undercarriage',
                 'method': 'measure_undercarriage', 'value_type': 'object',
                 'kind': 'measured', 'inputs': ['road.xodr',
                     'rail-review/undercarriage-grade.json',
                     'rail-review/undercarriage-grade.source.txt',
                     'vehicle-extent.json', 'rail-actors.jsonl']},
                {'disposition_index': 2, 'requirement': 'NRS-484B-560-7a',
                 'source': 'NRS 484B.560(7)(a); with 484B.560(8)', 'output_key': 'complete_crossing',
                 'method': 'measure_complete_crossing', 'value_type': 'object',
                 'kind': 'measured', 'inputs': ['rail-review/rail-geometry.json',
                     'rail-review/rail-geometry.source.txt', 'vehicle-extent.json',
                     'rail-actors.jsonl', 'video_frames.jsonl']}],
            'negative': {'remove': ['rail-review/rail-geometry.json'],
                         'error_contains': 'Missing required source: rail-review/rail-geometry.json'}})
        candidates = []
        for candidate, gain in (('primary', 4.0), ('fallback1', 5.0)):
            config = {'case_id': case_id, 'selected_case_id': case_id,
                      'supported_case_ids': [AID + '__' + s for s in VARIANTS],
                      'candidate_id': candidate, 'law_id': 'NRS-484B-560-7a',
                      'cell_id': 'C202465', 'actor': 'motor_vehicle_driver',
                      'rate_hz': 20, 'duration_s': 30, 'duration_frames': 600,
                      'brake_gain': gain, 'required_atoms': [], 'source_packets': [],
                      'source_actor_ids': ['ego', 'queue'],
                      'case': {'case_id': case_id, 'recording_description': description},
                      'cameras': [{'name': name, 'fps': 20,
                                   'width': 1920 if name == 'overview' else 1280,
                                   'height': 1080 if name == 'overview' else 720,
                                   'fov_deg': 85,
                                   'pose_strategy': 'reviewed fixed crossing and body views'}
                                  for name in CAMERAS],
                      'recording_description': description,
                      'physical_verified': False, 'legal_verdict': None}
            files = [{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'}]
            for name in ('runner.py', 'controller.py', 'source_review.py',
                         'measure_rail.py', 'finalize.py'):
                files.append({'path': name, 'content': (HERE / 'native' / name).read_text()})
            files.append({'path': 'tests/test_native.py',
                          'content': (HERE / 'native/tests/test_native.py').read_text()})
            construction = {'format': 'worker-inline-construction', 'case_id': case_id,
                            'cell_id': 'C202465', 'actor': 'motor_vehicle_driver',
                            'entrypoint': 'runner.py', 'files': files,
                            'recording_description': description,
                            'measurement_plan': '600-frame original body and queue trace joined to reviewed at-grade rails, opposite-side space, grade and four cameras; stop cause remains independently reviewed.',
                            'static_checks': ['exact law/cell/actor', '600 frames at 20 Hz',
                                              'four source cameras', 'reviewed original railroad source before mutation',
                                              'no legal or physical outcome preclaim'],
                            'termination_rules': ['600 original frames or explicit Native failure'],
                            'mechanisms': ['source-reviewed at-grade rail capture',
                                           'original body and queue actor trace',
                                           'source-hashed road and rail observations'],
                            'status': 'selected_cpu_source_dependency'}
            rel = (f'native/{suffix}/construction.json' if candidate == 'primary'
                   else f'fallbacks/{suffix}/fallback1/construction.json')
            write(HERE / rel, construction)
            candidates.append((rel, digest(HERE / rel)))
        primary, fallback = candidates
        entries.append({'case_id': case_id, 'kind': 'delivery',
                        'construction': primary[0], 'construction_sha256': primary[1],
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Native vehicle trajectory, clearance or stop cause may miss requested target.'},
                        'candidates': [{'id': 'fallback1', 'construction': fallback[0],
                                        'construction_sha256': fallback[1],
                                        'trigger': {'source': 'original Native rail actor and four-camera traces',
                                                    'metric': 'trailing-end position, grade or queue geometry',
                                                    'failure_condition': 'primary misses reviewed crossing geometry'},
                                        'changed_knobs': ['brake_gain 4.0 to 5.0']}],
                        'measurement_procedure': {'entrypoint': 'finalize.py'},
                        'measurement_contract': contract,
                        'fixture_recipe': f'work/{AID}/diagnostic-{suffix}-recipe.json',
                        'delivery_readiness': 'incomplete_original_rail_source_pending',
                        'id': 'primary'})
    batch = json.loads((ROOT / 'batch.json').read_text())
    write(HERE / 'execution-manifest.json',
          {'format': 'worker-execution-manifest', 'assignment_id': AID,
           'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
           'status': 'selected_cpu_source_dependency', 'cases': entries})
    first = json.loads((HERE / entries[0]['construction']).read_text())
    for item in first['files']:
        if not item['path'].startswith('tests/'):
            target = HERE / item['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item['content'])
    write(HERE / 'construction.json', first)
    write(HERE / 'proposals/cases.json', {
        'cell_id': 'C202465', 'actor': 'motor_vehicle_driver',
        'status': 'draft', 'sweep_specs': [], 'sweeps_expanded': True,
        'cases': [{'case_id': AID + '__' + suffix,
                   'target_law_id': 'NRS-484B-560-7a',
                   'target_type': 'boundary_probe' if suffix.startswith('trailing_') else 'controlled_attempt',
                   'rationale': 'At-grade crossing space, undercarriage and 15-foot trailing-end alternatives',
                   'paired_probe_id': variable,
                   'deliberate_differences': [variable],
                   'probe': {'primary_variable': variable,
                             'comparison_or_standard': 'original source-reviewed crossing',
                             'target_value_or_branch': suffix},
                   'variable_assignments': {variable: {'kind': 'world_setup',
                                                       'value': suffix}},
                   'recording_description': description,
                   'unresolved_judgment_calls': ['original rail and vehicle source review',
                                                  'independent physical stop cause']}
                  for suffix in VARIANTS
                  for variable, left, right in (
                      ('opposite_space', 'space_clear', 'space_short'),
                      ('undercarriage_clearance', 'grade_clear', 'grade_deficit'),
                      ('trailing_end_15_feet', 'trailing_exact', 'trailing_just_short'))
                  if suffix in (left, right)]})
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    pairings = (('opposite_space', 'space_clear', 'space_short'),
                ('undercarriage_clearance', 'grade_clear', 'grade_deficit'),
                ('trailing_end_15_feet', 'trailing_exact', 'trailing_just_short'))
    plan['cases'] = [{
        'case_id': AID + '__' + suffix,
        'target_law_id': 'NRS-484B-560-7a',
        'kind': 'selected_cpu_source_dependency',
        'target_type': 'boundary_probe' if suffix.startswith('trailing_') else 'controlled_attempt',
        'physical_target': {
            'space_clear': 'original vehicle reaches trailing-end 15-foot clearance with opposite-side space',
            'space_short': 'original queue constrains opposite-side space before trailing-end 15-foot clearance',
            'grade_clear': 'original road/vehicle grade permits crossing without preclear stop',
            'grade_deficit': 'original road/vehicle grade yields reviewed undercarriage contact before full crossing',
            'trailing_exact': 'trailing end reaches at least 15 feet past reviewed reference rail',
            'trailing_just_short': 'trailing end remains short of 15 feet past reviewed reference rail'}[suffix],
        'comparison_variable': next(variable for variable, left, right in pairings
                                    if suffix in (left, right)),
        'requested_not_measured': True,
        'selection_targets': ['full-train']}
        for suffix in VARIANTS]
    plan['comparisons'] = [{
        'comparison_id': AID + '__' + variable,
        'case_ids': [AID + '__' + left, AID + '__' + right],
        'deliberate_differences': [variable],
        'fixed_conditions': ['frozen cell and actor', 'original at-grade rail source',
                             '20 Hz and four-camera policy',
                             'same controller family and 30-second duration']}
        for variable, left, right in pairings]
    for index, disposition in enumerate(plan['requirement_dispositions']):
        disposition['status'] = 'selected_required'
        disposition['case_ids'] = [AID + '__' + suffix for suffix in VARIANTS]
        disposition['evidence_or_gap'] = (
            'Exact primary/fallback inline Native construction and offline CPU proof are selected. '
            'Independent original at-grade rail, vehicle, queue, grade and stop-cause evidence, '
            'public compatibility, saved processing and physical/lifecycle audit remain pending. '
            'No physical or legal outcome claimed.')
    plan['witness_branches'] = [
        'Opposite-side space insufficiency.', 'Undercarriage-clearance alternative.',
        'Completely-cross trailing-end 15-foot definition.']
    plan['candidate_plans'] = [{
        'case_id': entry['case_id'], 'primary': entry['construction'],
        'fallback1': entry['candidates'][0]['construction'],
        'risk': entry['candidate_risk']} for entry in entries]
    plan['summary_status'] = 'selected_cpu_original_source_pending'
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [{'view': name, 'subject': 'original rail, subject body and opposite-side space',
                      'interval': '0-30 seconds'} for name in CAMERAS]}
    plan['blockers'] = [
        'Original Native at-grade rail, reviewed opposite-side queue and grade/undercarriage sources have not been acquired.',
        'Independent stop-cause and trailing-end physical acceptance remain unverified.',
        'Public compatibility, recorded-only saved processing, and delivery/comparison audits remain pending.']
    write(plan_path, plan)
    return {'case_count': len(entries), 'manifest_sha256': digest(HERE / 'execution-manifest.json')}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
