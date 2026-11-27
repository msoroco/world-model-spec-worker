"""Diagnostic source-shape checks for distinct requested motion intervals."""

import copy
import json

from rail_finalize import original_native_source_contract


def packet_and_measurement(kind):
    frames = []
    measured = []
    hold = (210, 240) if kind == 'stop_depart' else (220, 350)
    for index in range(600):
        x = -12.0 if index < hold[1] else -12.0 + min(12.0, (index-hold[1]) * .1)
        at_rest = hold[0] <= index < hold[1]
        frames.append({'vehicle_footprint_xy_m': [[x+2, 1], [x+2, -1],
                                                   [x-2, -1], [x-2, 1]]})
        measured.append({'frame': index, 'at_rest': at_rest,
                         'inside_50ft_band': x < 0,
                         'footprint_to_nearest_rail_m': abs(x)})
    packet = {'frames': frames, 'diagnostic_fixture': True,
              'original_native_observed': False,
              'original_rail_survey_sha256': 'diagnostic-hash',
              'original_source_seal_sha256': 'diagnostic-hash'}
    return packet, {'frames': measured}


def main():
    for kind in ('stop_depart', 'stand_depart'):
        packet, measured = packet_and_measurement(kind)
        good = original_native_source_contract(packet, measured, kind)
        assert good['requested_motion_event_observed'] is True
        assert good['diagnostic_fixture'] is True
        no_departure = copy.deepcopy(packet)
        for frame in no_departure['frames']:
            frame['vehicle_footprint_xy_m'] = packet['frames'][350]['vehicle_footprint_xy_m']
        assert original_native_source_contract(no_departure, measured, kind)['requested_motion_event_observed'] is False
        too_short = copy.deepcopy(measured)
        too_short['frames'][230]['at_rest'] = False
        assert original_native_source_contract(packet, too_short, kind)['requested_motion_event_observed'] is False
    print(json.dumps({'diagnostic_motion_variants': 2, 'positive_count': 2,
                      'negative_count': 4, 'original_native_observed': False}))


if __name__ == '__main__':
    main()
