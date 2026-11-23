"""Independently audit the controlled synthetic no-countdown package pair."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(suffix):
    path = HERE / ('diagnostic-' + suffix + '.json')
    spec = json.loads(path.read_text())
    rows = [json.loads(line) for line in spec['files']['no-countdown-samples.jsonl'].splitlines()]
    context = json.loads(spec['files']['no-countdown-context.json'])
    assert len(rows) == len(spec['graphs']) == 240
    assert {video['path'] for video in spec['videos']} == {name + '.mkv' for name in CAMERAS}
    assert context['source_kind'] == 'synthetic_scene_request'
    assert context['countdown_present'] is False
    assert all(row['countdown_visible'] is False for row in rows)
    return path, spec, rows, context


def first_body_entry(rows, context):
    edge = context['near_highway_edge_xy_m']
    direction = context['crossing_forward_xy']
    for row in rows:
        if max(sum((vertex[i] - edge[i]) * direction[i] for i in (0, 1))
               for vertex in row['pedestrian_footprint_xy_m']) > 0:
            return row['native_frame'], row['time_s']
    raise AssertionError('No body entry')


def audit():
    first = source('controlled_1')
    second = source('controlled_2')
    p1, a, rows1, context1 = first
    p2, b, rows2, context2 = second
    assert set(a['files']) == set(b['files'])
    assert a['graphs'] == b['graphs'] and a['videos'] == b['videos']
    assert {key for key in a['files'] if a['files'][key] != b['files'][key]} == {
        'no-countdown-samples.jsonl', 'no-countdown-context.json'}
    assert {key for key in set(context1) | set(context2)
            if context1.get(key) != context2.get(key)} == {'flash_start_s'}
    assert (context1['flash_start_s'], context2['flash_start_s']) == (2, 0.5)
    assert all(x['native_frame'] == y['native_frame'] and
               x['time_s'] == y['time_s'] and
               {key: value for key, value in x.items() if key not in
                ('indication', 'display_illuminated')} ==
               {key: value for key, value in y.items() if key not in
                ('indication', 'display_illuminated')}
               for x, y in zip(rows1, rows2))
    assert first_body_entry(rows1, context1) == first_body_entry(rows2, context2) == (118, 0.9)
    starts = []
    for rows in (rows1, rows2):
        start = next(row for row in rows if row['indication'] == 'dont_walk_flashing')
        starts.append((start['native_frame'], start['time_s']))
        assert next(row['native_frame'] for row in rows
                    if row['indication'] == 'dont_walk_steady') == 280
    assert starts == [(140, 2.0), (110, 0.5)]
    summary = json.loads((HERE / 'public-compatibility-summary.json').read_text())
    assert len(summary['results']) == 8
    checked = []
    for item in summary['results']:
        assert item['exit_code'] == 0
        receipt = ROOT / item['receipt']
        assert receipt.is_file() and sha(receipt) == item['receipt_sha256']
        result = json.loads(receipt.read_text())
        assert result['passed'] is True and result['case_id'] == item['case_id']
        suffix = item['case_id'].rsplit('__', 1)[1]
        assert suffix in ('controlled_1', 'controlled_2')
        output = receipt.parent
        report = json.loads((output / 'analysis-report.json').read_text())
        observed = report['measurements']['no_countdown_entry_and_clearance']['value']
        expected = 'walk' if suffix == 'controlled_1' else 'dont_walk_flashing'
        assert observed['entry_indication'] == expected
        assert observed['first_entry']['first_frame'] == 118
        assert observed['flashing_start']['first_frame'] == (140 if suffix == 'controlled_1' else 110)
        assert observed['steady_start']['first_frame'] == 280
        assert observed['clearance_before_steady'] is True
        assert observed['legal_verdict_claimed'] is False
        checked.append({'case_id': item['case_id'], 'candidate': item['candidate'],
                        'receipt_sha256': sha(receipt),
                        'analysis_sha256': sha(output / 'analysis-report.json')})
    return {'format': 'c10316-public-no-countdown-comparison-audit-v1',
            'passed': True, 'source_sha256': {p1.name: sha(p1), p2.name: sha(p2)},
            'fixed': ['240 frame/time/body rows', 'all graph specifications',
                      'all four camera specifications', 'highway geometry',
                      'steady transition at frame 280'],
            'varied': ['flashing start at frames 140 and 110',
                       'entry indication at shared first body-entry frame 118'],
            'first_body_entry_frame': 118, 'flashing_start_frames': [140, 110],
            'package_receipts_checked': checked,
            'selected': False, 'physical_signal_observed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    result = audit()
    (HERE / 'public-comparison-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
