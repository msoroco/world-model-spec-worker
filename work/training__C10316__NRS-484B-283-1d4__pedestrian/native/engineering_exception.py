"""Unselected physical construction alternatives for the prior-entry exception pair."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
BASE = 'training__C10316__NRS-484B-283-1d4__pedestrian'
IDS = ('primary', 'fallback1', 'fallback2', 'fallback3')


def evaluate_fallbacks(samples_path, context_path, pixel_audit_path=None):
    """Evaluate proposed fallback gates against exact saved source receipts.

    A synthetic audit exercises the decision logic only. Original-pixel audits
    are required before any result can describe a physical trigger.
    """
    from exception import measure

    samples_path, context_path = Path(samples_path), Path(context_path)
    observed = measure(samples_path, context_path)
    context = json.loads(context_path.read_text())
    first = json.loads(next(line for line in samples_path.read_text().splitlines() if line.strip()))
    origin = context['near_highway_edge_xy_m']
    direction = context['crossing_forward_xy']
    projections = [sum((vertex[i] - origin[i]) * direction[i] for i in (0, 1))
                   for vertex in first['pedestrian_footprint_xy_m']]
    spawn_clearance = round(-max(projections), 4)
    if not math.isfinite(spawn_clearance):
        raise ValueError('Saved spawn clearance invalid')
    gates = {'fallback1': {'metric': 'native_spawn_clearance_m_below',
                           'observed': spawn_clearance, 'threshold': 1.25,
                           'advance': spawn_clearance < 1.25,
                           'source': 'original_native_footprint_and_authored_road_edge'}}
    if pixel_audit_path is not None:
        pixel_audit_path = Path(pixel_audit_path)
        receipt = json.loads(pixel_audit_path.read_text())
        if receipt.get('source_sha256') != observed['source_sha256']:
            raise ValueError('Display audit source hashes differ')
        kind = receipt.get('audit_kind')
        if kind not in ('synthetic_diagnostic', 'independent_original_pixel_audit'):
            raise ValueError('Display audit provenance invalid')
        if kind == 'independent_original_pixel_audit':
            if observed['source_kind'] != 'native_observation':
                raise ValueError('Original pixel audit needs Native source')
            rows = [json.loads(line) for line in samples_path.read_text().splitlines() if line.strip()]
            hashes = receipt.get('display_frame_sha256')
            if not isinstance(hashes, list) or hashes != [row['original_display_frame_sha256'] for row in rows]:
                raise ValueError('Original display frame hashes differ')
        skew = receipt.get('phase_skew_ms')
        legibility = receipt.get('display_legibility')
        if (type(skew) not in (int, float) or not math.isfinite(skew) or skew < 0 or
                type(legibility) not in (int, float) or not math.isfinite(legibility) or
                not 0 <= legibility <= 1):
            raise ValueError('Display audit metric invalid')
        gates.update({
            'fallback2': {'metric': 'original_prior_entry_phase_skew_ms_above',
                          'observed': skew, 'threshold': 25,
                          'advance': skew > 25,
                          'source': 'original_display_pixels_and_native_timestamp'},
            'fallback3': {'metric': 'original_prior_entry_display_legibility_below',
                          'observed': legibility, 'threshold': .95,
                          'advance': legibility < .95,
                          'source': 'independent_original_display_pixel_audit'},
        })
    return {'format': 'c10316-prior-entry-fallback-evaluation-v1',
            'source_sha256': observed['source_sha256'],
            'pixel_audit_sha256': (hashlib.sha256(pixel_audit_path.read_bytes()).hexdigest()
                                   if pixel_audit_path is not None else None),
            'audit_kind': (receipt['audit_kind'] if pixel_audit_path is not None else None),
            'physical_triggers_observed': False,
            'gates': gates, 'legal_verdict_claimed': False}


def candidate(suffix, ident):
    if suffix not in ('exception_1_1', 'exception_1_2') or ident not in IDS:
        raise ValueError('Unknown prior-entry case or candidate')
    entry_program = 'flashing_no_countdown' if suffix == 'exception_1_1' else 'walk'
    knobs = {'spawn_start_x_m': -4.5, 'capture_start_x_m': -4.5,
             'pre_roll_s': 0.0, 'walker_speed_mps': 8.14/8,
             'steady_start_s': 4.0, 'entry_program': entry_program,
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
        trigger = {'metric': 'original_prior_entry_phase_skew_ms_above',
                   'source': 'original_display_pixels_and_native_timestamp', 'threshold': 25}
    elif ident == 'fallback3':
        knobs.update(display_camera_distance_m=3.5)
        trigger = {'metric': 'original_prior_entry_display_legibility_below',
                   'source': 'independent_original_display_pixel_audit', 'threshold': .95}
    return {'case_id': BASE + '__' + suffix, 'candidate_id': ident,
            'law_id': 'NRS-484B-283-1d4', 'cell_id': 'C10316', 'actor': 'pedestrian',
            'duration_s': 12, 'rate_hz': 20, 'road_source': 'native/road.xodr',
            'crosswalk_id': 'C10316-authored-alley-crosswalk',
            'comparison_variable': 'prior_entry_indication_before_steady',
            'engineering': knobs, 'trigger': trigger,
            'status': 'unselected_cpu_construction_plan_without_native_runner_proof'}


def build():
    paths = []
    for suffix in ('exception_1_1', 'exception_1_2'):
        plans = [candidate(suffix, ident) for ident in IDS]
        assert len({json.dumps(plan['engineering'], sort_keys=True) for plan in plans}) == 4
        for plan in plans:
            path = HERE / 'draft-candidates' / suffix / plan['candidate_id'] / 'construction.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(plan, indent=2) + '\n')
            paths.append(str(path.relative_to(HERE)))
    return {'unselected_exception_candidate_plans': len(paths), 'paths': paths,
            'physically_measured_triggers': 0, 'selected_cases': 0}


if __name__ == '__main__':
    print(json.dumps(build()))
