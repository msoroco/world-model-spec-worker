"""Saved-only original-source measurement, before canonical conversion.

This command reads sealed site and Native frame sources. It does not execute
CARLA, alter a captured source, issue a legal verdict, or claim acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_crossing import measure, source


def build(site_ref, events_ref, attempt_root):
    site_path = source(site_ref, attempt_root)
    site = json.loads(site_path.read_text())
    facts = measure(site, attempt_root, events_ref)
    return {
        'format': 'worker-pedestrian-crossing-measurement',
        'assignment_id': 'testing__C111125__NRS-484B-307-2b__pedestrian',
        'site_source': site_ref,
        'events_source': events_ref,
        'site_source_sha256': hashlib.sha256(site_path.read_bytes()).hexdigest(),
        'facts': facts,
        'legal_verdict': None,
        'physical_acceptance': False,
    }


def build_sealed(site_ref, events_ref, capture_receipt_ref, attempt_root):
    """Require a source-hashed Native receipt before saved-only measurement."""
    receipt_path = source(capture_receipt_ref, attempt_root)
    receipt = json.loads(receipt_path.read_text())
    if receipt.get('format') != 'worker-original-crossing-capture':
        raise ValueError('wrong Native capture receipt format')
    if receipt.get('assignment_id') != 'testing__C111125__NRS-484B-307-2b__pedestrian':
        raise ValueError('wrong Native capture assignment')
    if receipt.get('original_frames') != events_ref:
        raise ValueError('Native receipt does not bind original frames')
    result = build(site_ref, events_ref, attempt_root)
    facts = result['facts']
    if receipt.get('frame_count') != facts['frame_count']:
        raise ValueError('Native receipt frame count mismatch')
    first = facts['measurements'][0]['frame']
    last = facts['measurements'][-1]['frame']
    if receipt.get('first_frame') != first or receipt.get('last_frame') != last:
        raise ValueError('Native receipt frame range mismatch')
    if receipt.get('first_highway_entry_frame') != (
        facts['first_highway_entry']['frame'] if facts['first_highway_entry'] else None
    ):
        raise ValueError('Native receipt highway entry mismatch')
    result['native_capture_receipt_source'] = capture_receipt_ref
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt-root', required=True)
    parser.add_argument('--site-ref', required=True)
    parser.add_argument('--events-ref', required=True)
    parser.add_argument('--capture-receipt-ref', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    site_ref = json.loads(Path(args.site_ref).read_text())
    events_ref = json.loads(Path(args.events_ref).read_text())
    capture_receipt_ref = json.loads(Path(args.capture_receipt_ref).read_text())
    result = build_sealed(site_ref, events_ref, capture_receipt_ref, args.attempt_root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + '.tmp')
    tmp.write_text(json.dumps(result, indent=2) + '\n')
    tmp.replace(output)


if __name__ == '__main__':
    main()
