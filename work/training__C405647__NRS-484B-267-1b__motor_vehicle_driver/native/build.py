"""Source-bound, unselected CPU construction for the right-edge response.

Coordinates in the requests are OpenDRIVE coordinates. Native requests reflect
y for the imported CARLA world. No requested motion or light is an observation.
"""
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
AID = 'training__C405647__NRS-484B-267-1b__motor_vehicle_driver'
SOURCE = ROOT / 'inputs' / AID / 'assignment.json'
PLAN = HERE.parent / 'case-plan.json'
OUT = HERE / 'drafts'
CASES = ('reference', 'contrast')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
RATE = 20
FRAMES = 480


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def lines(rows):
    return ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows).encode()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return sha(data)


def road():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C405647-1b-edge',
                  version='1', date='2026-11-08', north='20', south='-20',
                  east='220', west='-40', vendor='full-train-worker')
    r = ET.SubElement(root, 'road', id='1', name='eastbound_without_intersection',
                      length='260', junction='-1')
    ET.SubElement(r, 'link')
    g = ET.SubElement(ET.SubElement(r, 'planView'), 'geometry',
                      s='0', x='-40', y='0', hdg='0', length='260')
    ET.SubElement(g, 'line')
    ET.SubElement(ET.SubElement(r, 'elevationProfile'), 'elevation',
                  s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(r, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(ET.SubElement(section, 'center'), 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    for ident, kind, width in ((-1, 'driving', 3.5), (-2, 'driving', 3.5),
                               (-3, 'shoulder', 2.5)):
        lane = ET.SubElement(right, 'lane', id=str(ident), type=kind, level='false')
        ET.SubElement(lane, 'width', sOffset='0', a=str(width), b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type='solid' if ident == -3 else 'broken',
                      color='white', width='0.12')
    ET.SubElement(r, 'objects')
    ET.SubElement(r, 'signals')
    return ET.tostring(root, encoding='unicode')


def knobs(candidate):
    return {
        'primary': (5, 60, 70),
        'fallback1': (1, 60, 70),
        'fallback2': (5, 40, 70),
        'fallback3': (5, 60, 100),
    }[candidate]


def requests(case, candidate):
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError('unknown case or candidate')
    start, duration, camera_fov = knobs(candidate)
    rows = []
    for frame in range(FRAMES):
        time = frame / RATE
        progress = min(1.0, max(0.0, (frame - start) / duration))
        smooth = progress * progress * (3 - 2 * progress)
        # Stop at x=48 m, well inside the authored road with no junction.
        subject_x = min(48.0, 30.0 + 3.0 * time)
        subject_y = -1.75 - (4.25 * smooth if case == 'reference' else 0.0)
        approach_x = -20.0 + 8.0 * time
        rows.append({'frame': frame, 'time_s': round(time, 4),
                     'subject_request': {'x_m': round(subject_x, 4),
                                         'y_m': round(subject_y, 4),
                                         'heading_deg': 0.0,
                                         'speed_mps': 0.0 if frame >= 120 else 3.0},
                     'approach_request': {'x_m': round(approach_x, 4),
                                          'y_m': -1.75, 'speed_mps': 8.0},
                     'lamp_request': {'flash_on': frame % 10 < 5,
                                      'qualification_unverified': True},
                     'officer_direction_request': False,
                     'signed_shoulder_permission_request': False,
                     'approach_authority_observed': False,
                     'source_kind': 'authored_cpu_request',
                     'camera_fov_deg': camera_fov})
    return rows


def metrics(rows):
    edge = next((r['frame'] for r in rows
                 if r['subject_request']['y_m'] <= -5.95), None)
    moving = next((r['frame'] for r in rows
                   if r['subject_request']['y_m'] < -1.751), None)
    catchup = next((r['frame'] for r in rows
                    if r['approach_request']['x_m'] >= r['subject_request']['x_m'] - 4.5), None)
    stop = next((r['frame'] for r in rows
                 if r['subject_request']['speed_mps'] == 0), None)
    # Authored pinhole-frustum estimate. It only chooses a camera field of view.
    fov = rows[0]['camera_fov_deg']
    visible = sum(abs(math.degrees(math.atan2(
        r['approach_request']['y_m'] + 10.0,
        r['approach_request']['x_m'] - 40.0)) - 90.0) <= fov / 2
                  for r in rows[:catchup])
    return {'first_lateral_motion_frame': moving, 'edge_target_frame': edge,
            'approach_catchup_frame': catchup, 'stop_frame': stop,
            'stop_center_xy_m': [rows[stop]['subject_request'][k] for k in ('x_m', 'y_m')],
            'edge_offset_m': round(7.0 + rows[-1]['subject_request']['y_m'], 4),
            'authored_body_outer_y_m': round(rows[-1]['subject_request']['y_m'] - 0.9, 4),
            'authored_body_enters_shoulder': rows[-1]['subject_request']['y_m'] - 0.9 < -7.0,
            'synthetic_front_lamp_frustum_frames_before_catchup': visible,
            'intersection_on_authored_road': False}


def build():
    source = SOURCE.read_bytes()
    clause = json.loads(source)['law_record']['text']
    assert 'right-hand edge' in clause and 'paved shoulder' in clause
    plan = json.loads(PLAN.read_bytes())
    assert {c['case_id'] for c in plan['cases']} == {AID + '__' + c for c in CASES}
    map_sha = write(OUT / 'road.xodr', road().encode())
    manifest = {'format': 'c405647-1b-unselected-cpu-v1', 'assignment_id': AID,
                'assignment_sha256': sha(source), 'case_plan_sha256': sha(PLAN.read_bytes()),
                'map_sha256': map_sha, 'rate_hz': RATE, 'frames': FRAMES,
                'cell': {'layout': 'road', 'maneuver': 'travel', 'control': 'emergency_vehicle'},
                'cases': [], 'native_execution_observed': False,
                'legal_result_or_shoulder_signage_verified': False}
    for candidate in CANDIDATES:
        pair = []
        for case in CASES:
            rows = requests(case, candidate)
            native = []
            for row in rows:
                copy = json.loads(json.dumps(row))
                copy['subject_request']['y_m'] *= -1
                copy['approach_request']['y_m'] *= -1
                copy['source_kind'] = 'authored_native_request'
                native.append(copy)
            folder = OUT / case / candidate
            track_sha = write(folder / 'requested-tracks.jsonl', lines(rows))
            native_sha = write(folder / 'native-requests.jsonl', lines(native))
            measured = metrics(rows)
            primary = metrics(requests('reference', 'primary'))
            reference_candidate = metrics(requests('reference', candidate))
            trigger = None
            if candidate != 'primary':
                trigger = {
                    'fallback1': {'metric': 'first_lateral_motion_frame', 'limit_frame': 2,
                                  'baseline_value': primary['first_lateral_motion_frame'],
                                  'candidate_value': reference_candidate['first_lateral_motion_frame'],
                                  'triggered': primary['first_lateral_motion_frame'] > 2},
                    'fallback2': {'metric': 'edge_target_frame', 'limit_frame': 55,
                                  'baseline_value': primary['edge_target_frame'],
                                  'candidate_value': reference_candidate['edge_target_frame'],
                                  'triggered': primary['edge_target_frame'] > 55},
                    'fallback3': {'metric': 'synthetic_front_lamp_frustum_frames_before_catchup',
                                  'limit_frames': 30,
                                  'baseline_value': primary['synthetic_front_lamp_frustum_frames_before_catchup'],
                                  'candidate_value': reference_candidate['synthetic_front_lamp_frustum_frames_before_catchup'],
                                  'triggered': primary['synthetic_front_lamp_frustum_frames_before_catchup'] < 30},
                }[candidate]
                trigger['engineering_target_only'] = True
                trigger['source_sha256'] = track_sha
                trigger['measured_on_case'] = AID + '__reference'
            config = {'format': 'c405647-1b-native-request-v1',
                      'case_id': AID + '__' + case, 'candidate_id': candidate,
                      'status': 'unselected_cpu_draft', 'assignment_sha256': sha(source),
                      'map_sha256': map_sha, 'knobs': {'lateral_start_frame': knobs(candidate)[0],
                                                     'lateral_duration_frames': knobs(candidate)[1],
                                                     'camera_fov_deg': knobs(candidate)[2]},
                      'requested_tracks_sha256': track_sha,
                      'native_requests_sha256': native_sha, 'metrics': measured,
                      'measured_trigger': trigger,
                      'camera_plan': ['overview', 'front_lamp', 'right_edge', 'rear_approach'],
                      'physical_execution_or_legal_outcome_verified': False}
            config_sha = write(folder / 'config.json', encoded(config))
            manifest['cases'].append({'case_id': config['case_id'], 'candidate_id': candidate,
                                      'config_sha256': config_sha, 'tracks_sha256': track_sha,
                                      'native_sha256': native_sha})
            pair.append(rows)
        assert all(a['approach_request'] == b['approach_request'] and
                   a['lamp_request'] == b['lamp_request'] and
                   a['officer_direction_request'] == b['officer_direction_request'] and
                   a['signed_shoulder_permission_request'] == b['signed_shoulder_permission_request']
                   for a, b in zip(*pair))
    manifest_sha = write(OUT / 'manifest.json', encoded(manifest))
    return {'case_candidates': 8, 'manifest_sha256': manifest_sha}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
