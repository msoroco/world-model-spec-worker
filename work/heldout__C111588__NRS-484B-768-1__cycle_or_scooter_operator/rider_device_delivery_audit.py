"""Independent original-source audit for electric-device diagnostic results."""
from hashlib import sha256
import json
from pathlib import Path

from rider_delivery_audit import audit_attempt
from rider_device_class import measure


def audit(attempt, report, device, *, receipt_dir=None):
    root = Path(attempt)
    report = json.loads(Path(report).read_text()) if not isinstance(report, dict) else report
    base = audit_attempt(root, report, receipt_dir=receipt_dir)
    item = report['measurements']['electric_device_observation']
    observed = measure(root, device)
    if item['method'] != 'measure_electric_device' or item['value'] != observed:
        raise ValueError('Electric device analysis differs from original source recomputation')
    for name, expected in item['sources'].items():
        if not (root / name).is_file() or sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Stale or missing electric device original: ' + name)
    return {**base, 'electric_device_original_source_hashes': observed['sources'],
            'device_class_candidate': device, 'device_class_confirmed': None,
            'electric_drive_verified': None, 'legal_device_class_judgment': None}
