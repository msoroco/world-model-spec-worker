"""Independently audit four same-pose held/released exact package pairs."""
import hashlib
import json
from pathlib import Path

from audit_geometry import clipped_area

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def main():
    manifest_path = HERE / 'draft-execution-manifest.json'
    contract_path = HERE / 'draft-park-control-measurement-contract.json'
    contract = read(contract_path)
    assert contract['status'] == 'unselected_synthetic_cpu_diagnostic'
    assert contract['source_join']['frames'] == 480
    assert contract['act_candidate']['minimum_contiguous_frames'] == 40
    assert contract['controlled_contrast']['candidate_ids'] == list(NAMES)
    assert contract['selected'] is contract['accepted'] is False
    entry = next(c for c in read(manifest_path)['cases'] if c['case_id'].endswith('__probe_b'))
    pairs = []
    common_source = None
    for name in NAMES:
        log_path = HERE / f'park-exact-contrast-{name}.log'
        raw = log_path.read_text()
        report = json.loads(raw[raw.index('{'):])
        assert report['passed'] and report['candidate'] == name
        assert report['selected'] is report['accepted'] is False
        assert report['construction_manifest_sha256'] == sha(manifest_path)
        candidate = entry if name == 'primary' else next(c for c in entry['candidates'] if c['id'] == name)
        assert sha(HERE / candidate['construction']) == candidate['construction_sha256']
        held, released = report['reports']
        assert held['variant'] == 'held' and released['variant'] == 'released'
        h_source, r_source = ROOT / held['source_root'], ROOT / released['source_root']
        h_output, r_output = ROOT / held['output_root'], ROOT / released['output_root']
        assert all(sha(h_source / file) == sha(r_source / file)
                   for file in report['held_source_files_equal'])
        assert all(sha(h_source / file) != sha(r_source / file)
                   for file in report['source_difference'])
        source_hashes = {label: sha(h_source / label) for label in report['held_source_files_equal']}
        if common_source is None:
            common_source = source_hashes
        else:
            assert common_source == source_hashes
        poses = rows(h_source / 'native_samples.jsonl')
        geometry = read(h_source / 'road_geometry.json')
        bounds = geometry['bicycle_facility_native_xy_bounds_m']
        assert len(poses) == 480
        values = []
        for item, source, output in ((held, h_source, h_output), (released, r_source, r_output)):
            source_manifest = read(source / 'park-act-sources.json')
            assert item['park_source_sha256'] == sha(source / 'park-act-sources.json')
            assert all(sha(source / key) == digest for key, digest in source_manifest['sha256'].items())
            controls = rows(source / 'native_controls.jsonl')
            assert len(controls) == 480
            active = []
            for pose, control in zip(poses, controls):
                assert pose['native_frame'] == control['native_frame']
                assert pose['time_s'] == control['time_s']
                area = clipped_area(pose['native_body_xy_m'], bounds)
                active.append(pose['speed_mps'] <= .1 and control['throttle'] <= .01
                              and control['hand_brake'] and area > .01)
            runs = []
            start = None
            for i, flag in enumerate(active + [False]):
                if flag and start is None:
                    start = i
                if not flag and start is not None:
                    if i - start >= 40:
                        runs.append((start, i))
                    start = None
            longest = max(runs, key=lambda pair: pair[1]-pair[0], default=None)
            receipt = read(output / 'compatibility.json')
            observation = read(output / 'analysis-report.json')['measurements']['parking_control_observation']
            result = read(output / 'result.json')
            assert receipt['passed'] is True and receipt['format'] == 'worker-package-compatibility-v1'
            assert item['receipt_sha256'] == sha(output / 'compatibility.json')
            assert observation['sources']['native_controls.jsonl'] == sha(source / 'native_controls.jsonl')
            assert observation['sources']['native_samples.jsonl'] == sha(source / 'native_samples.jsonl')
            value = observation['value']
            assert value['park_control_candidate'] == (longest is not None)
            assert value['first_held_native_frame'] == (None if longest is None else poses[longest[0]]['native_frame'])
            assert value['held_duration_s'] == (0 if longest is None else (longest[1]-longest[0])/20)
            assert value['facility_designation_verified'] is False
            assert value['statutory_exceptions_verified'] is False
            assert value['legal_park_verdict_claimed'] is False
            assert result['accepted'] is False and result['legal_verdict_claimed'] is False
            values.append(value)
        assert values[0]['park_control_candidate'] is True
        assert values[0]['held_duration_s'] == 14.0
        assert values[0]['max_held_facility_overlap_m2'] == 9.36
        assert values[1]['park_control_candidate'] is False
        assert values[1]['held_duration_s'] == 0
        pairs.append({'candidate': name, 'held_receipt_sha256': held['receipt_sha256'],
                      'released_receipt_sha256': released['receipt_sha256'],
                      'held_duration_s': 14.0, 'released_duration_s': 0})
    return {'format': 'c10052-park-exact-contrast-independent-audit-v1',
            'passed': True, 'pairs': pairs, 'held_source_hashes': common_source,
            'measurement_contract_sha256': sha(contract_path),
            'selected': False, 'legal_park_observed': False, 'accepted': False}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
