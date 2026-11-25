"""Create CPU-only Native-shaped traces and prove audit rejection branches."""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from audit_original_speed import audit, compare
from speed import requested


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, separators=(',', ':'))+'\n' for row in rows))


def rejects(action, message):
    try:
        action()
    except ValueError as exc:
        if message not in str(exc):
            raise AssertionError(str(exc)) from exc
    else:
        raise AssertionError('Altered bicycle source accepted: ' + message)


def case(root, condition):
    here = root/condition
    here.mkdir()
    source = requested(condition)
    trace, mapping = [], []
    for index, item in enumerate(source):
        current_x = item['bicycle_center_xy_m'][0]
        previous_x = source[index-1]['bicycle_center_xy_m'][0] if index else current_x
        native = 1000 + index
        trace.append({'sample_index': index, 'native_frame': native,
            'time_s': item['time_s'], 'source_kind': 'synthetic_native_mock',
            'blueprint': 'vehicle.bh.crossbike', 'actor_id': 71,
            'condition': condition, 'fixed_conditions_id': 'c111325-dry-clear-stop-v1',
            'center_xy_m': item['bicycle_center_xy_m'],
            'velocity_xy_mps': [round((current_x-previous_x)*20, 6), 0.0],
            'legal_verdict': None})
        mapping.append({'video_frame': index, 'native_frame': native,
            'time_s': item['time_s'], 'camera_native_frames': {name: native for name in
                ('overview', 'approach', 'reference_corner', 'driver_reference')}})
    context = {'source_kind': 'synthetic_native_mock', 'cell_id': 'C111325',
        'law_id': 'LVMC-11-40-130', 'actor': 'cycle_or_scooter_operator',
        'bicycle_blueprint': 'vehicle.bh.crossbike',
        'stop_sign_governs_route': True, 'approach_lane_verified': True,
        'municipal_jurisdiction_review_pending': True,
        'fixed_conditions_id': 'c111325-dry-clear-stop-v1',
        'legal_prudence_verdict': None}
    tp, mp, cp = here/'trace.jsonl', here/'video_frames.jsonl', here/'context.json'
    write_rows(tp, trace)
    write_rows(mp, mapping)
    cp.write_text(json.dumps(context)+'\n')
    return trace, mapping, context, tp, mp, cp


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='c111325-speed-audit-') as tmp:
        root = Path(tmp)
        a = case(root, 'condition_a')
        b = case(root, 'condition_b')
        measured_a = audit(a[3], a[4], a[5], diagnostic=True)
        measured_b = audit(b[3], b[4], b[5], diagnostic=True)
        pair = compare(measured_a, measured_b)
        rejects(lambda: audit(a[3], a[4], a[5]), 'Missing bicycle law or Native')
        a[0][100]['actor_id'] = 72
        write_rows(a[3], a[0])
        rejects(lambda: audit(a[3], a[4], a[5], diagnostic=True), 'actor or speed condition')
        a[0][100]['actor_id'] = 71
        write_rows(a[3], a[0])
        a[1][200]['camera_native_frames']['approach'] += 1
        write_rows(a[4], a[1])
        rejects(lambda: audit(a[3], a[4], a[5], diagnostic=True), 'four-camera frame join')
        a[1][200]['camera_native_frames']['approach'] -= 1
        write_rows(a[4], a[1])
        a[2]['fixed_conditions_id'] = 'different'
        a[5].write_text(json.dumps(a[2])+'\n')
        for row in a[0]:
            row['fixed_conditions_id'] = 'different'
        write_rows(a[3], a[0])
        changed = audit(a[3], a[4], a[5], diagnostic=True)
        rejects(lambda: compare(changed, measured_b), 'changed fixed conditions')
        a[2]['fixed_conditions_id'] = 'c111325-dry-clear-stop-v1'
        a[5].write_text(json.dumps(a[2])+'\n')
        for row in a[0]:
            row['fixed_conditions_id'] = 'c111325-dry-clear-stop-v1'
        a[0][300]['center_xy_m'] = [1.0, -1.75]
        write_rows(a[3], a[0])
        rejects(lambda: audit(a[3], a[4], a[5], diagnostic=True), 'crossed stop position')
    script = Path(__file__).with_name('audit_original_speed.py')
    proof = {'format': 'c111325-speed-independent-audit-cpu-v1', 'passed': True,
             'auditor_sha256': hashlib.sha256(script.read_bytes()).hexdigest(),
             'conditions': [measured_a, measured_b], 'comparison': pair,
             'negative_checks': 5, 'synthetic_mock_only': True,
             'legal_prudence_verdict': None}
    Path(args.output).write_text(json.dumps(proof, indent=2)+'\n')
    print(json.dumps({'passed': True, 'conditions': 2, 'negative_checks': 5}))


if __name__ == '__main__':
    main()
