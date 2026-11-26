"""Add the statutory passing exception to the retained lane comparison plan."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRATCH = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])


def main():
    path = ROOT / 'case-plan.json'
    plan = json.loads(path.read_text())
    aid = plan['assignment_id']
    source = 'NRS 484B.627(1)(b)'
    suffixes = ('probe_a', 'probe_b', 'necessary_pass', 'post_pass_linger')
    ids = {name: aid + '__' + name for name in suffixes}
    existing = {case['case_id']: case for case in plan['cases']}
    for case in plan['cases']:
        case['target_type'] = 'judgment_sweep'
    for name, target, kind in (
        ('necessary_pass', 'occupy left lane only while passing an observed slower vehicle and return right after clearance', 'exception_attempt'),
        ('post_pass_linger', 'occupy left lane after the observed slower vehicle is cleared', 'exception_duration_contrast')):
        if ids[name] not in existing:
            plan['cases'].append({'case_id': ids[name], 'target_law_id': plan['law_id'],
                                  'kind': 'planned_only', 'target_type': 'judgment_sweep',
                                  'physical_target': target, 'comparison_variable': 'post_pass_lane_return',
                                  'exception_probe_kind': kind})
    plan['comparisons'] = [row for row in plan['comparisons'] if row['comparison_id'] != aid + '__passing_duration_comparison']
    plan['comparisons'].append({
        'comparison_id': aid + '__passing_duration_comparison',
        'case_ids': [ids['necessary_pass'], ids['post_pass_linger']],
        'deliberate_differences': ['post_clearance_target_lane'],
        'fixed_conditions': ['same roundabout topology and clearly marked same-direction lanes',
                             'same ego, follower and slower-vehicle blueprints and source speed policy',
                             'same pass initiation and clearance source definition',
                             'same 20 Hz, 30 second four-camera capture policy'],
        'source_review': 'A slower vehicle ahead and necessity of a pass require original Native and independent review; controller request does not establish either.'})
    plan['requirement_dispositions'] = [
        {'disposition_index': 0, 'requirement': 'slow speed impeding forward movement of traffic immediately behind',
         'source': source, 'status': 'selected_required', 'case_ids': list(ids.values()),
         'evidence_or_gap': 'Original ego/follower positions and velocities plus independent review of whether movement was impeded; synthetic speed ordering is diagnostic only.'},
        {'disposition_index': 1, 'requirement': 'two or more clearly marked same-direction lanes and extreme right-hand lane duty',
         'source': source, 'status': 'selected_required', 'case_ids': [ids['probe_a'], ids['probe_b']],
         'evidence_or_gap': 'Original Native lane topology, markings, actor body and lane occupancy throughout the impeding interval.'},
        {'disposition_index': 2, 'requirement': 'exception only when necessary to pass other slowly moving vehicles',
         'source': source, 'status': 'selected_required', 'case_ids': [ids['necessary_pass'], ids['post_pass_linger']],
         'evidence_or_gap': 'Original slower vehicle, relative motion, actual pass and clearance timing; independent necessity judgment remains for local review.'},
        {'disposition_index': 3, 'requirement': 'right-lane return after any necessary pass ends',
         'source': source, 'status': 'selected_required', 'case_ids': [ids['necessary_pass'], ids['post_pass_linger']],
         'evidence_or_gap': 'Original pass-clearance event and body-lane occupancy after that event; no invented statutory grace duration.'},
    ]
    plan['source_observation_mapping'] = {
        term: {'evidence': evidence,
               'channels': ['native_lane_body_follower_and_pass', 'four_camera_video'],
               'source_refs': ['native/capture.py', 'native/measure.py']}
        for term, evidence in (
            ('drv.speed_below_traffic', 'Original ego and immediately following traffic velocities, with independent impeding judgment.'),
            ('drv.queue_behind', 'Original follower identity and distance behind ego throughout the interval.'),
            ('drv.laned_roadway', 'Original Native map lane readback plus visible same-direction lane markings.'),
            ('drv.extreme_lane', 'Original ego body polygon and extreme-right lane boundary by frame.'),
            ('rel.occupies', 'Original ego body and lane occupancy join by frame.'),
            ('drv.overtaking', 'Original slower vehicle, pass onset/clearance and ego motion; necessity separately reviewed.'),
            ('st.lane_adjacency', 'Original Native same-direction lane topology and adjacency readback.'))}
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'entire marked roundabout, ego, follower, slower vehicle and lane topology', 'interval': 'full impeding and optional passing interval'},
            {'view': 'approach', 'subject': 'ego and following vehicle positions and same-direction lane markings', 'interval': 'entry through roundabout circulation'},
            {'view': 'reference_corner', 'subject': 'roundabout lane boundary, ego body and slower vehicle during pass and return', 'interval': 'pass onset through post-clearance'},
            {'view': 'driver_reference', 'subject': 'driver-relative marked lane and slower vehicle view', 'interval': 'full roundabout circulation'}]}
    plan['runtime_uncertainties'] = [
        'Original roundabout topology and marked same-direction lane readback require Native operator survey.',
        'A slow ego and trailing follower do not themselves settle statutory impeding; independent review required.',
        'Slower-vehicle pass necessity and clearance must be observed, not inferred from the requested controller phase.',
        'Actual camera pixels and physical lane occupancy remain local Native checks.']
    SCRATCH.mkdir(parents=True, exist_ok=True)
    stage = SCRATCH / 'c132924-plan.stage'
    stage.write_text(json.dumps(plan, indent=2) + '\n')
    os.replace(stage, path)
    print(json.dumps({'exact_cases': len(plan['cases']), 'comparisons': len(plan['comparisons']),
                      'statutory_dispositions': len(plan['requirement_dispositions'])}))


if __name__ == '__main__':
    main()
