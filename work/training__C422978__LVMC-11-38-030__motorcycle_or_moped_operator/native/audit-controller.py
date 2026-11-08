"""Independently integrate retained control commands and audit eight CPU paths."""
import copy
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def near(actual, expected, tolerance=.005):
    if abs(actual-expected) > tolerance:
        raise AssertionError(f'Controller integration differs: {actual} versus {expected}')


def audit_path(rows, requested, model):
    assert len(rows) == len(requested) == 480
    dt = model['dt_s']
    x, y, yaw, speed = 10.0, 1.75, 0.0, 0.0
    overlaps = []
    lateral = []
    for index, (row, request) in enumerate(zip(rows, requested)):
        assert row['frame'] == index and request['frame'] == index
        near(row['time_s'], index*dt, 1e-6)
        target = requested[min(479, index+15)]['requested_center_xy_m']
        assert row['target_native_xy_m'] == [target[0], -target[1]]
        assert row['requested_native_xy_m'] == [request['requested_center_xy_m'][0],
                                                -request['requested_center_xy_m'][1]]
        throttle, brake, steer = (row[name] for name in ('throttle', 'brake', 'steer'))
        assert 0 <= throttle <= 1 and 0 <= brake <= 1 and -.8 <= steer <= .8
        speed = max(0.0, speed + (3*throttle - 5*brake - .05*speed)*dt)
        yaw += speed/model['wheelbase_m']*math.tan(steer*math.radians(model['max_steer_deg']))*dt
        x += speed*math.cos(yaw)*dt
        y += speed*math.sin(yaw)*dt
        near(row['speed_mps'], speed, .001)
        near(row['heading_deg'], math.degrees(yaw), .02)
        near(row['center_native_xy_m'][0], x)
        near(row['center_native_xy_m'][1], y)
        expected_body = [[x+dx*math.cos(yaw)-dy*math.sin(yaw),
                          y+dx*math.sin(yaw)+dy*math.cos(yaw)]
                         for dx, dy in ((-model['body_length_m']/2,-model['body_width_m']/2),
                                        (-model['body_length_m']/2,model['body_width_m']/2),
                                        (model['body_length_m']/2,-model['body_width_m']/2),
                                        (model['body_length_m']/2,model['body_width_m']/2))]
        for actual, expected in zip(row['body_native_xy_m'], expected_body):
            near(actual[0], expected[0])
            near(actual[1], expected[1])
        ys = [point[1] for point in row['body_native_xy_m']]
        overlap = speed > .1 and min(ys) < 5.5 and max(ys) > 3.5
        assert row['moving_sidewalk_overlap'] is overlap
        if overlap: overlaps.append(index)
        if index >= 160:
            lateral.append(abs(row['center_native_xy_m'][1]-row['requested_native_xy_m'][1]))
    return {'first_moving_sidewalk_overlap_frame': overlaps[0] if overlaps else None,
            'moving_sidewalk_overlap_frames': len(overlaps),
            'terminal_x_m': rows[-1]['center_native_xy_m'][0],
            'terminal_y_m': rows[-1]['center_native_xy_m'][1],
            'terminal_speed_mps': rows[-1]['speed_mps'],
            'max_lateral_error_after_frame_160_m': round(max(lateral), 5)}


def main():
    proof = json.loads((HERE / 'controller-proof.json').read_text())
    assert proof['format'] == 'c422978-cpu-controller-model-proof-v1'
    assert proof['runner_sha256'] == sha(HERE / 'runner.py')
    assert proof['draft_manifest_sha256'] == sha(HERE / 'drafts/manifest.json')
    assert not proof['original_native_observed'] and not proof['carla_run'] and not proof['delivery_ready']
    assert len(proof['receipts']) == 8
    indexed = {}
    for receipt in proof['receipts']:
        case, candidate = receipt['case_suffix'], receipt['candidate_id']
        assert case in ('witness_1', 'witness_2')
        assert candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')
        folder = HERE / 'drafts' / case / candidate
        source = HERE / 'controller-fixtures' / case / (candidate + '.jsonl')
        assert receipt['config_sha256'] == sha(folder / 'config.json')
        assert receipt['request_sha256'] == sha(folder / 'requested-tracks.jsonl')
        assert receipt['trajectory_sha256'] == sha(source)
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        requested = [json.loads(line) for line in (folder / 'requested-tracks.jsonl').read_text().splitlines()]
        measured = audit_path(rows, requested, proof['model'])
        assert all(receipt[key] == value for key, value in measured.items())
        assert measured['terminal_x_m'] > 100
        assert measured['max_lateral_error_after_frame_160_m'] < .4
        indexed[case, candidate] = measured
        if case == 'witness_1': assert measured['moving_sidewalk_overlap_frames'] == 0
        else: assert measured['moving_sidewalk_overlap_frames'] >= 375
    assert len(indexed) == 8
    first = lambda candidate: indexed['witness_2',candidate]['first_moving_sidewalk_overlap_frame']
    assert first('fallback1') < first('primary') < first('fallback2')
    folder = HERE / 'drafts/witness_2/primary'
    rows = [json.loads(line) for line in (HERE / 'controller-fixtures/witness_2/primary.jsonl').read_text().splitlines()]
    requested = [json.loads(line) for line in (folder / 'requested-tracks.jsonl').read_text().splitlines()]
    bad = copy.deepcopy(rows)
    bad[90]['steer'] += .2
    try: audit_path(bad, requested, proof['model'])
    except AssertionError: pass
    else: raise AssertionError('Changed steering command passed independent integration')
    bad = copy.deepcopy(rows)
    bad[90]['target_native_xy_m'][1] += 1
    try: audit_path(bad, requested, proof['model'])
    except AssertionError: pass
    else: raise AssertionError('Changed lookahead target passed independent integration')
    result = {'format': 'c422978-independent-controller-model-audit-v1',
              'proof_sha256': sha(HERE / 'controller-proof.json'),
              'trajectories_audited': 8, 'frames_per_trajectory': 480,
              'changed_steer_rejected': True, 'changed_target_rejected': True,
              'original_native_observed': False, 'carla_run': False,
              'delivery_ready': False}
    (HERE / 'controller-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
