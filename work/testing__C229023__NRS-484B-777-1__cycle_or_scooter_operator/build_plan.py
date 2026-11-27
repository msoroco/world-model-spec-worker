"""Expand the frozen 777(1) pass witness into controlled physical probes."""

import json
from pathlib import Path

from rightside import CASES


HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = 'NRS-484B-777-1'


def build():
    path = HERE / 'case-plan.json'
    plan = json.loads(path.read_text())
    assert plan['assignment_id'] == AID and plan['law_id'] == LAW
    ids = {case.name: AID + '__' + case.name for case in CASES}
    reason = ('Reviewed original roadway and participant sources, original 20 Hz body geometry, '
              'passing phases and four synchronized cameras remain to be captured. '
              'Neither due care nor practicability is assigned a numeric cutoff.')
    plan['cases'] = []
    for case in CASES:
        plan['cases'].append({
            'case_id': ids[case.name], 'kind': 'delivery', 'target_law_id': LAW,
            'case_kind': 'physical_capture_probe', 'new_capture_selected': True,
            'capture_frames': 900, 'fps': 20, 'gap_ids': ['unverified-passing-coverage'],
            'cycle_kind': case.cycle_kind, 'requested_lateral_target_m': case.lateral_target_m,
            'right_impediment': case.right_impediment, 'narrow_lane': case.narrow_lane,
            'traffic_speed_context': case.traffic_speed_context,
            'left_turn_preparation': case.left_turn_preparation,
            'target_motion': case.target_motion,
            'construction': 'rightside.py:construct',
            'measurement': 'rightside.py:measure_original',
            'physical_risk': ('Native cycle and other-vehicle pass may miss behind/alongside/ahead '
                              'phases or camera views; source-reviewed roadway/body geometry and '
                              'right-side impediment must be confirmed at the original site.'),
            'candidate_risk': {'status': 'physical', 'reason':
                               'Source-gated Native cycle pass may miss alongside phase or camera coverage.'},
            'required_original_packets': ['road_geometry', 'roadway_boundary',
                                           'right_side_boundary', 'cycle_motion',
                                           'other_vehicle_motion', 'body_geometry',
                                           'right_impediment', 'lane_width',
                                           'nearby_traffic', 'left_turn_preparation',
                                           'four_camera_video'],
            'construction_status': 'source_gated_native_cpu_implementation',
        })

    specs = (
        ('right_side_position', 'moving_near_right', 'moving_left_offset',
         ['requested_lateral_target_m'], 'same roadway, target vehicle, bicycle, route and exception context'),
        ('moving_vehicle_impediment', 'moving_left_offset', 'moving_right_impeded',
         ['right_impediment'], 'same roadway width, bicycle, target motion and lateral target'),
        ('narrow_lane_exception', 'moving_left_offset', 'moving_narrow_lane',
         ['narrow_lane'], 'same route, bicycle, target motion and lateral target'),
        ('commensurate_speed_exception', 'moving_left_offset', 'moving_commensurate_speed',
         ['traffic_speed_context'], 'same route, bicycle, right position and target motion'),
        ('left_turn_preparation_exception', 'moving_left_offset', 'moving_left_preparation',
         ['left_turn_preparation'], 'same road, bicycle, right position and target motion'),
        ('standing_or_proceeding', 'moving_right_impeded', 'standing_right_impeded',
         ['target_motion', 'right_impediment'], 'same bicycle, right position and physical pass method'),
        ('cycle_classification', 'moving_right_impeded', 'scooter_right_impeded',
         ['cycle_kind'], 'same roadway, target motion, right obstruction and route'),
    )
    plan['comparisons'] = [
        {'comparison_id': key, 'case_ids': [ids[left], ids[right]],
         'fixed_conditions': fixed, 'deliberate_differences': changed,
         'status': 'planned_source_gated'}
        for key, left, right, changed, fixed in specs
    ]
    plan['observations'] = [
        {'name': name, 'mandatory': True, 'source': 'original Native source packet',
         'description': description}
        for name, description in (
            ('right_edge_distance', 'cycle body edge to reviewed right roadway boundary'),
            ('relative_station', 'cycle and target vehicle station across pass'),
            ('surface_clearance', 'minimum original cycle/vehicle body clearance'),
            ('cycle_speed', 'original cycle speed and nearby traffic context'),
            ('other_vehicle_speed', 'original target motion and speed'),
            ('right_access_width', 'original usable width at right side and impediment'),
            ('lane_width', 'reviewed lane and body dimensions'),
            ('left_turn_preparation', 'separately sourced turn intent and actions'),
            ('camera_frame_identity', 'four original synchronized camera frame IDs'),
        )]
    all_ids = list(ids.values())
    plan['requirement_dispositions'] = [
        {'disposition_index': index, 'requirement': requirement,
         'source': 'NRS 484B.777(1) and (2), ' + clause, 'status': 'selected_required',
         'case_ids': [ids[name] for name in names], 'evidence_or_gap': reason}
        for index, (requirement, clause, names) in enumerate((
            ('covered bicycle, electric bicycle or electric scooter operator on roadway',
             'activation', tuple(ids)),
            ('near right side as practicable, with full body and right boundary',
             'right-side placement', ('moving_near_right', 'moving_left_offset')),
            ('due care when passing a vehicle proceeding in the same direction',
             'same-direction passing', tuple(name for name in ids if name.startswith('moving_'))),
            ('due care when passing a standing vehicle',
             'standing vehicle', ('standing_right_impeded',)),
            ('lawful speed commensurate with nearby traffic exception',
             'exception (a)', ('moving_left_offset', 'moving_commensurate_speed')),
            ('preparing to turn left exception',
             'exception (b)', ('moving_left_offset', 'moving_left_preparation')),
            ('unsafe right-side access due to fixed or moving objects and surface hazards',
             'exception (c) and 777(2)(a)', ('moving_left_offset', 'moving_right_impeded', 'standing_right_impeded')),
            ('lane too narrow for cycle and vehicle side by side',
             '777(2)(b)', ('moving_left_offset', 'moving_narrow_lane')),
        ))]
    plan['selected_branch'] = 'passing_same_direction_vehicle'
    plan['source_observation_mapping'] = {}
    plan['evidence_review'] = {
        'reviewer': 'CPU worker',
        'method': 'Read the exact exported law and witness plus empty frozen accepted-recording inventory; no equivalent accepted recording exists.',
        'facts': [],
        'gaps': [{'id': 'unverified-passing-coverage',
                  'requirement': 'Original roadway, cycle, target and full pass evidence for 777(1) and (2)',
                  'source': 'inputs/' + AID + '/assignment.json',
                  'why_existing_insufficient': 'Frozen evidence.json lists no accepted recordings.'}],
    }
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 45,
        'composition': 'synchronized_four_view_primary',
        'coverage': [{'view': view, 'subject': 'cycle body, right roadway edge, target vehicle and pass phases',
                      'interval': 'all 900 original frames'}
                     for view in ('overview', 'approach', 'reference_corner', 'driver_reference')],
        'limitation': 'Synthetic diagnostics cannot prove actual participant visibility.'}
    plan['runtime_uncertainties'] = [
        'Actual CARLA cycle blueprint, road edge, obstruction, pass motion and pixels require local original capture.',
        'Lawful speed, commensurateness, due care, safety and practicability remain independent legal review questions.',
    ]
    plan['judgment_range_inventory'] = []
    plan['planning_status'] = 'selected_source_gated_cpu_implementation'
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
    return len(plan['cases']), len(plan['comparisons'])


if __name__ == '__main__':
    print('exact cases and comparisons:', *build())
