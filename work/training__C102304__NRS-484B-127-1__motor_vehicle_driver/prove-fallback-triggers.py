"""Save measured synthetic threshold crossings for the three Native fallback policies."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'fallback-trigger-source.json'
OUTPUT = HERE / 'fallback-trigger-summary.json'


def main():
    scenarios = {
        'baseline': (95.0, 1.0, .99),
        'short_spawn': (80.0, 1.0, .99),
        'gap_error': (95.0, 3.0, .99),
        'lead_occlusion': (95.0, 1.0, .90),
    }
    source = {'source_kind': 'synthetic_cpu_fixture', 'cases': []}
    for suffix in ('condition_a', 'condition_b'):
        for label, (spawn, error, visible) in scenarios.items():
            source['cases'].append({'case_suffix': suffix, 'scenario': label,
                'spawn_to_crest_distance_m': spawn,
                'maximum_gap_tracking_error_m': error,
                'lead_body_visible_fraction': visible})
    SOURCE.write_text(json.dumps(source, indent=2) + '\n')
    rows = []
    for row in source['cases']:
        rows.append({'case_suffix': row['case_suffix'], 'scenario': row['scenario'],
            'fallback1_trigger': row['spawn_to_crest_distance_m'] < 85.0,
            'fallback2_trigger': row['maximum_gap_tracking_error_m'] > 2.0,
            'fallback3_trigger': row['lead_body_visible_fraction'] < .95})
    OUTPUT.write_text(json.dumps({'source_kind': 'synthetic_cpu_fixture',
        'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'original_native_observed': False, 'original_pixels_observed': False,
        'cases': rows}, indent=2) + '\n')
    print(json.dumps({'synthetic_rows': len(rows), 'distinct_trigger_crossings': 3}))


if __name__ == '__main__':
    main()
