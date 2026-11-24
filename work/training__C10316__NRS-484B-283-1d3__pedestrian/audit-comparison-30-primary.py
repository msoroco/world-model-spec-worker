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
    path = HERE / ('diagnostic30-' + suffix + '.json')
    spec = json.loads(path.read_text())
    rows = [json.loads(line) for line in spec['files']['no-countdown-samples.jsonl'].splitlines()]
    context = json.loads(spec['files']['no-countdown-context.json'])
    assert len(rows) == len(spec['graphs']) == 600
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
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    checked = []
    for index, suffix in enumerate(('controlled_1', 'controlled_2')):
        output = ROOT / ('.runtime-work/c10316-30-compat-2' if index == 0 else '.runtime-work/c10316-30-compat-controlled2-primary')
        saved = ROOT / ('.runtime-work/c10316-30-saved-1/v0001' if index == 0 else '.runtime-work/c10316-30-saved-controlled2-primary/v0001')
        entry = manifest['cases'][index]
        c = json.loads((output / 'compatibility.json').read_text())
        r = json.loads((output / 'analysis-report.json').read_text())
        processing = json.loads((saved / 'processing.json').read_text())
        assert c['passed'] is True and c['case_id'] == entry['case_id'] and c['candidate_id'] == 'primary'
        assert c['construction_sha256'] == entry['construction_sha256']
        assert c['fixture_recipe_sha256'] == sha(ROOT / entry['fixture_recipe'])
        assert c['negative_removed'] == 'no-countdown-samples.jsonl'
        assert c['negative_error_contains'] in (output / 'negative-analysis.log').read_text()
        assert c['negative_log_sha256'] == sha(output / 'negative-analysis.log')
        value = r['measurements']['no_countdown_entry_and_clearance']['value']
        assert value['original_frames'] == 600
        assert value['source_kind'] == 'synthetic_scene_request' and value['governing_device_observed'] is False
        assert value['entry_indication'] == ('walk' if index == 0 else 'dont_walk_flashing')
        assert value['first_entry']['first_frame'] == 118
        assert value['flashing_start']['first_frame'] == (140 if index == 0 else 110)
        assert value['steady_start']['first_frame'] == 280
        assert processing['passed'] is True and processing['recorded_only'] is True
        assert processing['timestamp_joins']['frames'] == 600 and processing['final_video_checks']['frames'] == 600
        assert processing['physical_acceptance_claimed'] is False and processing['legal_acceptance_claimed'] is False
        checked.append({'case_id': entry['case_id'], 'construction_sha256': c['construction_sha256'],
                        'compatibility_sha256': sha(output / 'compatibility.json'),
                        'saved_processing_sha256': sha(saved / 'processing.json')})
    return {'format': 'c10316-current-30-second-primary-comparison-audit', 'passed': True,
            'source_sha256': {p1.name: sha(p1), p2.name: sha(p2)},
            'fixed': ['600 frame/time/body rows', 'all graph and four camera specifications',
                      'highway geometry', 'steady transition at frame 280'],
            'varied': ['flashing start at frames 140 and 110', 'entry indication at first body-entry frame 118'],
            'first_body_entry_frame': 118, 'flashing_start_frames': [140, 110],
            'package_receipts_checked': checked, 'selected': False,
            'physical_signal_observed': False, 'legal_verdict_claimed': False}

if __name__ == '__main__':
    result = audit()
    (HERE / 'comparison-30-primary-proof.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
