"""Construct and check full-duration diagnostic yellow/red source histories.

The generated rows are synthetic checker inputs, never Native observations.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from red_entry_measurements import analyze
from yellow_red_policy import CASES, DURATION_FRAMES, RATE_HZ, RED_START, signal_state

ROOT = REPO / '.runtime-work/c158196-yellow-red-source-proof'
POLYGON = [[-8.0, -8.0], [8.0, -8.0], [8.0, 8.0], [-8.0, 8.0]]
CONTEXT = {'native_map_id': 'synthetic_one_way_to_two_way_fixture',
           'intersection_id': 158196, 'native_signal_id': 3076,
           'governed_road_id': 158190, 'governed_lane_id': -1,
           'signal_head_video_source': 'diagnostic_fixture_only',
           'lane_governance_source': 'diagnostic_fixture_only',
           'intersection_polygon_xy_m': POLYGON,
           'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def body(center_x):
    return [[round(center_x - 2.0, 6), -1.0],
            [round(center_x - 2.0, 6), 1.0],
            [round(center_x + 2.0, 6), 1.0],
            [round(center_x + 2.0, 6), -1.0]]


def position(case, frame):
    target = CASES[case]
    if target is None:
        return -28.75 + 0.125 * min(frame, 100)
    return min(-10.0 + 0.125 * (frame - target), 14.0)


def construct(case):
    root = ROOT / case
    root.mkdir(parents=True, exist_ok=True)
    (root / 'junction_context.json').write_text(json.dumps(CONTEXT, indent=2) + '\n')
    rows, frames = [], []
    for frame in range(DURATION_FRAMES):
        pos = position(case, frame)
        prior = position(case, max(0, frame - 1))
        when = frame / RATE_HZ
        rows.append({'frame': frame, 'time_s': when, 'native_signal_id': CONTEXT['native_signal_id'],
                     'road_id': CONTEXT['governed_road_id'], 'lane_id': CONTEXT['governed_lane_id'],
                     'signal_state': signal_state(frame), 'ego_body_vertices_xy_m': body(pos),
                     'ego_speed_mps': round((pos - prior) * RATE_HZ, 6)})
        frames.append({'video_frame': frame, 'carla_frame': frame, 'time_s': when})
    for name, values in [('signal_vehicle_history.jsonl', rows), ('video_frames.jsonl', frames)]:
        (root / name).write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in values))
    return root


def reject_changed_frame_map(root):
    broken = ROOT / 'negative_stale_frame_map'
    if broken.exists():
        shutil.rmtree(broken)
    shutil.copytree(root, broken)
    path = broken / 'video_frames.jsonl'
    lines = path.read_text().splitlines()
    row = json.loads(lines[RED_START])
    row['carla_frame'] += 1
    lines[RED_START] = json.dumps(row, separators=(',', ':'))
    path.write_text('\n'.join(lines) + '\n')
    try:
        analyze(broken)
    except ValueError as error:
        if 'Original video frame join failed' not in str(error):
            raise
        return str(error)
    raise AssertionError('Changed frame map was accepted')


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    observations = []
    sequences = {}
    for case, target in CASES.items():
        root = construct(case)
        result = analyze(root)
        entry = result['first_body_entry']
        actual = None if entry is None else entry['frame']
        if actual != target or result['yellow_to_red_onset']['frame'] != RED_START:
            raise AssertionError(f'{case}: entry {actual}, red {result["yellow_to_red_onset"]}')
        expected_red = target is not None and target >= RED_START
        if result['entry_with_red_exhibited_observed'] != (None if target is None else expected_red):
            raise AssertionError('Observed red-entry classification differs')
        sequences[case] = result['samples']
        observations.append({'case_id': 'testing__C158196__NRS-484B-307-6a__motor_vehicle_driver__' + case,
                             'source_root': str(root.relative_to(REPO)), 'source_sha256': result['sources'],
                             'sample_count': len(result['samples']), 'red_onset_frame': RED_START,
                             'entry_frame': actual, 'entry_minus_red_onset_s': result['entry_minus_red_onset_s'],
                             'red_exhibited_at_entry': result['entry_with_red_exhibited_observed']})
    reference = sequences['entry_before_red']
    for case, samples in sequences.items():
        if [row['signal_state'] for row in samples] != [row['signal_state'] for row in reference]:
            raise AssertionError('Signal schedule differs across planned comparisons')
        if case != 'stops_on_yellow' and [row['ego_speed_mps'] for row in samples[1:100]] != [2.5] * 99:
            raise AssertionError('Compared entry cases have different approach speeds')
    if (sequences['stops_on_yellow'][1:100] != reference[1:100] or
            any(row['ego_speed_mps'] != 0 for row in sequences['stops_on_yellow'][101:])):
        raise AssertionError('Yellow stop fixture differs before warning or moves after braking')
    negative = reject_changed_frame_map(ROOT / 'entry_at_red')
    report = {'format': 'worker-yellow-red-source-diagnostic', 'provenance_kind': 'synthetic_fixture',
              'physical_acceptance_claimed': False, 'sample_rate_hz': RATE_HZ,
              'observations': observations, 'negative_stale_frame_map': negative,
              'limitation': 'Synthetic source joins only; no Native head, lane governance, pixels or motion.'}
    output = HERE / 'red-entry-source-diagnostic.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'cases': len(observations), 'frames_each': DURATION_FRAMES,
                      'entry_frames': [v['entry_frame'] for v in observations],
                      'negative': negative, 'report_sha256': sha(output)}))


if __name__ == '__main__':
    main()
