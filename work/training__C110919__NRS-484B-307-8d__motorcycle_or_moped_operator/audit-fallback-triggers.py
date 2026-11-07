"""Independently recompute measured synthetic fallback crossings and provenance."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    path = HERE/'fallback-trigger-source.json'
    source = json.loads(path.read_text())
    summary = json.loads((HERE/'fallback-trigger-summary.json').read_text())
    assert source['source_kind'] == summary['source_kind'] == 'synthetic_cpu_fixture'
    assert summary['source_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert summary['original_native_observed'] is False
    assert summary['original_pixels_observed'] is False
    expected = {'baseline': (False, False, False),
                'route_error': (True, False, False),
                'late_second_cycle': (False, True, False),
                'pixel_margin': (False, False, True)}
    assert len(source['measurements']) == len(summary['decisions']) == 8
    seen = set()
    for raw, result in zip(source['measurements'], summary['decisions']):
        key = (raw['case'], raw['scenario'])
        assert key == (result['case'], result['scenario']) and key not in seen
        seen.add(key)
        assert raw['case'] in ('condition_a', 'condition_b')
        actual = (raw['max_route_cross_track_error_m'] > .45,
                  raw['second_complete_cross_cycle_frame'] > 280,
                  raw['min_signal_or_body_pixel_margin_px'] < 40)
        assert actual == expected[raw['scenario']]
        assert actual == tuple(result[f'fallback{i}_trigger'] for i in (1, 2, 3))
    assert len(seen) == 8
    print(json.dumps({'audit': 'pass', 'synthetic_rows': 8,
                      'distinct_crossings_per_case': 3,
                      'original_observations': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
