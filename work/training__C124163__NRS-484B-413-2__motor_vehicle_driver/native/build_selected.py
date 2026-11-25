"""Materialize four exact source-capture proposals for the two statutory forks."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
NATIVE = ROOT/'native'
LAW = 'NRS-484B-413-2'
DISTANCES = {'other_long': 100.0, 'other_at': 91.44, 'other_short': 70.0,
             'district_long': 35.2, 'district_at': 30.48, 'district_short': 20.0}
TEST = '''import copy
import json
import unittest
from pathlib import Path
from runner import check

class ExactSourceCapture(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_exact_600_frame_source_plan(self):
        proof = check(self.config)
        self.assertEqual((proof['frames'], proof['rate_hz']), (600, 20))
        self.assertEqual(len(proof['cameras']), 4)
        self.assertFalse(proof['legal_verdict_claimed'])

    def test_reject_source_or_identity_change(self):
        for key, value in [('requested_signal_distance_m', 1),
                           ('weather', 'snow'), ('cell_id', 'other'),
                           ('duration_s', 1)]:
            bad = copy.deepcopy(self.config)
            bad[key] = value
            with self.assertRaises(ValueError):
                check(bad)
        bad = copy.deepcopy(self.config)
        bad['cameras'].pop()
        with self.assertRaises(ValueError):
            check(bad)
'''


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    from turn_capture_plan import plan
    batch = json.loads((REPO/'batch.json').read_text())
    runtime_sha = batch['runtime']['source_manifest_sha256']
    plan_data = json.loads((ROOT/'case-plan.json').read_text())
    entries = []
    proposals = []
    for condition, requested_m in DISTANCES.items():
        case = ROOT.name+'__'+condition
        request = plan(condition)
        cfg = {k: request[k] for k in ('condition', 'district_class', 'weather',
                 'requested_signal_distance_m', 'rate_hz', 'frames', 'duration_s',
                 'maneuver', 'layout')}
        cfg.update(case_id=case, selected_case_id=case, law_id=LAW,
                   cell_id='C124163', actor='motor_vehicle_driver',
                   supported_case_ids=[ROOT.name+'__'+name for name in DISTANCES],
                   spawn_point_index=0, legal_verdict=None,
                   required_atoms=['kin.position', 'kin.speed'],
                   signal_request_start_odometer_m=120.0-requested_m,
                   course_change_request_odometer_m=120.0,
                   physical_completion={'criterion': 'travel_progress',
                        'motion_source': 'trace.jsonl', 'position_key': 'position_m',
                        'minimum_progress_m': 120.0,
                        'engineering_tolerances_not_legal': True},
                   cameras=[{'name': name, 'width': width, 'height': height,
                             'fov_deg': 90, 'pose': [*xyz, 0, 0, 0],
                             'pose_strategy': 'capture original indicator pixels, median-opening turn onset and route context for all 600 frames'}
                            for name, width, height, xyz, _ in
                            [(c['name'], c['width'], c['height'], c['xyz_m'],
                              c['attach_to_ego']) for c in request['cameras']]],
                   recording_description={
                       'channels': [{'name': name, 'unit': 'structured',
                                     'sampling_rate_hz': 20,
                                     'time_window': '600 original frames',
                                     'method': 'post-tick Native source joined to original camera frames; unobservable terms remain explicitly unresolved',
                                     'reference_frame': 'original Native frame',
                                     'uncertainty': 'Visible signaling, hand signal, district/weather and turn onset need original independent review'}
                                    for name in ('kin.position', 'kin.speed',
                                                 'sig.turn_indicator', 'sig.hand_signal',
                                                 'drv.distance_while', 'kin.path_length',
                                                 'drv.turning', 'drv.lane_change',
                                                 'env.precipitation')],
                       'context_inputs': [{'name': 'district_weather_review',
                            'unit': 'structured',
                            'method': 'independent original district and weather source review'}],
                       'limitations': ['A control request does not prove visible signaling.',
                                       'District, weather, turn onset and indicator pixels require original review.']})
        files = [{'path': name, 'source': 'work/'+ROOT.name+'/native/'+name,
                  'content': (NATIVE/name).read_text()}
                 for name in ('selected_runner.py', 'turn_capture_plan.py', 'finalize.py')]
        files[0]['path'] = 'runner.py'
        files += [{'path': 'config.json', 'content': json.dumps(cfg, indent=2)+'\n'},
                  {'path': 'tests/test_offline.py', 'content': TEST}]
        construction = {'actor': 'motor_vehicle_driver', 'case_id': case,
                        'cell_id': 'C124163', 'law_id': LAW,
                        'entrypoint': 'runner.py', 'status': 'selected_cpu_construction',
                        'files': files,
                        'mechanisms': ['20 Hz original Native frame and odometer capture',
                                       'post-tick signal-state readback',
                                       'four original camera streams and frame map'],
                        'measurement_plan': 'Join original signal activity, traveled distance, yaw change, reviewed district and weather, and visible pixels. No legal verdict from requests.',
                        'recording_description': cfg['recording_description'],
                        'termination_rules': ['600 synchronized frames or explicit failure'],
                        'static_checks': ['four source cameras', '600 frames at 20 Hz',
                                          'exact condition and source-uncertainty flags']}
        path = NATIVE/'selected-drafts'/condition/'primary'/'construction.json'
        write(path, construction)
        fallback_config = deepcopy(cfg)
        fallback_config['spawn_point_index'] = 1
        fallback_files = [dict(item) for item in files]
        fallback_files = [dict(item, content=json.dumps(fallback_config, indent=2)+'\n')
                          if item['path'] == 'config.json' else item for item in fallback_files]
        fallback_construction = dict(construction, files=fallback_files,
            measurement_plan=construction['measurement_plan']+' Fallback shifts only the surveyed spawn point.')
        fallback_path = NATIVE/'selected-drafts'/condition/'fallback1'/'construction.json'
        write(fallback_path, fallback_construction)
        entries.append({'case_id': case, 'kind': 'delivery', 'id': 'primary',
                        'candidate_risk': {'status': 'physical',
                            'reason': 'The median-opening route or actor spawn may be occupied or unsuitable for the requested 120 m approach.'},
                        'candidates': [{'id': 'fallback1',
                            'construction': str(fallback_path.relative_to(ROOT)),
                            'construction_sha256': sha(fallback_path),
                            'trigger': {'source': 'native-run-status.json',
                                'metric': 'spawn_and_120m_route_progress',
                                'failure_condition': 'primary spawn occupied or source route cannot reach requested course-change point'},
                            'changed_knobs': ['spawn_point_index 0 to 1']}],
                        'construction': str(path.relative_to(ROOT)),
                        'construction_sha256': sha(path),
                        'measurement_contract': 'measurement-'+condition+'.json',
                        'measurement_procedure': {'entrypoint': 'finalize.py',
                            'output_schema': 'signal-distance-saved-analysis-v1'},
                        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                            'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
                        'acquisition': {item['name']: {'entrypoint': 'finalize.py',
                            'method': 'source-joined original post-tick Native light, odometer and camera frames',
                            'evidence': 'Original pixels, district, weather and turn onset require independent review'}
                            for item in cfg['recording_description']['channels']}})
        proposals.append({'case_id': case, 'target_law_id': LAW,
            'target_type': 'judgment_sweep',
            'rationale': 'Source-joined signal distance before a left-turn request in the stated district and weather, without a legal verdict.',
            'variable_assignments': {
                'requested_signal_distance_m': {'kind': 'controller', 'unit': 'm', 'value': requested_m},
                'district_class': {'kind': 'world_setup', 'unit': 'categorical', 'value': cfg['district_class']},
                'weather': {'kind': 'world_setup', 'unit': 'categorical', 'value': cfg['weather']}},
            'paired_probe_id': ROOT.name+'__'+condition.split('_')[0]+'_signal_pair',
            'deliberate_differences': ['requested_signal_distance_m'],
            'probe': {'primary_variable': 'requested_signal_distance_m',
                'comparison_or_standard': 'source-joined continuous visible signal distance and exact statutory district threshold',
                'target_value_or_branch': requested_m},
            'unresolved_judgment_calls': ['visible signal pixels', 'district class',
                'weather verification', 'observed course-change onset', 'accepted recording equivalence'],
            'recording_description': cfg['recording_description']})
        selected = [0, 1] + ([2, 3] if condition.startswith('other_') else [])
        requirements = [{'disposition_index': i,
            'requirement': plan_data['requirement_dispositions'][i]['requirement'],
            'source': plan_data['requirement_dispositions'][i]['source'],
            'output_key': ('continuous_signal_distance', 'weather_no_waiver',
                           'other_area_review_scope', 'other_area_review_repeat')[i],
            'method': ('measure_signal_distance', 'source_weather_context',
                       'reviewed_other_area_scope', 'reviewed_other_area_repeat')[i],
            'value_type': 'object',
            'kind': 'measured' if i == 0 else 'sourced_context',
            'inputs': ['signal-source.jsonl', 'video_frames.jsonl', 'context-review.json']}
            for i in selected]
        write(ROOT/('measurement-'+condition+'.json'),
              {'format': 'worker-measurement-contract', 'requirements': requirements,
               'negative': {'remove': ['signal-source.jsonl'],
                            'error_contains': 'Missing required source: signal-source.jsonl'}})
    write(ROOT/'execution-manifest.json',
          {'format': 'worker-execution-manifest', 'assignment_id': ROOT.name,
           'runtime_manifest_sha256': runtime_sha,
           'status': 'selected_cpu_construction_partial', 'cases': entries})
    all_cases = [entry['case_id'] for entry in entries]
    for i, disposition in enumerate(plan_data['requirement_dispositions']):
        disposition['status'] = 'selected_required'
        disposition['case_ids'] = all_cases if i < 2 else all_cases[:3]
        disposition['evidence_or_gap'] = ('Exact source-joined CPU measurement selected; original visible signal, district, weather, onset and accepted-equivalence review pending.'
                                         if i < 2 else 'Reviewed other-area 300-foot source scope bound to two exact other-area cases; original source review pending.')
    plan_data['cases'] = [
        {'case_id': p['case_id'], 'target_law_id': LAW,
         'target_type': 'planned_delivery_comparison',
         'planning_status': 'selected_cpu_prepared',
         'source_branch': 'other_area_300ft' if p['case_id'].endswith(('other_long', 'other_short')) else 'business_or_residential_100ft',
         'comparison_variable': 'continuous_signal_distance_before_course_change',
         'fixed_conditions': {'cell_id': 'C124163', 'layout': 'median_opening',
            'maneuver': 'left_turn', 'actor': 'motor_vehicle_driver', 'law_id': LAW,
            'district_class': p['variable_assignments']['district_class']['value'],
            'weather': p['variable_assignments']['weather']['value']},
         'source_text': plan_data['source_law']['text'],
         'claim': 'CPU construction and synthetic source checks only; no original physical or legal outcome.'}
        for p in proposals]
    plan_data['comparisons'] = [
        {'comparison_id': ROOT.name+'__'+district+'_'+left+'_'+right+'_signal_pair',
         'case_ids': [ROOT.name+'__'+district+'_'+left, ROOT.name+'__'+district+'_'+right],
         'deliberate_differences': ['requested_signal_distance_m'],
         'fixed_conditions': {'cell_id': 'C124163', 'layout': 'median_opening',
            'maneuver': 'left_turn', 'actor': 'motor_vehicle_driver', 'law_id': LAW,
            'district_class': 'other_area' if district == 'other' else 'business_or_residential',
            'weather': 'clear' if district == 'other' else 'rain'},
         'status': 'selected_cpu_prepared',
         'audit_gap': 'Original pixel visibility, route, district/weather and independent comparison review pending.'}
        for district in ('other', 'district') for left, right in (('long', 'at'), ('at', 'short'))]
    plan_data['legal_analysis_note'] = ('Six selected left-indicator requests cover above, exactly at and below 300-foot other-area clear and 100-foot district rain stimuli. Observed post-tick distance is measured separately; exact physical boundary is not inferred from a request. Right turns, hand signals and other direct-course changes remain source alternatives requiring explicit future original capture/review; weather never waives either distance. Accepted membership lacks source-hashed equivalence.')
    plan_data['camera_plan'] = {'profile': 'overview1080-capability',
        'duration_s': 30, 'composition': 'synchronized_four_view_primary',
        'coverage': [{'subject': 'visible left indicator, median-opening course change, district and weather context',
                      'interval': 'all 600 original frames', 'view': view}
                     for view in ('overview', 'approach', 'reference_corner', 'driver_reference')]}
    plan_data['readiness'] = 'selected_cpu_partial'
    write(ROOT/'case-plan.json', plan_data)
    write(ROOT/'proposals'/'cases.json',
          {'format': 'worker-case-proposals', 'cell_id': 'C124163',
           'actor': 'motor_vehicle_driver', 'law_id': LAW, 'status': 'draft',
           'cases': proposals, 'sweep_specs': [], 'sweeps_expanded': True})
    print(json.dumps({'cases': [e['case_id'] for e in entries],
                      'manifest_sha256': sha(ROOT/'execution-manifest.json')}))


if __name__ == '__main__':
    main()
