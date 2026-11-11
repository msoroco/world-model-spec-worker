"""Independently audit retained hand/control originals and rider/video joins."""
from hashlib import sha256
import json
from pathlib import Path

from rider_delivery_audit import audit_attempt
from rider_hand_control import measure as measure_hands


def audit(attempt, report, *, receipt_dir=None):
    root = Path(attempt)
    report = json.loads(Path(report).read_text()) if not isinstance(report, dict) else report
    base = audit_attempt(root, report, receipt_dir=receipt_dir)
    item = report['measurements']['both_hands_observation']
    observed = measure_hands(root)
    if item['method'] != 'measure_both_hands' or item['value'] != observed:
        raise ValueError('Hand-control analysis differs from original source recomputation')
    for name, expected in item['sources'].items():
        if sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Stale or missing hand-control original: ' + name)
    return {**base, 'hand_control_original_source_hashes': observed['sources'],
            'hand_contact_review_complete': observed['hand_contact_review_complete'],
            'both_hands_required_for_safety': None,
            'legal_signal_exception_judgment': None}
