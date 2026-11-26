"""Exercise each feature and exception branch with source-shaped CPU packets."""
import copy
import json
from pathlib import Path

from measure_feature import measure, sha

REPO = Path(__file__).resolve().parents[3]
ROOT = Path(__file__).resolve().parents[1]
OUT = REPO / '.runtime-work/c230259-nrs213/feature-source-proof'


def packet(label, kind, left, directionality):
    folder = OUT / label
    folder.mkdir(parents=True, exist_ok=True)
    road = folder / 'road.json'
    trace = folder / 'trace.jsonl'
    road.write_text(json.dumps({
        'feature_kind': kind, 'feature_start_s_m': 80, 'feature_end_s_m': 105,
        'road_geometry_sha256': 'source-shaped-test-road',
        'directionality': directionality, 'centerline_source': 'illustrative OpenDRIVE readback',
        'grade_profile_source': 'illustrative elevation readback' if kind == 'crest' else None,
        'curvature_source': 'illustrative planView arc readback' if kind == 'curve' else None}, sort_keys=True) + '\n')
    with trace.open('w') as stream:
        for index in range(600):
            inside_left = left and 220 <= index < 350
            row = {'frame': index, 'ego_id': 'ego', 'ego_s_m': 35 + index * .15,
                   'ego_forward_mps': 3, 'ego_body_min_signed_m': -1 if inside_left else 1,
                   'ego_body_max_signed_m': 1 if inside_left else 3,
                   'sight_clear_m': 30 if 220 <= index < 380 else 200,
                   'available_forward_road_m': 90,
                   'sight_censored': 220 <= index < 380,
                   'camera_frame_ids': {name: index for name in
                                        ('overview', 'approach', 'reference_corner', 'driver_reference')},
                   'map_waypoint_source': 'illustrative source frame ' + str(index),
                   'other_vehicle_id': 'peer',
                   'other_vehicle_route_direction': 'same' if directionality == 'one_way' else 'opposing',
                   'other_vehicle_s_m': 140 - index * .05 if directionality == 'two_way' else 120 + index * .05}
            stream.write(json.dumps(row, sort_keys=True) + '\n')
    return trace, road


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    scenarios = [('crest_right', 'crest', False, 'two_way'),
                 ('crest_left', 'crest', True, 'two_way'),
                 ('curve_right', 'curve', False, 'two_way'),
                 ('curve_left', 'curve', True, 'two_way'),
                 ('one_way_crest', 'crest', True, 'one_way'),
                 ('one_way_curve', 'curve', True, 'one_way')]
    values = {}
    for name, kind, left, direction in scenarios:
        trace, road = packet(name, kind, left, direction)
        values[name] = measure(trace, road)
        assert values[name]['feature_kind'] == kind
        assert values[name]['one_way_exception_context'] == (direction == 'one_way')
    for name in ('crest_right', 'curve_right'):
        assert values[name]['active_left_obscured_frame_count'] == 0
    for name in ('crest_left', 'curve_left', 'one_way_crest', 'one_way_curve'):
        assert values[name]['active_left_obscured_frame_count'] > 0
    negatives = []
    trace, road = packet('damaged', 'curve', True, 'two_way')
    for name in ('missing_frame', 'missing_camera', 'missing_sight', 'missing_curve', 'contradict_one_way'):
        damaged_trace = OUT / (name + '.jsonl')
        damaged_road = OUT / (name + '.json')
        rows = [json.loads(line) for line in trace.read_text().splitlines()]
        road_obj = json.loads(road.read_text())
        if name == 'missing_frame':
            rows.pop(240)
        elif name == 'missing_camera':
            rows[240]['camera_frame_ids'].pop('driver_reference')
        elif name == 'missing_sight':
            rows[240].pop('sight_clear_m')
        elif name == 'missing_curve':
            road_obj['curvature_source'] = None
        else:
            road_obj['directionality'] = 'one_way'
        damaged_trace.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
        damaged_road.write_text(json.dumps(road_obj, sort_keys=True) + '\n')
        try:
            measure(damaged_trace, damaged_road)
        except ValueError as error:
            negatives.append({'name': name, 'rejected': str(error)})
        else:
            raise AssertionError('damaged original source accepted: ' + name)
    proof = {'format': 'worker-feature-source-proof-v1', 'assignment_id': ROOT.name,
             'meter_sha256': sha(ROOT / 'native/measure_feature.py'),
             'scenarios': values, 'negative_rejections': negatives,
             'source_kind': 'source-shaped CPU fixture, not original Native observation',
             'original_native_observed': False}
    target = ROOT / 'native/feature-source-proof.json'
    target.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'positive': len(values), 'negative': len(negatives), 'proof_sha256': sha(target)}))


if __name__ == '__main__':
    main()
