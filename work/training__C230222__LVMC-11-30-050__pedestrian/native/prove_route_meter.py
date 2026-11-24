"""CPU software fixture for source-bound full-crossing geometry and rejection paths."""
import hashlib
import json
import math
from pathlib import Path

from route_meter import measure_files

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[2] / '.runtime-work' / 'lvmc-11-30-050-route-proof'
WORK.mkdir(parents=True, exist_ok=True)
FRAMES = 600


def write_case(name, start, end, origin, opposite, crosswalks=()):
    folder = WORK / name
    folder.mkdir(parents=True, exist_ok=True)
    context = {'source_kind': 'synthetic_cpu_fixture', 'expected_frames': FRAMES,
               'origin_curb_xy_m': origin, 'opposite_curb_xy_m': opposite,
               'crosswalk_polygons_xy_m': crosswalks,
               'sampling_rate_hz': 20,
               'limitation': 'Synthetic positions test software only; no Native or legal outcome'}
    (folder / 'context.json').write_text(json.dumps(context, indent=2) + '\n')
    with (folder / 'samples.jsonl').open('w') as stream:
        for i in range(FRAMES):
            alpha = i / (FRAMES - 1)
            point = [start[j] + alpha * (end[j] - start[j]) for j in range(2)]
            stream.write(json.dumps({'native_frame': 1000 + i, 'time_s': i / 20,
                                     'pedestrian_xy_m': point}) + '\n')
    return measure_files(folder / 'samples.jsonl', folder / 'context.json', folder / 'report.json')


def close(a, b, tolerance=1e-7):
    assert abs(a-b) <= tolerance, (a,b)


def run():
    origin = [[-10.0, 0.0], [10.0, 0.0]]
    opposite = [[-10.0, 8.0], [10.0, 8.0]]
    perpendicular = write_case('perpendicular', [0, 0], [0, 8], origin, opposite)
    close(perpendicular['right_angle_deviation_deg'], 0)
    close(perpendicular['route_excess_length_m'], 0)
    diagonal = write_case('diagonal_longer', [0, 0], [3, 8], origin, opposite)
    assert diagonal['right_angle_deviation_deg'] > 19
    assert diagonal['route_excess_length_m'] > .5
    skew_target = [[-10.0, 7.0], [10.0, 9.0]]
    nearest_x = -80 / 101
    nearest_y = 8 + .1 * nearest_x
    skew = write_case('skew_shortest', [0, 0], [nearest_x, nearest_y], origin, skew_target)
    close(skew['route_excess_length_m'], 0)
    assert skew['right_angle_deviation_deg'] > .5
    in_crosswalk = write_case('crosswalk_exception', [0, 0], [3, 8], origin, opposite,
                              [[[-1, -1], [4, -1], [4, 9], [-1, 9]]])
    assert in_crosswalk['crosswalk_sample_count'] == FRAMES
    assert in_crosswalk['route_excess_length_m'] > .5
    failures = {}
    for name, transform, expected in (
        ('missing_position', lambda row: row.pop('pedestrian_xy_m'), 'Original pedestrian position missing'),
        ('duplicate_native_frame', lambda row: row.update(native_frame=1000), 'Native frame order differs'),
    ):
        base = WORK / 'perpendicular'
        rows = [json.loads(line) for line in (base / 'samples.jsonl').read_text().splitlines()]
        transform(rows[1])
        mutated = WORK / (name + '.jsonl')
        mutated.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        try:
            measure_files(mutated, base / 'context.json', WORK / (name + '.report.json'))
        except ValueError as exc:
            assert expected in str(exc), str(exc)
            failures[name] = str(exc)
        else:
            raise AssertionError(name + ' unexpectedly accepted')
    report = {'format': 'worker-route-meter-cpu-proof-v1',
              'assignment_id': HERE.parent.name,
              'status': 'passed_software_only', 'frames_per_case': FRAMES,
              'sampling_rate_hz': 20,
              'cases': {key: {'right_angle_deviation_deg': value['right_angle_deviation_deg'],
                              'route_excess_length_m': value['route_excess_length_m'],
                              'crosswalk_sample_count': value['crosswalk_sample_count'],
                              'source_samples_sha256': value['source_samples_sha256'],
                              'source_context_sha256': value['source_context_sha256']}
                        for key, value in [('perpendicular', perpendicular), ('diagonal_longer', diagonal),
                                           ('skew_shortest', skew), ('crosswalk_exception', in_crosswalk)]},
              'negative_rejections': failures,
              'meter_sha256': hashlib.sha256((HERE / 'route_meter.py').read_bytes()).hexdigest(),
              'native_motion_observed': False, 'legal_verdict_assigned': False,
              'source_contract': 'Native samples and authored/map-verified curb and crosswalk geometry must be retained'}
    output = HERE / 'route-meter-proof.json'
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    run()
