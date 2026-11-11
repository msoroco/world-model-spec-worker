"""Independently audit retained lane originals in addition to rider/video joins."""
from hashlib import sha256
import json
from pathlib import Path

from rider_delivery_audit import audit_attempt
from rider_turn_lane import measure as measure_lane


def audit(attempt, report, *, receipt_dir=None):
    root = Path(attempt)
    report = json.loads(Path(report).read_text()) if not isinstance(report, dict) else report
    base = audit_attempt(root, report, receipt_dir=receipt_dir)
    item = report['measurements']['turn_lane_observation']
    observed = measure_lane(root)
    if item['method'] != 'measure_turn_lane' or item['value'] != observed:
        raise ValueError('Lane analysis differs from original source recomputation')
    for name, expected in item['sources'].items():
        if sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Stale or missing lane original: ' + name)
    return {**base, 'lane_original_source_hashes': observed['sources'],
            'designation_review_complete': observed['designation_review_complete'],
            'designated_turn_lane_confirmed': None,
            'legal_signal_exception_judgment': None}
