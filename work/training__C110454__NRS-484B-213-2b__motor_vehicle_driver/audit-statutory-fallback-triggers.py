"""Independently recompute measured synthetic fallback crossings and provenance."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent


def main():
    path = HERE/'statutory-fallback-trigger-source.json'
    source = json.loads(path.read_text())
    summary = json.loads((HERE/'statutory-fallback-trigger-summary.json').read_text())
    assert source['source_kind'] == summary['source_kind'] == 'synthetic_cpu_fixture'
    assert summary['source_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert summary['original_native_observed'] is False
    assert summary['original_pixels_observed'] is False
    expected = {'baseline': (False, False, False),
                'route_error': (True, False, False),
                'parking_speed': (False, True, False),
                'pixel_margin': (False, False, True)}
    assert len(source['measurements']) == len(summary['decisions']) == 16
    seen = set()
    for raw, result in zip(source['measurements'], summary['decisions']):
        key = (raw['case'], raw['scenario'])
        assert key == (result['case'], result['scenario']) and key not in seen
        seen.add(key)
        assert raw['case'] in ('rail_reference', 'rail_contrast', 'oneway_absent', 'oneway_present')
        actual = (raw['max_route_cross_track_error_m'] > .45,
                  raw['parking_endpoint_speed_m_s'] > .3,
                  raw['min_ego_pixel_margin_px'] < 40)
        assert actual == expected[raw['scenario']]
        assert actual == tuple(result[f'fallback{i}_trigger'] for i in (1, 2, 3))
    assert len(seen) == 16
    spec = importlib.util.spec_from_file_location('statutory_engineering', HERE/'native/engineering_statutory.py')
    engineering = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engineering)
    with tempfile.TemporaryDirectory() as temp:
        metric_path = Path(temp)/'metrics.json'
        for candidate in ('fallback1', 'fallback2', 'fallback3'):
            metric = engineering.TRIGGERS[candidate]['metric']
            for invalid in (float('nan'), float('inf'), float('-inf'), -1, True):
                record = {'source_kind': 'original_native_and_video', metric: invalid}
                metric_path.write_text(json.dumps(record))
                digest = hashlib.sha256(metric_path.read_bytes()).hexdigest()
                try:
                    engineering.evaluate_trigger(candidate, record, metric_path, digest)
                except ValueError:
                    pass
                else:
                    raise AssertionError('Invalid statutory fallback metric accepted')
    print(json.dumps({'audit': 'pass', 'synthetic_rows': 16,
                      'distinct_crossings_per_case': 3,
                      'original_observations': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
