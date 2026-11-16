"""Synthetic CPU comparison of parking at and outside a painted curb extent."""
import copy
import json

from measure_red_curb import VIEWS, measure


def fixture(stop_x):
    rows = []; frames = []
    for index in range(240):
        x = stop_x * min(index, 120) / 120
        y = -6.8
        rows.append({'frame': index, 'native_frame': index,
                     'source_kind': 'synthetic_native_sample',
                     'ego_center_native_xy_m': [x, y],
                     'ego_body_native_xy_m': [[x - 1, y - .5],
                                              [x + 1, y - .5],
                                              [x + 1, y + .5],
                                              [x - 1, y + .5]]})
        frames.append({'video_frame': index, 'native_frame': index,
                       'views': sorted(VIEWS)})
    return rows, frames


def reject(action, label):
    try:
        action()
    except ValueError:
        return label
    raise AssertionError('Red-curb negative accepted: ' + label)


def prove():
    curb = {'paint_color': 'red', 'source_kind': 'synthetic_native_sample',
            'start_x_m': 30, 'end_x_m': 50, 'curb_y_m': -7}
    reference_rows, frames = fixture(40)
    contrast_rows, _ = fixture(60)
    reference = measure(reference_rows, frames, curb)
    contrast = measure(contrast_rows, frames, curb)
    assert reference['red_curb_stop_or_park_observed']
    assert not contrast['red_curb_stop_or_park_observed']
    assert len(reference['red_curb_stopped_frame_ids']) == 119
    assert len(contrast['red_curb_stopped_frame_ids']) == 0
    negatives = []
    altered = copy.deepcopy(frames); altered[90]['views'] = ['overview']
    negatives.append(reject(lambda: measure(reference_rows, altered, curb),
                            'missing-three-cameras'))
    altered = copy.deepcopy(reference_rows); altered[90]['source_kind'] = 'original_native'
    negatives.append(reject(lambda: measure(altered, frames, curb),
                            'mixed-provenance'))
    altered = {**curb, 'paint_color': 'yellow'}
    negatives.append(reject(lambda: measure(reference_rows, frames, altered),
                            'not-red-paint'))
    altered = {**curb, 'start_x_m': 55, 'end_x_m': 45}
    negatives.append(reject(lambda: measure(reference_rows, frames, altered),
                            'inverted-paint-extent'))
    altered = copy.deepcopy(reference_rows); altered[90]['ego_body_native_xy_m'] = []
    negatives.append(reject(lambda: measure(altered, frames, curb),
                            'missing-measured-body'))
    negatives.append(reject(lambda: measure(reference_rows[:-1], frames, curb),
                            'missing-frame'))
    return {'format': 'c150142-red-curb-measure-cpu-proof-v1',
            'reference': {'red_stopped_frames': len(reference['red_curb_stopped_frame_ids']),
                          'observed': reference['red_curb_stop_or_park_observed']},
            'contrast': {'red_stopped_frames': len(contrast['red_curb_stopped_frame_ids']),
                         'observed': contrast['red_curb_stop_or_park_observed']},
            'negative_rejections': negatives, 'source_kind': 'synthetic_native_sample',
            'speed_values_supplied': False, 'original_native_observed': False,
            'physical_acceptance_claimed': False, 'legal_verdict': None}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
