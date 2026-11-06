"""Independent retained synthetic countdown saved-source audit."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
summary = json.loads((HERE / 'saved-countdown-summary.json').read_text())
records = summary['records']
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
    assert config['law_id'] == 'NRS-484B-283-1d2' and config['cell_id'] == 'C10316'
    assert sha(root / 'result.json') == record['result_sha256']
    assert sha(root / 'analysis-report.json') == record['analysis_report_sha256']
    for name, digest in record['original_source_hashes'].items():
        assert sha(root / name) == digest, name
    samples = rows(root / 'countdown_samples.jsonl')
    mapping = rows(root / 'video_frames.jsonl')
    trace = rows(root / 'trace.jsonl')
    evidence = rows(root / 'capture/evidence.jsonl')
    assert len(samples) == len(mapping) == len(trace) == len(evidence) == 240
    for index, (sample, frame, pose, original) in enumerate(zip(samples, mapping, trace, evidence)):
        assert frame['video_frame'] == index
        assert sample['native_frame'] == frame['native_frame'] == pose['frame'] == original['original_frame']
        assert abs(sample['time_s'] - frame['time_s']) < 1e-6
        assert sample['pedestrian_xy_m'] == pose['position_m'][:2] == original['ego']['position_m'][:2]
        assert {(round(x, 3), round(y, 3)) for x, y in sample['pedestrian_footprint_xy_m']} == {
            (round(point[0], 3), round(point[1], 3)) for point in original['ego']['body_vertices_m']}
    first_zero = next(item for item in samples if item['displayed_countdown_s'] == 0)
    first_clear = next(item for item in samples if min(point[0] for point in item['pedestrian_footprint_xy_m']) >= 3.5)
    relation = 'before_zero' if first_clear['time_s'] < first_zero['time_s'] else 'at_or_after_zero'
    expected = 'before_zero' if suffix == 'probe_01' else 'at_or_after_zero'
    assert relation == expected == record['measured_relation']
    assert result['target_checks'][0]['matched'] is True
    assert result['accepted'] is False and result['legal_verdict_claimed'] is False
    assert result['setup_confirmed'] is False and result['behavior_attempted'] is False
    assert result['maneuver_completed'] is False
    assert report['measurements']['flashing_countdown_clearance']['value']['source_kind'] == 'synthetic_scene_request'
    assert report['measurements']['flashing_countdown_clearance']['value']['exceptions_reviewed'] is False
    for camera in config['cameras']:
        name = camera['name'] + '.mkv'
        assert report['video_frames'][name] == {
            'frames': 240, 'width': camera['width'], 'height': camera['height']}
    for label, removed in (('missing', 'countdown_samples.jsonl'),
                           ('missing-video', 'overview.mkv')):
        assert not (root.parent / (suffix + '-' + label) / removed).exists()
    wrong = rows(root.parent / (suffix + '-wrong-footprint') / 'capture/evidence.jsonl')
    assert wrong[10]['ego']['body_vertices_m'][0][0] != evidence[10]['ego']['body_vertices_m'][0][0]

first = rows(Path(records[0]['retained_positive']) / 'countdown_samples.jsonl')
second = rows(Path(records[1]['retained_positive']) / 'countdown_samples.jsonl')
assert len(first) == len(second) == 240
for a, b in zip(first, second):
    display = ('displayed_countdown_s', 'indication', 'display_illuminated')
    assert {k: v for k, v in a.items() if k not in display} == {
        k: v for k, v in b.items() if k not in display}
assert first[0]['displayed_countdown_s'] == 10 and second[0]['displayed_countdown_s'] == 7
assert [r['measured_relation'] for r in records] == ['before_zero', 'at_or_after_zero']
print(json.dumps({'independent_audit': 'pass', 'synthetic_saved_cases': 2,
                  'source_frames_per_case': 240, 'controlled_display_zero_s': [10, 7],
                  'original_videos_per_case': 4, 'negative_source_variants': 6,
                  'accepted_recordings': 0}))
