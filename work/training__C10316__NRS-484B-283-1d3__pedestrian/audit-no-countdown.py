"""Independent original-row audit of synthetic no-countdown controlled pair."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
summary = json.loads((HERE / 'no-countdown-summary.json').read_text())
assert len(summary['records']) == 2


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


sources = []
for record in summary['records']:
    folder = Path(record['retained_positive'])
    for name, digest in record['source_hashes'].items():
        assert sha(folder / name) == digest
    assert sha(folder / 'analysis-report.json') == record['analysis_report_sha256']
    report = json.loads((folder / 'analysis-report.json').read_text())
    assert report['source_kind'] == 'synthetic_scene_request'
    assert report['legal_verdict_claimed'] is False
    assert report['exceptions_reviewed'] is False
    assert report['lawful_prior_entry_proven'] is False
    values = rows(folder / 'no-countdown-samples.jsonl')
    assert len(values) == 240
    assert all('displayed_countdown_s' not in item and item['countdown_visible'] is False for item in values)
    first_entry = next(item for item in values if max(point[0] for point in item['pedestrian_footprint_xy_m']) > -3.5)
    first_clear = next(item for item in values if min(point[0] for point in item['pedestrian_footprint_xy_m']) >= 3.5)
    first_flash = next(item for item in values if item['indication'] == 'dont_walk_flashing')
    first_steady = next(item for item in values if item['indication'] == 'dont_walk_steady')
    assert first_entry['native_frame'] == report['first_entry']['first_frame']
    assert first_clear['native_frame'] == report['full_body_clearance']['first_frame']
    assert first_flash['native_frame'] == report['flashing_start']['first_frame']
    assert first_steady['native_frame'] == report['steady_start']['first_frame']
    assert first_entry['indication'] == record['entry_indication'] == report['entry_indication']
    assert first_clear['native_frame'] < first_steady['native_frame']
    assert {'walk', 'dont_walk_flashing', 'dont_walk_steady'} == {item['indication'] for item in values}
    assert {True, False} == {item['display_illuminated'] for item in values if item['indication'] == 'dont_walk_flashing'}
    assert len(record['negative_errors']) == 3
    sources.append(values)

walk, flashing = sources
assert walk[0]['indication'] == flashing[0]['indication'] == 'walk'
for a, b in zip(walk, flashing):
    display = ('indication', 'display_illuminated')
    assert {key: value for key, value in a.items() if key not in display} == {
        key: value for key, value in b.items() if key not in display}
assert [record['entry_indication'] for record in summary['records']] == ['walk', 'dont_walk_flashing']
print(json.dumps({'audit': 'pass', 'synthetic_unselected_cases': 2,
                  'frames_per_case': 240, 'controlled_flash_start_s': [2, .5],
                  'same_pedestrian_motion': True, 'negative_rejections': 6,
                  'accepted_recordings': 0}))
