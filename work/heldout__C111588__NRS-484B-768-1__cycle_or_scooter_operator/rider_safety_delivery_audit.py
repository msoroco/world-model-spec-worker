"""Independently verify the original participant-clearance source join."""
from hashlib import sha256
import json
from pathlib import Path

from rider_delivery_audit import audit_attempt
from rider_clearance_measurement import measure


def audit(attempt, report, *, receipt_dir=None):
    root = Path(attempt)
    report = json.loads(Path(report).read_text()) if not isinstance(report, dict) else report
    base = audit_attempt(root, report, receipt_dir=receipt_dir)
    item = report['measurements']['rider_clearance_observation']
    observed = measure(root)
    if item['method'] != 'measure_rider_clearance' or item['value'] != observed:
        raise ValueError('Clearance analysis differs from original source recomputation')
    for name, expected in item['sources'].items():
        source = root / name
        if not source.is_file() or sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError('Stale or missing participant original: ' + name)
    return {**base, 'participant_original_source_hashes': observed['sources'],
            'minimum_center_distance_m': observed['minimum_center_distance_m'],
            'time_to_conflict_s': observed['time_to_conflict_s'],
            'physical_participant_visibility_verified': False,
            'legal_reasonable_safety_judgment': None}
