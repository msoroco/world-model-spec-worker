"""Prepare controlled, unlabeled bicycle-speed and condition cases."""
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
path = folder / 'case-plan.json'
plan = json.loads(path.read_text())
aid = plan['assignment_id']
variants = [
    ('reference', 3.0, 'clear', 'dry', 'no pedestrian near rack'),
    ('faster', 5.0, 'clear', 'dry', 'no pedestrian near rack'),
    ('reduced_visibility', 3.0, 'reduced', 'dry', 'no pedestrian near rack'),
    ('pedestrian_near_rack', 3.0, 'clear', 'dry', 'pedestrian near rack'),
    ('wet_surface', 3.0, 'clear', 'wet', 'no pedestrian near rack'),
]
plan['cases'] = [{
    'case_id': aid + '__' + name,
    'target_law_id': plan['law_id'],
    'kind': 'delivery',
    'target_type': 'judgment_sweep',
    'gap_ids': ['no_accepted_bicycle_speed_history'],
    'world_setup': {'layout': 'alley', 'maneuver': 'travel', 'control': 'bicycle_rack',
                    'bicycle': 'human-powered, excluding moped', 'municipal_jurisdiction': 'City of Las Vegas; to verify against the actual map',
                    'visibility_condition': visibility, 'surface_condition': surface,
                    'pedestrian_condition': pedestrian},
    'controller': {'target_speed_mps': speed},
    'subject_behavior': {'observed_speed_mps': None, 'legal_prudence': None},
    'rationale': 'Measure actual bicycle speed with contemporaneous conditions; no target speed establishes the legal standard.',
    'recording_description': '20 Hz original bicycle velocity and frame map; four-camera synchronized full episode; original weather, surface, visibility, pedestrian and alley/rack geometry context.',
    'physical_risk': {'status': 'physical', 'reason': 'A bicycle may fail to follow the alley route or the rack may fall outside camera coverage; verify realized body motion and rack pixels before selecting any same-case fallback.'},
} for name, speed, visibility, surface, pedestrian in variants]
reference = aid + '__reference'
plan['comparisons'] = [{
    'comparison_id': name,
    'case_ids': [reference, aid + '__' + other],
    'fixed_conditions': ['same alley and bicycle-rack geometry', 'same human-powered bicycle classification', 'same route and four-camera contract', *fixed],
    'deliberate_differences': [difference],
    'audit_measurements': ['actual bicycle speed time history', 'original contemporaneous condition history'],
    'legal_prudence': 'unresolved',
} for name, other, fixed, difference in [
    ('speed_under_clear_conditions', 'faster', ['same clear visibility', 'same dry surface', 'same pedestrian state'], 'controller speed target only; compare actual measured speed'),
    ('visibility_at_reference_speed', 'reduced_visibility', ['same speed target', 'same dry surface', 'same pedestrian state'], 'visibility condition only; compare original weather and visibility sources'),
    ('pedestrian_at_reference_speed', 'pedestrian_near_rack', ['same speed target', 'same clear visibility', 'same dry surface'], 'pedestrian presence near rack only; compare actor tracks and video'),
    ('surface_at_reference_speed', 'wet_surface', ['same speed target', 'same clear visibility', 'same pedestrian state'], 'surface condition only; compare original surface and weather sources'),
]]
plan['observations'] = [
    {'name': 'actual_bicycle_speed', 'unit': 'm/s', 'source': 'original bicycle velocity and synchronized frame map', 'method': 'Euclidean velocity magnitude at every original 20 Hz frame; retain full history', 'legal_threshold': None},
    {'name': 'contemporaneous_conditions', 'unit': 'source-bound context', 'source': 'original weather, surface, visibility, pedestrian, route and rack packets plus full video', 'method': 'retain conditions on the same original frame/time axis; report uncertainty', 'legal_threshold': None},
    {'name': 'bicycle_subject_and_jurisdiction', 'unit': 'source-bound context', 'source': 'actor classification and map jurisdiction review', 'method': 'document human-powered bicycle, moped exclusion and City of Las Vegas location; unresolved applicability remains pending'},
]
plan['evidence_review']['gaps'] = [{
    'id': 'no_accepted_bicycle_speed_history',
    'requirement': 'Actual bicycle operation, original speed history and contemporaneous alley conditions for LVMC 11.40.130',
    'source': {'path': 'inputs/' + aid + '/evidence.json', 'sha256': '8226450e7732a54b7e084467da9f669f2ffec3e209e6189f279f3445433fd586'},
    'why_existing_insufficient': 'The frozen evidence inventory lists zero accepted recordings; no original speed or condition history is available for reuse.',
}]
plan['requirement_dispositions'] = [{
    'disposition_index': 0, 'requirement': 'Bicycle speed no greater than reasonable and prudent under then-existing conditions',
    'source': 'LVMC 11.40.130; inputs/' + aid + '/assignment.json',
    'status': 'selected_required', 'case_ids': [case['case_id'] for case in plan['cases']],
    'evidence_or_gap': 'No accepted recording; five controlled unlabeled cases measure speed and condition dimensions without defining prudence.',
}]
plan['selected_branch'] = plan['selected_branches'][0]
plan['runtime_uncertainties'] = [
    'The legal meaning of reasonable and prudent remains unresolved; target speeds are engineering coverage values only.',
    'Human-powered bicycle actor, municipal jurisdiction, alley route, rack geometry and actual video visibility need local verification.',
    'Exact CARLA construction, canonical semantic proposals, offline/compatibility, saved-only and independent delivery/comparison proofs remain to be implemented.',
]
plan['planning_status'] = 'controlled_cases_drafted'
path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
print('planned', len(plan['cases']), 'cases and', len(plan['comparisons']), 'comparisons')
