"""Verify a separately reviewed site receipt before original Native capture.

The receipt identifies the exact source bytes and reviewer. This checks
provenance and internal consistency; it cannot authenticate a parcel claim.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from map_binding import bind


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(opendrive: Path, authority: Path, receipt_path: Path,
           *, property_id: str) -> dict:
    for path in (opendrive, authority, receipt_path):
        if not path.is_file() or path.is_symlink():
            raise ValueError('regular original site source and review receipt required')
    receipt = json.loads(receipt_path.read_text())
    source = json.loads(authority.read_text())
    if receipt.get('format') != 'original-site-review-v1':
        raise ValueError('original site review receipt format required')
    if receipt.get('opendrive_sha256') != _sha(opendrive) or receipt.get('authority_sha256') != _sha(authority):
        raise ValueError('reviewed site source hash differs')
    if (receipt.get('map_name') != source.get('map_name') or
            receipt.get('coordinate_frame') != source.get('coordinate_frame') or
            receipt.get('property_id') != property_id):
        raise ValueError('reviewed site identity differs')
    review = receipt.get('review', {})
    if (not isinstance(review, dict) or not review.get('reviewer') or
            not review.get('source') or review.get('decision') != 'reviewed' or
            not receipt.get('reviewed_at') or not receipt.get('source_record_id')):
        raise ValueError('separate source review and provenance required')
    packet = bind(opendrive, authority, property_id=property_id,
                  intersecting_street_id=source['intersecting_street_id'],
                  connector_routes=source['connector_routes'],
                  roadway_route=source.get('roadway_route'), review=review)
    return {'packet': packet, 'review_receipt_sha256': _sha(receipt_path),
            'source_record_id': receipt['source_record_id'],
            'physical_acceptance_claimed': False}
