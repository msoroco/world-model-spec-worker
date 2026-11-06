"""Unselected no-countdown Native capture alternatives and measured trigger rules."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
BASE = 'training__C10316__NRS-484B-283-1d3__pedestrian'
IDS = ('primary', 'fallback1', 'fallback2', 'fallback3')


def candidate(suffix, ident):
    if suffix not in ('controlled_1', 'controlled_2') or ident not in IDS:
        raise ValueError('Unknown no-countdown case or candidate')
    start = 2.0 if suffix == 'controlled_1' else .5
    knobs = {'spawn_start_x_m': -4.5, 'capture_start_x_m': -4.5,
             'pre_roll_s': 0.0, 'walker_speed_mps': 8.14/8,
             'flash_start_s': start, 'steady_start_s': 9.0,
             'clock_mode': 'frame_index_20hz',
             'display_camera_distance_m': 6.0,
             'display_camera_width': 1280, 'display_camera_height': 720}
    trigger = {'metric': 'initial', 'source': 'none', 'threshold': None}
    if ident == 'fallback1':
        knobs.update(spawn_start_x_m=-6.5, pre_roll_s=round(2/(8.14/8), 6))
        trigger = {'metric': 'native_spawn_clearance_m_below',
                   'source': 'original_native_footprint_and_authored_road_edge', 'threshold': 1.25}
    elif ident == 'fallback2':
        knobs.update(clock_mode='snapshot_timestamp_20hz')
        trigger = {'metric': 'original_no_countdown_phase_skew_ms_above',
                   'source': 'original_display_pixels_and_native_timestamp', 'threshold': 25}
    elif ident == 'fallback3':
        knobs.update(display_camera_distance_m=3.5)
        trigger = {'metric': 'original_no_countdown_display_legibility_below',
                   'source': 'independent_original_display_pixel_audit', 'threshold': .95}
    return {'case_id': BASE + '__' + suffix, 'candidate_id': ident,
            'law_id': 'NRS-484B-283-1d3', 'cell_id': 'C10316', 'actor': 'pedestrian',
            'duration_s': 12, 'rate_hz': 20, 'road_source': 'native/road.xodr',
            'crosswalk_id': 'C10316-authored-alley-crosswalk',
            'comparison_variable': 'no_countdown_flash_start_s',
            'engineering': knobs, 'trigger': trigger,
            'status': 'unselected_cpu_construction_plan_no_native_display_proof'}


def synthetic_trigger_metrics(folder):
    rows = [json.loads(line) for line in (Path(folder) / 'no-countdown-samples.jsonl').read_text().splitlines()
            if line.strip()]
    front = max(point[0] for point in rows[0]['pedestrian_footprint_xy_m'])
    clearance = -3.5 - front
    return {'synthetic_spawn_clearance_m': round(clearance, 3),
            'physical_spawn_clearance_m': None,
            'original_phase_skew_ms': None,
            'original_pixel_legibility_fraction': None,
            'scope': 'synthetic geometry only; Native trigger events unmeasured'}


def build():
    paths = []
    for suffix in ('controlled_1', 'controlled_2'):
        plans = [candidate(suffix, ident) for ident in IDS]
        assert len({json.dumps(plan['engineering'], sort_keys=True) for plan in plans}) == 4
        assert len({(plan['case_id'], plan['law_id'], plan['cell_id'], plan['actor'],
                     plan['duration_s'], plan['rate_hz']) for plan in plans}) == 1
        for plan in plans:
            path = HERE / 'draft-candidates' / suffix / plan['candidate_id'] / 'construction.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(plan, indent=2) + '\n')
            paths.append(str(path.relative_to(HERE)))
    return {'unselected_candidate_plans': len(paths), 'paths': paths,
            'physically_measured_triggers': 0, 'selected_cases': 0}


if __name__ == '__main__':
    print(json.dumps(build()))
