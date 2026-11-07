"""Independently recompute synthetic fallback thresholds from saved measurements."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    path = HERE / 'fallback-trigger-source.json'
    source = json.loads(path.read_text())
    summary = json.loads((HERE / 'fallback-trigger-summary.json').read_text())
    assert source['source_kind'] == summary['source_kind'] == 'synthetic_cpu_fixture'
    assert summary['source_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert summary['original_native_observed'] is False
    assert summary['original_pixels_observed'] is False
    expected = {'baseline': (False, False, False),
                'short_spawn': (True, False, False),
                'gap_error': (False, True, False),
                'lead_occlusion': (False, False, True)}
    seen = set()
    assert len(source['cases']) == len(summary['cases']) == 8
    for raw, result in zip(source['cases'], summary['cases']):
        key = (raw['case_suffix'], raw['scenario'])
        assert key == (result['case_suffix'], result['scenario'])
        assert key not in seen
        seen.add(key)
        assert raw['case_suffix'] in ('condition_a', 'condition_b')
        assert 0 <= raw['lead_body_visible_fraction'] <= 1
        actual = (raw['spawn_to_crest_distance_m'] < 85.0,
                  raw['maximum_gap_tracking_error_m'] > 2.0,
                  raw['lead_body_visible_fraction'] < .95)
        assert actual == expected[raw['scenario']]
        assert actual == tuple(result[f'fallback{i}_trigger'] for i in (1, 2, 3))
    assert len(seen) == 8
    print(json.dumps({'audit': 'pass', 'synthetic_rows': 8,
                      'distinct_trigger_crossings_per_case': 3,
                      'original_observations': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
