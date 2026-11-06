"""Independent saved-source audit of the unselected synthetic steady cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
records = json.loads((HERE / 'saved-steady-summary.json').read_text())['records']
assert len(records) == 2


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


for record in records:
    suffix = record['case_suffix']
    root = Path(record['retained_positive'])
    config = json.loads((root / 'config.json').read_text())
    result = json.loads((root / 'result.json').read_text())
    report = json.loads((root / 'analysis-report.json').read_text())
    assert config['case_id'] == record['case_id'] == result['case_id'] == report['case_id']
    assert config['law_id'] == 'NRS-484B-283-1d4' and config['cell_id'] == 'C10316'
    assert sha(root / 'result.json') == record['result_sha256']
    assert sha(root / 'analysis-report.json') == record['analysis_report_sha256']
    for name, digest in record['original_source_hashes'].items():
        assert sha(root / name) == digest, name
    samples, mapping, trace, evidence = (rows(root / name) for name in
        ('steady-samples.jsonl', 'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl'))
    assert len(samples) == len(mapping) == len(trace) == len(evidence) == 240
    for index, (sample, frame, pose, original) in enumerate(zip(samples, mapping, trace, evidence)):
        assert frame['video_frame'] == index
        assert sample['native_frame'] == frame['native_frame'] == pose['frame'] == original['original_frame']
        assert abs(sample['time_s'] - frame['time_s']) < 1e-6
        assert sample['pedestrian_xy_m'] == pose['position_m'][:2] == original['ego']['position_m'][:2]
        assert {(round(x, 3), round(y, 3)) for x, y in sample['pedestrian_footprint_xy_m']} == {
            (round(point[0], 3), round(point[1], 3)) for point in original['ego']['body_vertices_m']}
        assert sample['display_illuminated'] is True
    entry = next(item for item in samples if max(point[0] for point in item['pedestrian_footprint_xy_m']) > -3.5)
    steady = next(item for item in samples if item['indication'] == 'dont_walk_steady')
    expected = 'before_steady' if suffix == 'witness_1' else 'at_or_after_steady'
    relation = 'before_steady' if entry['native_frame'] < steady['native_frame'] else 'at_or_after_steady'
    assert relation == expected == record['measured_entry_relation']
    assert result['target_checks'][0]['matched'] is True
    assert result['accepted'] is False and result['legal_verdict_claimed'] is False
    assert result['setup_confirmed'] is False and result['behavior_attempted'] is False
    assert result['maneuver_completed'] is False
    measured = report['measurements']['steady_entry_and_progress']['value']
    assert measured['source_kind'] == 'synthetic_scene_request'
    assert measured['exceptions_reviewed'] is False and measured['lawful_prior_entry_proven'] is False
    assert measured['as_soon_as_possible_bound_declared'] is False
    for camera in config['cameras']:
        assert report['video_frames'][camera['name'] + '.mkv'] == {
            'frames': 240, 'width': camera['width'], 'height': camera['height']}
    for label, removed in (('missing', 'steady-samples.jsonl'),
                           ('missing-video', 'overview.mkv')):
        assert not (root.parent / (suffix + '-' + label) / removed).exists()
    wrong = rows(root.parent / (suffix + '-wrong-footprint') / 'capture/evidence.jsonl')
    assert wrong[10]['ego']['body_vertices_m'][0][0] != evidence[10]['ego']['body_vertices_m'][0][0]

first = rows(Path(records[0]['retained_positive']) / 'steady-samples.jsonl')
second = rows(Path(records[1]['retained_positive']) / 'steady-samples.jsonl')
for a, b in zip(first, second):
    display = ('indication', 'display_illuminated')
    assert {k: v for k, v in a.items() if k not in display} == {
        k: v for k, v in b.items() if k not in display}
assert [r['measured_entry_relation'] for r in records] == ['before_steady', 'at_or_after_steady']
print(json.dumps({'independent_audit': 'pass', 'synthetic_saved_cases': 2,
                  'source_frames_per_case': 240, 'original_videos_per_case': 4,
                  'negative_source_variants': 6, 'accepted_recordings': 0}))
