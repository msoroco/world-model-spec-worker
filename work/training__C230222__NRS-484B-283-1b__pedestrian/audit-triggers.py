"""Independently replay retained synthetic fallback decision fixtures."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from triggers import decide, measure_source


def audit():
    summary = json.loads((HERE / 'trigger-proof-summary.json').read_text())
    if len(summary['records']) != 2 or summary['physical_trigger_observations'] != 0:
        raise ValueError('Trigger proof scope differs')
    for record in summary['records']:
        suffix = record['case_suffix']
        folder = Path(record['positive_folder'])
        measured = measure_source(folder, folder / 'visibility.json')
        source_rows = [json.loads(line) for line in (folder / 'curb-samples.jsonl').read_text().splitlines()]
        pixel_rows = json.loads((folder / 'visibility.json').read_text())['frames']
        clearance = -3.5 - max(vertex[0] for vertex in source_rows[0]['pedestrian_footprint_xy_m'])
        first = next(i for i in range(1, 240)
                     if source_rows[i-1]['pedestrian_speed_mps'] <= .05 < source_rows[i]['pedestrian_speed_mps'])
        acceleration = ((source_rows[first]['pedestrian_speed_mps'] -
                         source_rows[first-1]['pedestrian_speed_mps']) /
                        (source_rows[first]['time_s'] - source_rows[first-1]['time_s']))
        visibility = sum(row['curb_visible'] and row['vehicle_visible'] for row in pixel_rows) / 240
        if (abs(clearance - measured['initial_footprint_clearance_m']) > 1e-6 or
            abs(acceleration - measured['first_departure_acceleration_mps2']) > 1e-6 or
            visibility != measured['curb_and_vehicle_visibility_fraction']):
            raise ValueError('Independent trigger metric differs')
        if (measured != record['positive_metrics'] or
            measured['source_sha256'] != record['positive_source_sha256'] or
            decide(suffix, measured) != record['positive_decision'] or
            measured['visibility_kind'] != 'synthetic_visibility_fixture' or
            not all(decide(suffix, measured)['decisions'][x]['activate']
                    for x in ('fallback1', 'fallback2', 'fallback3'))):
            raise ValueError('Positive trigger source or decision differs')
        for ident, negative in record['negative_fixtures'].items():
            folder = Path(negative['folder'])
            value = measure_source(folder, folder / 'visibility.json')
            if (value['source_sha256'] != negative['source_sha256'] or
                decide(suffix, value)['decisions'][ident]['activate'] or
                decide(suffix, value)['decisions'][ident]['value'] != negative['value']):
                raise ValueError('Negative trigger source or decision differs')
        if not record['bad_join_rejected']:
            raise ValueError('Bad join rejection missing')
        bad = Path(record['bad_join_folder'])
        try:
            measure_source(bad, bad / 'visibility.json')
        except ValueError as error:
            if 'frame join' not in str(error):
                raise
        else:
            raise ValueError('Bad visibility frame join accepted')
    return {'independent_audit': 'pass', 'cases': 2,
            'synthetic_positive_decisions': 6, 'synthetic_negative_decisions': 6,
            'physical_trigger_observations': 0}


if __name__ == '__main__':
    print(json.dumps(audit()))
