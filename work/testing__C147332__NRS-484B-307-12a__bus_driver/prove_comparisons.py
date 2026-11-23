"""Verify both exact synthetic source-bound comparison pairs and rejections."""
from __future__ import annotations

from pathlib import Path
from comparison_audit import audit

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = REPO / '.runtime-work/c147332-12a-delivery-v2'
PAIRS = (
    ('second_green_arrow', 'adjacent_dark_drive', 'second_green_drive'),
    ('permission_without_motion', 'green_selected_drive', 'green_selected_stand'),
)
for kind, left, right in PAIRS:
    first = BASE / left / 'positive'
    second = BASE / right / 'positive'
    report = audit(first, second, kind)
    if report['source_bound'] is not True or report['physical_acceptance_claimed'] is not False:
        raise AssertionError('comparison made an unsupported physical claim')
    try:
        audit(second, first, kind)
    except ValueError as error:
        if 'wrong exact comparison case pair or order' not in str(error):
            raise
    else:
        raise AssertionError('reversed exact pair was accepted')
    try:
        audit(BASE / left / 'negative', second, kind)
    except ValueError as error:
        if 'Missing required source: lane-signal-history.jsonl' not in str(error):
            raise
    else:
        raise AssertionError('missing original lane signal was accepted')
    print(kind, 'exact pair positive, reversed order and missing-source negatives passed')
