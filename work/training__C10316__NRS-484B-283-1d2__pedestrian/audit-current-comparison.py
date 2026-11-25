"""Audit the controlled countdown pair from source rows and public receipts."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c10316-1d2-public-v1'
CAMERAS = {'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(suffix):
    path = HERE / ('diagnostic-current-' + suffix + '.json')
    spec = json.loads(path.read_text())
    rows = [json.loads(line) for line in
            spec['files']['countdown_samples.jsonl'].splitlines()]
    context = json.loads(spec['files']['countdown-context.json'])
    assert len(rows) == len(spec['graphs']) == 600
    assert {item['path'] for item in spec['videos']} == CAMERAS
    assert context['source_kind'] == 'synthetic_scene_request'
    assert context['introductory_exceptions']['status'] == 'unverified_synthetic_request'
    return path, spec, rows, context


def main():
    first = load('probe_01')
    second = load('probe_02')
    p1, a, rows1, context1 = first
    p2, b, rows2, context2 = second
    assert a['graphs'] == b['graphs'] and a['videos'] == b['videos']
    assert context1 == context2
    assert {key for key in a['files'] if a['files'][key] != b['files'][key]} == {
        'countdown_samples.jsonl'}
    for left, right in zip(rows1, rows2):
        assert (left['native_frame'], left['time_s']) == (
            right['native_frame'], right['time_s'])
        assert {key: value for key, value in left.items()
                if key not in ('displayed_countdown_s', 'display_illuminated')} == {
                    key: value for key, value in right.items()
                    if key not in ('displayed_countdown_s', 'display_illuminated')}
    assert rows1[0]['displayed_countdown_s'] == 10
    assert rows2[0]['displayed_countdown_s'] == 7
    assert all(left['pedestrian_xy_m'] == right['pedestrian_xy_m']
               for left, right in zip(rows1, rows2))
    proof = json.loads((HERE / 'current-public/proof.json').read_text())
    assert proof['manifest_sha256'] == sha(HERE / 'current-probe-manifest.json')
    assert len(proof['records']) == 8
    checked = []
    for row in proof['records']:
        suffix = row['case_id'].rsplit('__', 1)[1]
        key = suffix + '-' + row['candidate']
        attempt = SCRATCH / key / 'compat'
        receipt = attempt / 'compatibility.json'
        report = attempt / 'analysis-report.json'
        assert sha(receipt) == row['compatibility_receipt_sha256']
        assert json.loads(receipt.read_text())['passed'] is True
        value = json.loads(report.read_text())['measurements'][
            'flashing_countdown_clearance']['value']
        assert value['original_frames'] == 600
        assert value['entry']['first_frame'] == 118
        assert value['full_body_clearance']['first_frame'] == 260
        expected = (300, 'before_zero') if suffix == 'probe_01' else (
            240, 'at_or_after_zero')
        assert (value['displayed_zero']['first_frame'],
                value['clearance_relative_to_displayed_zero']) == expected
        assert value['governing_device_observed'] is False
        assert value['highway_boundary_observed'] is False
        assert value['legal_verdict_claimed'] is False
        checked.append({'case_id': row['case_id'], 'candidate': row['candidate'],
                        'receipt_sha256': sha(receipt),
                        'analysis_sha256': sha(report)})
    result = {'format': 'c10316-current-countdown-comparison-audit',
              'passed': True,
              'source_sha256': {p1.name: sha(p1), p2.name: sha(p2)},
              'fixed': ['600 frame/time/pose/footprint rows', 'all graph rows',
                        'all four camera specifications', 'authored crossing map'],
              'varied': ['requested displayed-zero frame 300 versus 240'],
              'package_receipts_checked': checked,
              'physical_or_legal_acceptance_claimed': False}
    (HERE / 'current-comparison-audit.json').write_text(
        json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
