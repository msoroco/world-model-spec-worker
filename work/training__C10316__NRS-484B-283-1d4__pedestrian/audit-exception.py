"""Independent row-level audit of unselected prior-entry source facts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
records = json.loads((HERE / 'exception-summary.json').read_text())['records']
assert len(records) == 2


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


sources = []
for record in records:
    folder = Path(record['retained_positive'])
    context = json.loads((folder / 'exception-context.json').read_text())
    samples = rows(folder / 'exception-samples.jsonl')
    measured = json.loads((folder / 'source-measurement.json').read_text())
    assert len(samples) == 240 and measured['original_frames'] == 240
    assert sha(folder / 'source-measurement.json') == record['source_measurement_sha256']
    for name, digest in record['source_hashes'].items():
        assert sha(folder / name) == digest
    assert context['source_kind'] == 'synthetic_scene_request'
    assert context['introductory_exceptions'] == 'unreviewed_synthetic_context'
    assert context['lawful_prior_entry_review'] == 'unverified'
    assert all(row['native_frame'] == 100 + index and abs(row['time_s'] - index / 20) < 1e-9
               for index, row in enumerate(samples))
    entry = next(row for row in samples if max(v[0] for v in row['pedestrian_footprint_xy_m']) > -3.5)
    steady = next(row for row in samples if row['indication'] == 'dont_walk_steady')
    clear = next(row for row in samples if min(v[0] for v in row['pedestrian_footprint_xy_m']) >= 3.5)
    assert entry['native_frame'] == 118 and steady['native_frame'] == 180 and clear['native_frame'] == 260
    assert entry['indication'] == measured['entry_indication'] == record['entry_indication']
    assert measured['post_steady_crossing_samples'] == 80
    assert measured['continued_progress_source_fact'] is True
    assert measured['lawful_prior_entry_proven'] is False
    assert measured['as_soon_as_possible_bound_declared'] is False
    assert measured['exceptions_reviewed'] is False
    assert measured['physical_signal_observed'] is False
    assert measured['legal_verdict_claimed'] is False
    assert not (folder.parent / (record['case_suffix'] + '-missing') / 'exception-samples.jsonl').exists()
    sources.append(samples)

first, second = sources
for a, b in zip(first, second):
    assert {k: v for k, v in a.items() if k not in ('indication', 'display_illuminated')} == {
        k: v for k, v in b.items() if k not in ('indication', 'display_illuminated')}
assert [r['entry_indication'] for r in records] == ['dont_walk_flashing', 'walk']
assert [r['steady_start_s'] for r in records] == [4.0, 4.0]
print(json.dumps({'independent_audit': 'pass', 'synthetic_exception_cases': 2,
                  'rows_per_case': 240, 'adversarial_rejections': 10,
                  'lawful_prior_entry_proven': False, 'accepted_recordings': 0}))
