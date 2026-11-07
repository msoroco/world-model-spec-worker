"""Independent saved-source audit of the unselected synthetic prior-entry cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
records = json.loads((HERE / 'saved-exception-summary.json').read_text())['records']
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
        ('exception-samples.jsonl', 'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl'))
    assert len(samples) == len(mapping) == len(trace) == len(evidence) == 240
    for index, (sample, frame, pose, original) in enumerate(zip(samples, mapping, trace, evidence)):
        assert frame['video_frame'] == index
        assert sample['native_frame'] == frame['native_frame'] == pose['frame'] == original['original_frame']
        assert abs(sample['time_s'] - frame['time_s']) < 1e-6
        assert sample['pedestrian_xy_m'] == pose['position_m'][:2] == original['ego']['position_m'][:2]
        assert {(round(x, 3), round(y, 3)) for x, y in sample['pedestrian_footprint_xy_m']} == {
            (round(point[0], 3), round(point[1], 3)) for point in original['ego']['body_vertices_m']}
        assert type(sample['display_illuminated']) is bool
        assert sample['indication'] == 'dont_walk_flashing' or sample['display_illuminated'] is True
    entry = next(item for item in samples if max(point[0] for point in item['pedestrian_footprint_xy_m']) > -3.5)
    steady = next(item for item in samples if item['indication'] == 'dont_walk_steady')
    expected = 'dont_walk_flashing' if suffix == 'exception_1_1' else 'walk'
    assert entry['native_frame'] < steady['native_frame']
    assert entry['indication'] == expected == record['measured_entry_indication']
    assert result['target_checks'][0]['matched'] is True
    assert result['accepted'] is False and result['legal_verdict_claimed'] is False
    assert result['setup_confirmed'] is False and result['behavior_attempted'] is False
    assert result['maneuver_completed'] is False
    measured = report['measurements']['prior_entry_exception_source_facts']['value']
    assessment = report['statutory_context_assessment']
    contract = json.loads((HERE / 'statutory-context-contract.json').read_text())
    packet_path = root / 'statutory-diagnostic-facts.json'
    packet = json.loads(packet_path.read_text())
    canonical_measurement = json.dumps(measured, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    assert assessment['contract_sha256'] == sha(HERE / 'statutory-context-contract.json')
    assert assessment['source_measurement_sha256'] == hashlib.sha256(canonical_measurement).hexdigest()
    assert assessment['facts_sha256'] == sha(packet_path)
    assert packet['source_sha256'] == measured['source_sha256']
    assert packet['provenance'] == assessment['fact_provenance'] == 'synthetic_diagnostic'
    assert len(assessment['branches']) == len(contract['dependencies']) == 12
    for branch, dependency in zip(assessment['branches'], contract['dependencies']):
        assert branch['law_id'] == dependency['law_id']
        assert branch['required_source_facts'] == dependency['required_source_facts']
        assert branch['missing_source_facts'] == []
        assert branch['diagnostic_facts_complete'] is True
        assert branch['physical_context_observed'] is False
        assert branch['legal_applicability_determined'] is False
    assert assessment['physical_context_observed'] is False
    assert assessment['legal_applicability_determined'] is False
    assert assessment['selected_delivery_cases'] == 0
    assert measured['source_kind'] == 'synthetic_scene_request'
    assert measured['exceptions_reviewed'] is False and measured['lawful_prior_entry_proven'] is False
    assert measured['as_soon_as_possible_bound_declared'] is False
    assert measured['progress_bound']['observed_max_stationary_s'] == 0.0
    assert measured['progress_bound']['observed_clearance_after_steady_s'] == 4.0
    assert measured['progress_bound']['engineering_surrogate_met'] is True
    assert measured['progress_bound']['legal_sufficiency_assessed'] is False
    for camera in config['cameras']:
        assert report['video_frames'][camera['name'] + '.mkv'] == {
            'frames': 240, 'width': camera['width'], 'height': camera['height']}
    for label, removed in (('missing', 'exception-samples.jsonl'),
                           ('missing-video', 'overview.mkv')):
        assert not (root.parent / (suffix + '-' + label) / removed).exists()
    wrong = rows(root.parent / (suffix + '-wrong-footprint') / 'capture/evidence.jsonl')
    assert wrong[10]['ego']['body_vertices_m'][0][0] != evidence[10]['ego']['body_vertices_m'][0][0]
    wrong_packet = json.loads((root.parent / (suffix + '-wrong-statutory-source') /
                               'statutory-diagnostic-facts.json').read_text())
    assert wrong_packet['source_sha256'] != packet['source_sha256']

first = rows(Path(records[0]['retained_positive']) / 'exception-samples.jsonl')
second = rows(Path(records[1]['retained_positive']) / 'exception-samples.jsonl')
for a, b in zip(first, second):
    display = ('indication', 'display_illuminated')
    assert {k: v for k, v in a.items() if k not in display} == {
        k: v for k, v in b.items() if k not in display}
assert [r['measured_entry_indication'] for r in records] == ['dont_walk_flashing', 'walk']
print(json.dumps({'independent_audit': 'pass', 'synthetic_saved_cases': 2,
                  'source_frames_per_case': 240, 'original_videos_per_case': 4,
                  'negative_source_variants': 8, 'accepted_recordings': 0}))
