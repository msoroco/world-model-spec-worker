"""Independent row-level audit of synthetic steady witness sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
records = json.loads((HERE / 'steady-summary.json').read_text())['records']
assert len(records) == 2


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


sources = []
for record in records:
    folder = Path(record['retained_positive'])
    context = json.loads((folder / 'steady-context.json').read_text())
    samples = rows(folder / 'steady-samples.jsonl')
    measured = json.loads((folder / 'source-measurement.json').read_text())
    assert len(samples) == 240 and measured['original_frames'] == 240
    assert sha(folder / 'source-measurement.json') == record['source_measurement_sha256']
    for name, digest in record['source_hashes'].items():
        assert sha(folder / name) == digest
    assert context['source_kind'] == 'synthetic_scene_request'
    assert context['introductory_exceptions'] == 'unreviewed_synthetic_context'
    assert context['safety_destination_review'] == 'unverified'
    assert context['as_soon_as_possible_judgment_bound'] is None
    assert all(row['native_frame'] == 100 + index and abs(row['time_s'] - index/20) < 1e-9
               for index, row in enumerate(samples))
    entry = next(row for row in samples if max(v[0] for v in row['pedestrian_footprint_xy_m']) > -3.5)
    steady = next(row for row in samples if row['indication'] == 'dont_walk_steady')
    clearance = next(row for row in samples if min(v[0] for v in row['pedestrian_footprint_xy_m']) >= 3.5)
    relation = 'before_steady' if entry['native_frame'] < steady['native_frame'] else 'at_or_after_steady'
    assert relation == record['entry_relative_to_steady'] == measured['entry_relative_to_steady']
    assert measured['first_entry']['first_frame'] == entry['native_frame']
    assert measured['steady_start']['first_frame'] == steady['native_frame']
    assert measured['full_body_clearance']['first_frame'] == clearance['native_frame']
    assert steady['native_frame'] < clearance['native_frame']
    assert measured['lawful_prior_entry_proven'] is False
    assert measured['exceptions_reviewed'] is False
    assert measured['as_soon_as_possible_bound_declared'] is False
    assert measured['physical_signal_observed'] is False
    assert measured['legal_verdict_claimed'] is False
    for label, missing in (('missing', 'steady-samples.jsonl'),):
        assert not (folder.parent / (record['case_suffix'] + '-' + label) / missing).exists()
    sources.append(samples)

first, second = sources
for a, b in zip(first, second):
    assert {k: v for k, v in a.items() if k != 'indication'} == {
        k: v for k, v in b.items() if k != 'indication'}
assert [record['steady_start_s'] for record in records] == [4.0, .5]
assert [record['entry_relative_to_steady'] for record in records] == [
    'before_steady', 'at_or_after_steady']
print(json.dumps({'independent_audit': 'pass', 'synthetic_witness_cases': 2,
                  'rows_per_case': 240, 'steady_start_s': [4.0, .5],
                  'adversarial_rejections': 8, 'accepted_recordings': 0}))
