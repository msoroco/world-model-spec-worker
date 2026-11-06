"""Independent row and conditional-stopping audit of the synthetic curb pair."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
records = json.loads((HERE / 'curb-summary.json').read_text())['records']
assert len(records) == 2


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


sources = []
for record in records:
    folder = Path(record['retained_positive'])
    context = json.loads((folder / 'curb-context.json').read_text())
    samples = rows(folder / 'curb-samples.jsonl')
    measured = json.loads((folder / 'source-measurement.json').read_text())
    assert len(samples) == measured['original_frames'] == 240
    assert sha(folder / 'source-measurement.json') == record['source_measurement_sha256']
    for name, digest in record['source_hashes'].items():
        assert sha(folder / name) == digest
    assert context['source_kind'] == 'synthetic_scene_request'
    assert context['driver_capability_source'] == 'assumption_only_not_original_vehicle_measurement'
    assert context['introductory_exceptions'] == 'unreviewed_synthetic_context'
    assert all(row['native_frame'] == 100+i and abs(row['time_s']-i/20) < 1e-9
               for i, row in enumerate(samples))
    departure = next(row for row in samples if row['pedestrian_speed_mps'] > 0)
    entry = next(row for row in samples if max(v[0] for v in row['pedestrian_footprint_xy_m']) > -3.5)
    arrival = next(row for row in samples if row['vehicle_xy_m'][1] >= 0)
    assert departure['time_s'] == record['requested_departure_s']
    assert measured['first_curb_departure']['first_frame'] == departure['native_frame']
    assert measured['first_roadway_entry']['first_frame'] == entry['native_frame']
    assert arrival['time_s'] == 4.5
    distance = -entry['vehicle_xy_m'][1]
    assert abs(measured['vehicle_distance_at_entry_m']-distance) < 1e-9
    shortest = 4*.8 + 16/(2*5)
    longest = 4*1.2 + 16/(2*3)
    assert all(abs(a-b) < 1e-9 for a,b in zip(measured['conditional_stopping_distance_range_m'],
                                               (shortest,longest)))
    assert all(abs(a-b) < 1e-9 for a,b in zip(measured['conditional_stopping_margin_range_m'],
                                               (distance-longest,distance-shortest)))
    relation = ('conditional_yield_possible' if distance-longest > 0 else
                'conditional_yield_impossible' if distance-shortest < 0 else
                'conditional_yield_indeterminate')
    assert relation == record['conditional_yield_relation'] == measured['conditional_yield_relation']
    assert measured['actual_driver_yield_observed'] is False
    assert measured['driver_capability_measured'] is False
    assert measured['impossibility_to_yield_proven'] is False
    assert measured['introductory_exceptions_reviewed'] is False
    assert measured['legal_verdict_claimed'] is False
    assert not (folder.parent / (record['case_suffix']+'-missing') / 'curb-samples.jsonl').exists()
    sources.append(samples)

first, second = sources
for a,b in zip(first,second):
    assert (a['native_frame'],a['time_s'],a['vehicle_xy_m'],a['vehicle_speed_mps']) == (
        b['native_frame'],b['time_s'],b['vehicle_xy_m'],b['vehicle_speed_mps'])
assert [r['requested_departure_s'] for r in records] == [.5,3.5]
assert [r['conditional_yield_relation'] for r in records] == [
    'conditional_yield_possible','conditional_yield_impossible']
print(json.dumps({'independent_audit':'pass','synthetic_curb_cases':2,
                  'rows_per_case':240,'conditional_entry_distances_m':[14.8,2.8],
                  'driver_capability_measured':False,'accepted_recordings':0}))
