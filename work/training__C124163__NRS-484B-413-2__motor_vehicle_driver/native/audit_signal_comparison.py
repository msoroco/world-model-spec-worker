"""Independent controlled-pair audit of the synthetic distance diagnostics."""
import hashlib
import json
from pathlib import Path

from signal_distance import load, measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    root = Path(__file__).with_name('diagnostic-sources')
    pairs = [('other_long', 'other_short'), ('district_long', 'district_short')]
    reviewed = []
    for long, short in pairs:
        a_index, a_context, a_rows = load(root / long)
        b_index, b_context, b_rows = load(root / short)
        a, b = measure(root / long), measure(root / short)
        assert a_context == b_context
        assert len(a_rows) == len(b_rows) == 600
        assert sha(root / long / 'context.json') == sha(root / short / 'context.json')
        assert a['statutory_distance_ft'] == b['statutory_distance_ft']
        assert a['synthetic_numeric_distance_met'] and not b['synthetic_numeric_distance_met']
        for x, y in zip(a_rows, b_rows):
            assert {key: value for key, value in x.items() if key != 'signal_visible'} == {
                key: value for key, value in y.items() if key != 'signal_visible'}
        assert a['continuous_signal_distance_m'] > b['continuous_signal_distance_m']
        reviewed.append({'pair': [a_index['condition'], b_index['condition']],
                         'district': a_context['district_class'],
                         'weather': a_context['weather'],
                         'continuous_distance_m': [a['continuous_signal_distance_m'],
                                                   b['continuous_signal_distance_m']],
                         'context_sha256': sha(root / long / 'context.json')})
    proof = {
        'format': 'c124163-signal-distance-independent-comparison-v1',
        'passed': True, 'pairs': reviewed,
        'fixed_distance_course_weather_within_pairs': True,
        'physical_signal_pixels_confirmed': False,
        'legal_verdict_claimed': False,
    }
    target = Path(__file__).with_name('signal-comparison-audit.json')
    target.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': True, 'pairs': len(reviewed)}))


if __name__ == '__main__':
    main()
