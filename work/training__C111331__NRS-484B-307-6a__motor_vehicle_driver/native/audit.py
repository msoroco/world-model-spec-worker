"""Independent source and controlled-pair audit for unselected signal requests."""
import copy
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
AID = HERE.parent.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def verify_case(rows_, config):
    if len(rows_) != 480:
        raise ValueError('Request frame count differs')
    red = config['knobs'][config['case_id'].rsplit('__', 1)[1] + '_red_frame']
    prior = None
    entry = None
    for i, row in enumerate(rows_):
        if row['frame'] != i or row['time_s'] != round(i / 20, 4):
            raise ValueError('Request frame/time join differs')
        if row['actual_signal_phase_observed'] is not None or \
                row['actual_intersection_entry_observed'] is not None:
            raise ValueError('Requested state promoted to observation')
        phase = 'green' if i < 150 else 'yellow' if i < red else 'red'
        if row['signal_phase_requested'] != phase:
            raise ValueError('Requested signal phase differs')
        x, native_y = row['native_center_xy_m']
        body = row['native_body_xy_m']
        if len(body) != 4 or \
                abs(sum(v[0] for v in body)/4 - x) > 1e-5 or \
                abs(sum(v[1] for v in body)/4 - native_y) > 1e-5:
            raise ValueError('Native body/center geometry differs')
        if prior is not None and abs(math.dist(prior, (x, native_y)) - config['knobs']['speed_m_per_frame']) > .001:
            raise ValueError('Requested pose cadence differs')
        prior = (x, native_y)
        distance = i * config['knobs']['speed_m_per_frame']
        curve_length = 5.25 * math.pi / 2
        if distance <= 73:
            expected = (1.75, -80 + distance)
            yaw = 90
        elif distance <= 73 + curve_length:
            theta = math.pi - (distance - 73) / 5.25
            expected = (7 + 5.25 * math.cos(theta), -7 + 5.25 * math.sin(theta))
            yaw = math.degrees(math.atan2(-math.cos(theta), math.sin(theta)))
        else:
            expected = (7 + distance - 73 - curve_length, -1.75)
            yaw = 0
        if math.dist((x, native_y), expected) > 1e-4 or abs(row['native_yaw_deg_requested'] - yaw) > 1e-4:
            raise ValueError('Authored approach/turn/destination route differs')
        if entry is None and max(v[1] for v in body) >= -7:
            entry = i
    if entry is None or entry != config['metrics']['requested_full_body_entry_frame'] or \
            rows_[entry]['signal_phase_requested'] != config['metrics']['requested_phase_at_entry']:
        raise ValueError('Full-body entry/phase metric differs')
    return entry


