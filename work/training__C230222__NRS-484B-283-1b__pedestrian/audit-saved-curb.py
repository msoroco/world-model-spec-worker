"""Independent retained synthetic curb-source and negative-fixture audit."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit():
    records = json.loads((HERE / 'saved-curb-summary.json').read_text())['records']
    if len(records) != 2:
        raise ValueError('Saved curb case count differs')
    pairs = []
    for record in records:
        suffix = record['case_suffix']
        root = Path(record['retained_positive'])
        config = json.loads((root / 'config.json').read_text())
        result = json.loads((root / 'result.json').read_text())
        report = json.loads((root / 'analysis-report.json').read_text())
        if config['case_id'] != record['case_id'] or result['case_id'] != record['case_id'] or report['case_id'] != record['case_id']:
            raise ValueError('Saved curb case identity differs')
        if config['law_id'] != 'NRS-484B-283-1b' or config['cell_id'] != 'C230222':
            raise ValueError('Saved curb law/cell differs')
        if sha(root / 'result.json') != record['result_sha256'] or sha(root / 'analysis-report.json') != record['analysis_report_sha256']:
            raise ValueError('Saved curb output hash differs')
        for name, digest in record['original_source_hashes'].items():
            if sha(root / name) != digest:
                raise ValueError('Saved curb original hash differs: ' + name)
        samples, mapping, trace, evidence = (rows(root / name) for name in
            ('curb-samples.jsonl', 'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl'))
        if len(samples) != 240 or len(mapping) != 240 or len(trace) != 240 or len(evidence) != 240:
            raise ValueError('Saved curb full source missing')
        for index, (sample, frame, pose, original) in enumerate(zip(samples, mapping, trace, evidence)):
            if frame['video_frame'] != index or not (
                sample['native_frame'] == frame['native_frame'] == pose['frame'] == original['original_frame']):
                raise ValueError('Saved curb frame join differs')
            if abs(sample['time_s'] - frame['time_s']) > 1e-6:
                raise ValueError('Saved curb time join differs')
            if sample['pedestrian_xy_m'] != pose['position_m'][:2] or sample['pedestrian_xy_m'] != original['ego']['position_m'][:2]:
                raise ValueError('Saved curb pose join differs')
            source_body = {(round(x, 3), round(y, 3)) for x, y in sample['pedestrian_footprint_xy_m']}
            evidence_body = {(round(point[0], 3), round(point[1], 3)) for point in original['ego']['body_vertices_m']}
            if source_body != evidence_body:
                raise ValueError('Saved curb footprint join differs')
        measured = report['measurements']['curb_departure_conditional_margin']['value']
        expected = 'conditional_yield_possible' if suffix == 'probe_1' else 'conditional_yield_impossible'
        if measured['source_kind'] != 'synthetic_scene_request' or measured['conditional_yield_relation'] != expected:
            raise ValueError('Saved curb synthetic relation differs')
        if any(measured[key] for key in ('actual_driver_yield_observed', 'driver_capability_measured',
                                         'impossibility_to_yield_proven', 'introductory_exceptions_reviewed', 'legal_verdict_claimed')):
            raise ValueError('Saved curb falsely claims physical or legal proof')
        if result['accepted'] or result['legal_verdict_claimed'] or result['setup_confirmed'] or result['behavior_attempted']:
            raise ValueError('Saved curb falsely claims delivery')
        if result['target_checks'][0]['matched'] is not True:
            raise ValueError('Saved curb controlled request did not match synthetic measurement')
        for camera in config['cameras']:
            if report['video_frames'][camera['name'] + '.mkv'] != {
                'frames': 240, 'width': camera['width'], 'height': camera['height']}:
                raise ValueError('Saved curb video decode differs')
        for label, removed in (('missing', 'curb-samples.jsonl'), ('missing-video', 'overview.mkv')):
            if (root.parent / (suffix + '-' + label) / removed).exists():
                raise ValueError('Saved curb negative source remains')
        wrong = rows(root.parent / (suffix + '-wrong-footprint') / 'capture/evidence.jsonl')
        if wrong[10]['ego']['body_vertices_m'][0][0] == evidence[10]['ego']['body_vertices_m'][0][0]:
            raise ValueError('Saved curb wrong-footprint negative not mutated')
        pairs.append(samples)
    for a, b in zip(*pairs):
        for key in ('vehicle_id', 'vehicle_xy_m', 'vehicle_speed_mps', 'time_s'):
            if a[key] != b[key]:
                raise ValueError('Saved curb controlled vehicle trace differs')
    return {'independent_audit': 'pass', 'synthetic_saved_cases': 2,
            'source_frames_per_case': 240, 'source_videos_per_case': 4,
            'negative_source_variants': 6, 'accepted_recordings': 0}


if __name__ == '__main__':
    print(json.dumps(audit()))
