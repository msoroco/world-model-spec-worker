"""Independent exact v1 no-countdown package receipt, source and Core audit."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
summary = json.loads((HERE / 'draft-package-no-countdown-summary.json').read_text())
offline = json.loads((HERE / 'draft-offline-summary.json').read_text())
manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
assert len(summary['records']) == 8 and summary['selected_cases'] == 0
assert summary['accepted_recordings'] == 0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


by_pair = {}
for record in summary['records']:
    suffix, candidate = record['case_suffix'], record['candidate']
    assert (suffix, candidate) not in by_pair
    by_pair[suffix, candidate] = record
    assert record['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256']
    assert record['package_log_sha256'] == sha(HERE / record['package_log'])
    receipt = json.loads((HERE / record['package_log']).read_text().splitlines()[-1])
    assert receipt['positive']['passed'] is True
    assert receipt['positive']['construction_sha256'] == record['construction_sha256']
    assert receipt['negative']['removed'] == 'no-countdown-samples.jsonl'
    assert receipt['negative']['exit_code'] != 0
    scratch = Path(record['retained_scratch'])
    output = scratch / 'output'
    negative = scratch / 'negative'
    assert (output / 'compatibility.json').is_file()
    assert json.loads((output / 'compatibility.json').read_text())['passed'] is True
    assert sha(output / 'finalize.py') == receipt['positive']['analysis_sha256']
    assert 'Missing required source: no-countdown-samples.jsonl' in (scratch / 'negative-analysis.log').read_text()
    assert not (negative / 'no-countdown-samples.jsonl').exists()
    result = json.loads((output / 'result.json').read_text())
    analysis = json.loads((output / 'analysis-report.json').read_text())
    assert result['case_id'] == analysis['case_id'] == record['case_id']
    assert result['accepted'] is False and result['legal_verdict_claimed'] is False
    assert result['setup_confirmed'] is False and result['behavior_attempted'] is False
    assert result['maneuver_completed'] is False
    assert analysis['measurements']['no_countdown_entry_and_clearance']['value']['source_kind'] == 'synthetic_scene_request'
    assert len(rows(output / 'no-countdown-samples.jsonl')) == 240
    assert len(rows(output / 'trace.jsonl')) == 240
    assert len(rows(output / 'video_frames.jsonl')) == 240
    assert len(json.loads((output / 'converted/trace.json').read_text())['scenes']) == 240
    assert json.loads((output / 'final-decode.json').read_text())['passed'] is True
    for camera in json.loads((output / 'config.json').read_text())['cameras']:
        assert (output / (camera['name'] + '.mkv')).is_file()
    matching = [item for item in offline['results'] if item['case_id'] == record['case_id']
                and item['candidate_id'] == candidate]
    assert len(matching) == 1 and matching[0]['construction_sha256'] == record['construction_sha256']
    expected = 'walk' if suffix == 'controlled_1' else 'dont_walk_flashing'
    assert result['measured_values']['entry_indication'] == expected

assert set(by_pair) == {(suffix, candidate) for suffix in ('controlled_1', 'controlled_2')
                       for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')}
for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
    a = Path(by_pair['controlled_1', candidate]['retained_scratch']) / 'output/no-countdown-samples.jsonl'
    b = Path(by_pair['controlled_2', candidate]['retained_scratch']) / 'output/no-countdown-samples.jsonl'
    first, second = rows(a), rows(b)
    assert len(first) == len(second) == 240
    for one, two in zip(first, second):
        display = ('indication', 'display_illuminated')
        assert {k: v for k, v in one.items() if k not in display} == {
            k: v for k, v in two.items() if k not in display}
print(json.dumps({'audit': 'pass', 'unselected_v1_packages': 8,
                  'positive_processing_and_negative_rejection': 8,
                  'core_scenes_per_package': 240, 'controlled_pairs': 4,
                  'accepted_recordings': 0}))
