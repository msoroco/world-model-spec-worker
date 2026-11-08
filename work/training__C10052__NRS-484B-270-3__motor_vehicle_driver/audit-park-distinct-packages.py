"""Independent CPU audit of two distinct park cases and eight exact bundles."""
import hashlib
import json
from pathlib import Path

from audit_geometry import clipped_area

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')
SUFFIXES = ('probe_park_released', 'probe_park_held')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def main():
    manifest_path = HERE / 'draft-park-execution-manifest.json'
    manifest = read(manifest_path)
    offline = read(HERE / 'park-case-offline-summary.json')
    trigger_summary = read(HERE / 'park-case-trigger-summary.json')
    proposals = read(HERE / 'proposals/cases.json')
    plan = read(HERE / 'case-plan.json')
    assert manifest['status'] == 'draft_not_selected' and len(manifest['cases']) == 2
    assert offline['passed'] and offline['manifest_sha256'] == sha(manifest_path)
    assert len(offline['results']) == 8
    assert trigger_summary['passed'] and trigger_summary['manifest_sha256'] == sha(manifest_path)
    assert len(trigger_summary['rows']) == 8
    comparison = next(c for c in plan['comparisons'] if c['comparison_id'].endswith('__comparison_park_act'))
    assert set(comparison['case_ids']) == {e['case_id'] for e in manifest['cases']}
    assert set(comparison['case_ids']) <= {c['case_id'] for c in proposals['cases']}
    pairs = []
    for name in NAMES:
        log = (HERE / f'park-distinct-{name}.log').read_text()
        report = json.loads(log[log.index('{'):])
        assert report['passed'] and report['manifest_sha256'] == sha(manifest_path)
        assert report['selected'] is report['accepted'] is False
        assert len(report['results']) == 2
        pair = {}
        for item in report['results']:
            suffix = item['case_id'].rsplit('__', 1)[-1]
            assert suffix in SUFFIXES and item['candidate'] == name
            entry = next(e for e in manifest['cases'] if e['case_id'] == item['case_id'])
            contract = read(HERE / entry['measurement_contract'])
            assert contract['case_id'] == item['case_id']
            assert contract['controlled_contrast']['target_held_control'] is (suffix == 'probe_park_held')
            assert contract['source_join']['frames'] == 480
            assert contract['act_candidate']['minimum_contiguous_frames'] == 40
            assert contract['selected'] is contract['accepted'] is False
            ref = entry if name == 'primary' else next(c for c in entry['candidates'] if c['id'] == name)
            construction = HERE / ref['construction']
            assert sha(construction) == ref['construction_sha256']
            bundle = read(construction)
            files = {f['path']: f['content'] for f in bundle['files']}
            config = json.loads(files['config.json'])
            assert bundle['case_id'] == config['case_id'] == item['case_id']
            assert config['case_suffix'] == suffix and config['candidate_id'] == name
            assert "suffix == 'probe_park_held'" in files['runner.py']
            assert "'probe_park_released': -4.0" in files['geometry.py']
            assert "expected_park = config['case_suffix'] == 'probe_park_held'" in files['finalize.py']
            offline_row = next(r for r in offline['results'] if r['case_id'] == item['case_id']
                               and r['candidate'] == name)
            assert offline_row['exit_code'] == 0
            assert offline_row['construction_sha256'] == sha(construction)
            assert sha(HERE / offline_row['command_log']) == offline_row['command_log_sha256']
            unit = ROOT / offline_row['unit_log']
            assert sha(unit) == offline_row['unit_log_sha256']
            assert 'Ran 6 tests' in unit.read_text() and '\nOK\n' in unit.read_text()
            trigger_row = next(r for r in trigger_summary['rows'] if r['case_id'] == item['case_id']
                               and r['candidate'] == name)
            trigger_folder = ROOT / trigger_row['source_root']
            trigger_manifest = read(trigger_folder / 'trigger-sources.json')
            assert trigger_row['construction_sha256'] == sha(construction)
            assert trigger_row['source_manifest_sha256'] == sha(trigger_folder / 'trigger-sources.json')
            assert all(sha(trigger_folder / key) == value for key, value in trigger_manifest['sha256'].items())
            trigger_measurement = read(trigger_folder / 'measurement.json')
            assert trigger_row['measurement_sha256'] == sha(trigger_folder / 'measurement.json')
            trigger_poses = rows(trigger_folder / 'native_samples.jsonl')
            views = rows(trigger_folder / 'camera_visibility.jsonl')
            assert len(trigger_poses) == len(views) == 480
            intervals = []
            start = None
            for i, stopped in enumerate([r['speed_mps'] <= .1 for r in trigger_poses] + [False]):
                if stopped and start is None:
                    start = i
                if not stopped and start is not None:
                    intervals.append([start, i])
                    start = None
            interval = max(intervals, key=lambda pair: pair[1]-pair[0])
            assert trigger_measurement['stop_interval_frames'] == interval
            target = (-12.0, -4.0)
            error = max(((r['native_center_xy_m'][0]-target[0])**2 +
                         (r['native_center_xy_m'][1]-target[1])**2)**.5
                        for r in trigger_poses[interval[0]:interval[1]])
            first_y = trigger_poses[0]['native_center_xy_m'][1]
            shift = next(i for i, r in enumerate(trigger_poses)
                         if abs(r['native_center_xy_m'][1]-first_y) >= .05)
            lead = trigger_poses[shift]['native_center_xy_m'][0]-trigger_poses[0]['native_center_xy_m'][0]
            fractions = {view: sum(row['views'][view]['full_body'] and
                                   row['views'][view]['facility_edge']
                                   for row in views[interval[0]:interval[1]])/(interval[1]-interval[0])
                         for view in ('overview', 'facility')}
            assert trigger_measurement['route_lead_in_before_lateral_shift_m'] == lead
            assert abs(trigger_measurement['maximum_stationary_target_error_m']-error) < 1e-9
            assert trigger_measurement['longest_stationary_duration_s'] == (interval[1]-interval[0])/20
            assert trigger_measurement['stopped_frame_visible_fraction'] == fractions
            assert all(trigger_measurement[f'fallback{i}_trigger_measured'] is (name == f'fallback{i}')
                       for i in range(1, 4))
            assert trigger_row['changed_visibility_rejected'] is True
            source = ROOT / item['source_root']
            output = ROOT / item['output_root']
            negative = ROOT / item['negative_root']
            receipt = read(output / 'compatibility.json')
            assert receipt['passed'] and receipt['format'] == 'worker-package-compatibility-v1'
            assert sha(output / 'compatibility.json') == item['positive_receipt_sha256']
            assert receipt['construction_sha256'] == sha(construction)
            assert sha(negative.with_suffix('.log')) == item['negative_log_sha256']
            assert 'Parking source hash differs: native_controls.jsonl' in negative.with_suffix('.log').read_text()
            assert not (negative / 'result.json').exists()
            source_manifest = read(source / 'park-act-sources.json')
            assert all(sha(source / key) == value for key, value in source_manifest['sha256'].items())
            poses = rows(source / 'native_samples.jsonl')
            controls = rows(source / 'native_controls.jsonl')
            assert len(poses) == len(controls) == 480
            bounds = read(source / 'road_geometry.json')['bicycle_facility_native_xy_bounds_m']
            active = [p['speed_mps'] <= .1 and c['throttle'] <= .01 and c['hand_brake']
                      and clipped_area(p['native_body_xy_m'], bounds) > .01
                      for p, c in zip(poses, controls)]
            max_run = run = 0
            for flag in active:
                run = run + 1 if flag else 0
                max_run = max(max_run, run)
            observed = read(output / 'analysis-report.json')['measurements']['parking_control_observation']['value']
            expected = suffix == 'probe_park_held'
            assert observed['park_control_candidate'] is expected
            assert observed['held_duration_s'] == (14.0 if expected else 0)
            assert max_run == (280 if expected else 0)
            result = read(output / 'result.json')
            assert result['target_checks'][1]['requested'] is expected
            assert result['target_checks'][1]['measured'] is expected
            assert result['target_checks'][1]['matched'] is True
            assert result['accepted'] is result['legal_verdict_claimed'] is False
            pair[suffix] = {'source': source, 'output': output,
                            'receipt_sha256': item['positive_receipt_sha256']}
        held = pair['probe_park_held']['source']
        released = pair['probe_park_released']['source']
        for file in ('native_samples.jsonl', 'road_geometry.json', 'overview.mkv',
                     'approach.mkv', 'facility.mkv', 'driver_reference.mkv'):
            assert sha(held / file) == sha(released / file)
        assert sha(held / 'native_controls.jsonl') != sha(released / 'native_controls.jsonl')
        pairs.append({'candidate': name,
                      'held_receipt_sha256': pair['probe_park_held']['receipt_sha256'],
                      'released_receipt_sha256': pair['probe_park_released']['receipt_sha256']})
    return {'format': 'c10052-distinct-park-independent-audit-v1',
            'passed': True, 'candidate_pairs': pairs,
            'manifest_sha256': sha(manifest_path),
            'offline_summary_sha256': sha(HERE / 'park-case-offline-summary.json'),
            'trigger_summary_sha256': sha(HERE / 'park-case-trigger-summary.json'),
            'selected': False, 'legal_park_observed': False, 'accepted': False}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
