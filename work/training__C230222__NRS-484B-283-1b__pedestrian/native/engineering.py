"""Unselected curb-entry Native alternatives and measured-trigger requirements."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
BASE = 'training__C230222__NRS-484B-283-1b__pedestrian'
IDS = ('primary', 'fallback1', 'fallback2', 'fallback3')


def candidate(suffix, ident):
    if suffix not in ('probe_1', 'probe_2') or ident not in IDS:
        raise ValueError('Unknown curb probe or candidate')
    start = .5 if suffix == 'probe_1' else 3.5
    knobs = {'pedestrian_spawn_x_m': -4.5, 'pedestrian_pre_roll_s': 0.0,
             'pedestrian_departure_s': start, 'pedestrian_target_speed_mps': 3.0,
             'pedestrian_control': 'target_velocity', 'vehicle_start_y_m': -18.0,
             'vehicle_target_speed_mps': 4.0,
             'vehicle_control': 'speed_until_observed_departure_then_brake',
             'vehicle_reaction_s': 0.8, 'vehicle_brake_command': 1.0,
             'camera_distance_m': 8.0, 'camera_width': 1280, 'camera_height': 720}
    trigger = {'metric': 'initial', 'source': 'none', 'threshold': None,
               'physical_observation': None}
    if ident == 'fallback1':
        knobs.update(pedestrian_spawn_x_m=-6.5, pedestrian_pre_roll_s=2/3)
        trigger = {'metric': 'native_initial_footprint_clearance_m_below',
                   'source': 'original_native_pedestrian_footprint_and_road_edge',
                   'threshold': 1.25, 'physical_observation': None}
    elif ident == 'fallback2':
        knobs.update(pedestrian_control='bounded_acceleration_to_target_velocity')
        trigger = {'metric': 'native_first_departure_acceleration_mps2_above',
                   'source': 'original_native_pedestrian_velocity_and_frame_times',
                   'threshold': 4.0, 'physical_observation': None}
    elif ident == 'fallback3':
        knobs.update(camera_distance_m=4.0)
        trigger = {'metric': 'original_curb_and_vehicle_visibility_fraction_below',
                   'source': 'independent_original_camera_pixel_audit',
                   'threshold': .95, 'physical_observation': None}
    return {'case_id': BASE + '__' + suffix, 'candidate_id': ident,
            'law_id': 'NRS-484B-283-1b', 'cell_id': 'C230222', 'actor': 'pedestrian',
            'duration_s': 12, 'rate_hz': 20, 'road_source': 'native/road.xodr',
            'comparison_variable': 'pedestrian_departure_s', 'engineering': knobs,
            'trigger': trigger, 'status': 'unselected_cpu_construction_plan_no_native_proof',
            'actual_driver_yield_measured': False, 'impossibility_to_yield_proven': False}


def synthetic_trigger_metrics(folder):
    rows = [json.loads(line) for line in (Path(folder) / 'curb-samples.jsonl').read_text().splitlines()
            if line.strip()]
    front = max(point[0] for point in rows[0]['pedestrian_footprint_xy_m'])
    return {'synthetic_spawn_clearance_m': round(-3.5 - front, 3),
            'physical_spawn_clearance_m': None, 'physical_departure_acceleration_mps2': None,
            'original_pixel_visibility_fraction': None,
            'scope': 'synthetic geometry only; Native trigger events unmeasured'}


def build():
    paths = []
    for suffix in ('probe_1', 'probe_2'):
        plans = [candidate(suffix, ident) for ident in IDS]
        if len({json.dumps(plan['engineering'], sort_keys=True) for plan in plans}) != 4:
            raise ValueError('Curb candidate knobs are not distinct')
        for plan in plans:
            path = HERE / 'draft-candidates' / suffix / plan['candidate_id'] / 'construction.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(plan, indent=2) + '\n')
            paths.append(str(path.relative_to(HERE)))
    summary = {'format': 'c230222-curb-engineering-plans-v1',
               'unselected_candidate_plans': len(paths), 'paths': paths,
               'synthetic_trigger_metrics': synthetic_trigger_metrics(
                   Path(json.loads((HERE / 'curb-summary.json').read_text())['records'][0]['retained_positive'])),
               'physically_measured_triggers': 0, 'selected_cases': 0}
    (HERE / 'curb-engineering-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


if __name__ == '__main__':
    print(json.dumps(build()))
