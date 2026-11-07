"""Unselected Native-coordinate requests for the yellow-to-red entry pair."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
AID = HERE.parent.name
CASES = ('reference', 'contrast')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
SEED = REPO / 'work/training__C110919__NRS-484B-307-8a__motor_vehicle_driver/native/road.xodr'
ENTRANCE_Y = -7.0
YELLOW_START = 150


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def knobs(candidate):
    return {
        'primary': {'speed_m_per_frame': .35, 'reference_red_frame': 240,
                    'contrast_red_frame': 190, 'signal_camera_fov_deg': 60},
        'fallback1': {'speed_m_per_frame': .35, 'reference_red_frame': 260,
                      'contrast_red_frame': 175, 'signal_camera_fov_deg': 60},
        'fallback2': {'speed_m_per_frame': .32, 'reference_red_frame': 240,
                      'contrast_red_frame': 190, 'signal_camera_fov_deg': 60},
        'fallback3': {'speed_m_per_frame': .35, 'reference_red_frame': 240,
                      'contrast_red_frame': 190, 'signal_camera_fov_deg': 82},
    }[candidate]


def proposal(case, candidate):
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError('Unknown controlled case or candidate')
    k = knobs(candidate)
    red_frame = k[case + '_red_frame']
    rows = []
    for frame in range(480):
        authored_y = -80 + k['speed_m_per_frame'] * frame
        # Northbound full body first enters the junction at its leading edge.
        front_y = authored_y + 2.25
        phase = ('green' if frame < YELLOW_START else
                 'yellow' if frame < red_frame else 'red')
        rows.append({'frame': frame, 'time_s': round(frame / 20, 4),
                     'source_kind': 'authored_cpu_request',
                     'native_center_xy_m': [1.75, round(-authored_y, 5)],
                     'native_body_xy_m': [[x, round(-y, 5)] for x, y in
                                          ((.85, authored_y - 2.25),
                                           (2.65, authored_y - 2.25),
                                           (.85, front_y), (2.65, front_y))],
                     'signal_phase_requested': phase,
                     'signal_red_start_requested_frame': red_frame,
                     'actual_signal_phase_observed': None,
                     'actual_intersection_entry_observed': None,
                     'intersection_entrance_authored_y_m': ENTRANCE_Y,
                     'camera_fov_deg': k['signal_camera_fov_deg']})
    entry = next(i for i, row in enumerate(rows)
                 if -min(v[1] for v in row['native_body_xy_m']) >= ENTRANCE_Y)
    phase_at_entry = rows[entry]['signal_phase_requested']
    assert phase_at_entry == ('yellow' if case == 'reference' else 'red')
    # Projection of the authored signal head from the fixed camera site at entry.
    camera_xy = (1.75, -17.0)
    signal_xy = (3.5, -13.0)
    angle = math.degrees(math.atan2(abs(signal_xy[0] - camera_xy[0]),
                                    signal_xy[1] - camera_xy[1]))
    fov_margin = k['signal_camera_fov_deg'] / 2 - angle
    metrics = {'requested_full_body_entry_frame': entry,
               'requested_phase_at_entry': phase_at_entry,
               'requested_red_start_frame': red_frame,
               'entry_to_red_margin_frames': red_frame - entry,
               'authored_signal_camera_angle_deg': round(angle, 4),
               'authored_fov_margin_deg': round(fov_margin, 4),
               'physical_signal_phase_verified': False,
               'original_pixel_visibility_verified': False}
    return rows, k, metrics


def build():
    # Reuse only work-owned intersection geometry as an authored seed.
    xml = SEED.read_text().replace('C110919', 'C111331').replace(
        'south-approach-circular-red', 'south-approach-yellow-red-head')
    road = HERE / 'road.xodr'
    road.write_text(xml)
    parsed = ET.fromstring(xml)
    assert len(parsed.findall('.//junction')) >= 1
    assert any(s.get('id') == '601' for s in parsed.findall('.//signal'))
    summary = {'format': 'c111331-unselected-native-requests-v1',
               'assignment_id': AID, 'road_sha256': sha(road),
               'seed_road_sha256': sha(SEED), 'cases': []}
    for case in CASES:
        for candidate in CANDIDATES:
            rows, k, metrics = proposal(case, candidate)
            folder = HERE / 'drafts' / case / candidate
            folder.mkdir(parents=True, exist_ok=True)
            request = folder / 'native-requests.jsonl'
            request.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
            trigger = {
                'primary': {'metric': 'requested_phase_at_entry',
                            'operator': 'equals', 'target': 'yellow' if case == 'reference' else 'red',
                            'measured': metrics['requested_phase_at_entry']},
                'fallback1': {'metric': 'entry_to_red_margin_frames',
                              'operator': 'at_least' if case == 'reference' else 'at_most',
                              'target': 50 if case == 'reference' else -20,
                              'measured': metrics['entry_to_red_margin_frames']},
                'fallback2': {'metric': 'requested_full_body_entry_frame',
                              'operator': 'at_least', 'target': 220,
                              'measured': metrics['requested_full_body_entry_frame']},
                'fallback3': {'metric': 'authored_fov_margin_deg',
                              'operator': 'at_least', 'target': 15,
                              'measured': metrics['authored_fov_margin_deg']},
            }[candidate]
            config = {'case_id': AID + '__' + case, 'candidate_id': candidate,
                      'status': 'unselected_cpu_request', 'frozen_cell': {
                          'layout': 'intersection', 'maneuver': 'travel',
                          'control': 'traffic_light'},
                      'road_sha256': sha(road), 'knobs': k, 'metrics': metrics,
                      'camera_plan': {'authored_xy_m': [1.75, -17.0],
                                      'signal_head_authored_xy_m': [3.5, -13.0],
                                      'horizontal_fov_deg': k['signal_camera_fov_deg']},
                      'measured_trigger': trigger,
                      'assignment_source_sha256': sha(REPO / 'inputs' / AID / 'assignment.json'),
                      'no_native_or_original_observation_claimed': True}
            (folder / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
            summary['cases'].append({'case': case, 'candidate': candidate,
                                     'request_sha256': sha(request),
                                     'config_sha256': sha(folder / 'config.json'),
                                     'metrics': metrics})
    (HERE / 'request-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return {'cases': 2, 'candidate_bundles': 8,
            'summary_sha256': sha(HERE / 'request-summary.json')}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
