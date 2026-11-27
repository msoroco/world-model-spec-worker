"""Diagnostic fixed-source comparison proof for selected beam-policy pairs."""
import json
from pathlib import Path

from compare_beam import compare


REPO = Path(__file__).resolve().parents[3]
ROOT = Path(__file__).resolve().parents[1]
SCRATCH = REPO / '.runtime-work/c183394'
PLAN = json.loads((ROOT / 'case-plan.json').read_text())
PAIRS = (
    ('condition_a', 'condition_b', 'civil-compat-', 'primary'),
    ('visibility_dim', 'visibility_high', 'civil-compat-', 'primary'),
    ('device_dim', 'device_high', 'compat-', 'primary'),
)
expected = {row['comparison_id']: row['case_ids'] for row in PLAN['comparisons']}
for low, high, prefix, candidate in PAIRS:
    a = SCRATCH / f'{prefix}{low}-{candidate}'
    b = SCRATCH / f'{prefix}{high}-{candidate}'
    value = compare(a, b)
    assert value['comparison_id'] in expected
    assert value['case_ids'] == expected[value['comparison_id']]
    assert value['joined_frames'] == 600
    assert value['contrasting_within_500_feet_frames'] > 0
    assert value['legal_verdict_claimed'] is False
    print('PASS', value['comparison_id'], value['contrasting_within_500_feet_frames'])
