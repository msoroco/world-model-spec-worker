"""CPU proof of a fixed physical Walk hold-margin coverage grid."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from physical_sweep import MARGINS_M, SAMPLE_FRONT_Y_M, measured_hold_margin, request_grid


def rejection(name, source, **changes):
    altered = [dict(row) for row in source]
    if name == 'missing_frame':
        altered.pop()
    elif name == 'invented_speed':
        altered[0]['speed_provenance'] = 'native_measured'
    elif name == 'missing_body':
        altered[0]['bus_body_xy_m'] = []
    elif name == 'no_hold':
        altered[100]['controller_request'] = {'hold_requested': False}
    elif name == 'time_order':
        altered[101]['time_s'] = altered[100]['time_s']
    try:
        measured_hold_margin(altered, diagnostic=True)
    except ValueError:
        return name
    raise AssertionError('Damaged source accepted: ' + name)


def main():
    grid = request_grid()
    assert len(grid) == len(MARGINS_M) * len(SAMPLE_FRONT_Y_M)
    assert all(row['hold_requested'] == (
        -11.0 - row['source_shaped_front_y_m'] > row['setpoint_margin_m'])
        for row in grid)
    assert not any(row['physical_yield_observed'] or row['legal_outcome_claimed'] for row in grid)
    assert {row['hold_requested'] for row in grid} == {True, False}
    source = []
    for index in range(480):
        front = -12.25 if index == 100 else -14.0
        source.append({'native_frame': index + 1, 'time_s': (index + 1) * .05,
                       'speed_provenance': 'synthetic_native_sample',
                       'bus_body_xy_m': [[1.0, front - 7], [2.5, front - 7],
                                         [1.0, front], [2.5, front]],
                       'controller_request': {'hold_requested': index == 100}})
    measured = measured_hold_margin(source, diagnostic=True)
    assert measured['native_frame'] == 101 and measured['value'] == 1.25
    try:
        measured_hold_margin(source)
    except ValueError:
        original_rejected = True
    else:
        raise AssertionError('Synthetic samples accepted as original')
    rejected = [rejection(name, source) for name in (
        'missing_frame', 'invented_speed', 'missing_body', 'no_hold', 'time_order')]
    contract = {
        'format': 'c111256-physical-judgment-sweep-cpu-v1',
        'status': 'candidate_grid_not_selected',
        'axis': 'crosswalk_hold_margin_m', 'unit': 'm',
        'setpoints_m': list(MARGINS_M),
        'source': ['native/controller.py: WalkYieldController hold_margin_m domain (0,5] m',
                   'native/geometry.py: marked near crosswalk y=-11 m',
                   'native/runner.py: original four-corner bus body and controller_request per Native frame'],
        'rationale': 'Fixed engineering coverage of the bus-front hold request at a marked crosswalk; no legal cutoff or compliance label.',
        'measurement': 'First source requested hold: marked crosswalk y minus measured bus body front y, with all 480 original frames required.',
        'diagnostic_measurement': measured,
        'controller_grid_rows': len(grid), 'controller_true_and_false': True,
        'negative_rejections': rejected, 'synthetic_original_rejected': original_rejected,
        'original_recordings_accepted': 0,
    }
    path = HERE / 'update026-physical-sweep-cpu.json'
    path.write_text(json.dumps(contract, indent=2) + '\n')
    print(json.dumps({'contract': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'setpoints_m': list(MARGINS_M), 'grid_rows': len(grid),
                      'negative_rejections': len(rejected) + 1,
                      'original_recordings_accepted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