def audit():
    summary_path = HERE / 'request-summary.json'
    summary = json.loads(summary_path.read_text())
    assert summary['assignment_id'] == AID and len(summary['cases']) == 8
    plan = json.loads((HERE.parent / 'case-plan.json').read_text())
    assert plan['unselected_native_request_construction']['summary_sha256'] == sha(summary_path)
    assert plan['unselected_native_request_construction']['physical_signal_or_original_pixels_verified'] is False
    assert summary['road_sha256'] == sha(HERE / 'road.xodr')
    seed = REPO / 'work/training__C110919__NRS-484B-307-8a__motor_vehicle_driver/native/road.xodr'
    assert summary['seed_road_sha256'] == sha(seed)
    source_topics = set(json.loads((REPO / 'inputs/coverage/branch-sources.json').read_text())
                        ['laws']['NRS-484B-307-6a']['topics'])
    coverage_path = REPO / 'work/_shared/branch-coverage.json'
    branch = json.loads(coverage_path.read_text())['laws']['NRS-484B-307-6a']['branches']
    assert len(branch) == 1 and set(branch[0]['topic_ids']) == source_topics
    assert branch[0]['status'] == 'pending_review' and branch[0]['assignment_id'] == AID
    assert set(branch[0]['case_ids']) == {AID + '__reference', AID + '__contrast'}
    assert branch[0]['comparison_ids'] == [AID + '__comparison_main']
    review = json.loads((REPO / 'work/_shared/branch-review.json').read_text())
    assert review['coverage_sha256'] == sha(coverage_path)
    road = ET.parse(HERE / 'road.xodr').getroot()
    assert road.find('.//junction') is not None
    assert any(s.get('id') == '601' for s in road.findall('.//signal'))
    approach = next(r for r in road.findall('road') if r.get('id') == '1')
    turn = next(r for r in road.findall('road') if r.get('id') == '13')
    destination = next(r for r in road.findall('road') if r.get('id') == '2')
    approach_geometry = approach.find('./planView/geometry')
    turn_geometry = turn.find('./planView/geometry')
    destination_geometry = destination.find('./planView/geometry')
    assert abs(float(approach_geometry.get('y')) + 100) < 1e-9
    assert abs(float(approach_geometry.get('length')) - 93) < 1e-9
    assert abs(float(approach_geometry.get('hdg')) - math.pi/2) < 1e-9
    assert abs(float(turn_geometry.get('y')) + 7) < 1e-9
    assert abs(float(turn_geometry.find('arc').get('curvature')) + 1/7) < 1e-9
    assert abs(float(destination_geometry.get('x')) - 7) < 1e-9
    signal = next(s for s in road.findall('.//signal') if s.get('id') == '601')
    assert abs(float(signal.get('s')) - 87) < 1e-9 and abs(float(signal.get('t')) + 3.5) < 1e-9
    records = {}
    for item in summary['cases']:
        case, candidate = item['case'], item['candidate']
        folder = HERE / 'drafts' / case / candidate
        assert item['request_sha256'] == sha(folder / 'native-requests.jsonl')
        assert item['config_sha256'] == sha(folder / 'config.json')
        packet = rows(folder / 'native-requests.jsonl')
        config = json.loads((folder / 'config.json').read_text())
        assert config['case_id'] == AID + '__' + case and config['candidate_id'] == candidate
        assert config['status'] == 'unselected_cpu_request'
        assert config['assignment_source_sha256'] == sha(REPO / 'inputs' / AID / 'assignment.json')
        assert config['road_sha256'] == summary['road_sha256']
        assert config['metrics'] == item['metrics']
        camera = config['camera_plan']
        cx, cy = camera['authored_xy_m']
        sx, sy = camera['signal_head_authored_xy_m']
        angle = math.degrees(math.atan2(abs(sx-cx), sy-cy))
        assert abs(config['metrics']['authored_fov_margin_deg'] -
                   round(camera['horizontal_fov_deg']/2-angle, 4)) < 1e-5
        trigger = config['measured_trigger']
        assert trigger['measured'] == config['metrics'][trigger['metric']]
        if trigger['operator'] == 'equals':
            assert trigger['measured'] == trigger['target']
        elif trigger['operator'] == 'at_least':
            assert trigger['measured'] >= trigger['target']
        else:
            assert trigger['operator'] == 'at_most' and trigger['measured'] <= trigger['target']
        verify_case(packet, config)
        records[case, candidate] = packet, config
    assert set(records) == {(case, candidate) for case in ('reference', 'contrast')
                            for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')}
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        reference, rc = records['reference', candidate]
        contrast, cc = records['contrast', candidate]
        assert rc['metrics']['requested_phase_at_entry'] == 'yellow'
        assert cc['metrics']['requested_phase_at_entry'] == 'red'
        assert rc['metrics']['entry_to_red_margin_frames'] >= 15
        assert cc['metrics']['entry_to_red_margin_frames'] <= -10
        assert all(a['native_center_xy_m'] == b['native_center_xy_m'] and
                   a['native_body_xy_m'] == b['native_body_xy_m'] and
                   a['camera_fov_deg'] == b['camera_fov_deg']
                   for a, b in zip(reference, contrast))
    primary = records['reference', 'primary'][1]['metrics']
    assert records['reference', 'fallback1'][1]['metrics']['entry_to_red_margin_frames'] > primary['entry_to_red_margin_frames']
    assert records['reference', 'fallback2'][1]['metrics']['requested_full_body_entry_frame'] > primary['requested_full_body_entry_frame']
    assert records['reference', 'fallback3'][1]['metrics']['authored_fov_margin_deg'] > 15
    packet, config = records['contrast', 'primary']
    negatives = []
    for label, mutate, error in (
        ('phase', lambda p: p[200].update(signal_phase_requested='green'), 'Requested signal phase differs'),
        ('observation', lambda p: p[200].update(actual_signal_phase_observed='red'), 'promoted to observation'),
        ('body', lambda p: p[200]['native_body_xy_m'][0].__setitem__(1, 999), 'body/center geometry differs')):
        bad = copy.deepcopy(packet)
        mutate(bad)
        try:
            verify_case(bad, config)
        except ValueError as exc:
            assert error in str(exc)
            negatives.append(label)
        else:
            raise AssertionError('Corrupt ' + label + ' accepted')
    return {'passed': True, 'candidate_bundles': len(records),
            'paired_candidate_comparisons': 4, 'negative_rejections': negatives,
            'summary_sha256': sha(summary_path),
            'physical_or_original_pixel_observation_verified': False}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
