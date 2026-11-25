"""Join independent municipal source records to an original parking inventory.

This verifies provenance and explicit source assertions. It does not decide
whether the legal designation, posting, or vehicle classification is sufficient.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ASSIGNMENT = 'training__C150129__LVMC-11-52-340__motor_vehicle_driver'
SOURCE_FIELDS = ('city_street', 'council_designation', 'posting_or_marking',
                 'subject_vehicle_status')


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _source(attempt: Path, record: dict, field: str):
    _require(isinstance(record, dict), 'Missing independent source record: ' + field)
    name = record.get('path')
    _require(isinstance(name, str) and name.startswith('source_context/'),
             'Invalid independent source path: ' + field)
    relative = Path(name)
    _require(not relative.is_absolute() and '..' not in relative.parts and len(relative.parts) == 2,
             'Invalid independent source path: ' + field)
    source = attempt / relative
    _require(source.is_file() and source.stat().st_size > 0,
             'Missing independent source bytes: ' + field)
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    _require(record.get('sha256') == checksum,
             'Independent source hash differs: ' + field)
    _require(isinstance(record.get('source_id'), str) and record['source_id'].strip(),
             'Independent source ID missing: ' + field)
    _require(isinstance(record.get('review_method'), str) and record['review_method'].strip(),
             'Independent review method missing: ' + field)
    return record


def join(attempt: Path, inventory: dict, review: dict):
    """Return a source-bound copy; never mutate original Native inventory."""
    attempt = Path(attempt)
    _require(inventory.get('assignment_id') == ASSIGNMENT and review.get('assignment_id') == ASSIGNMENT,
             'Municipal source assignment mismatch')
    _require(review.get('format') == 'c150129-independent-source-review-v1',
             'Unknown independent source review')
    _require(review.get('case_id') in (
        ASSIGNMENT + '__controlled_1', ASSIGNMENT + '__controlled_2'),
        'Independent source review binds another case')
    original_path = attempt / 'parking-inventory.json'
    _require(original_path.is_file() and
             review.get('native_inventory_sha256') == hashlib.sha256(original_path.read_bytes()).hexdigest(),
             'Independent review binds another Native inventory')
    _require(inventory.get('space_id') and inventory.get('space_polygon_xy_m'),
             'Native parking space geometry missing')
    records = {field: _source(attempt, review.get(field), field) for field in SOURCE_FIELDS}
    street, designation, posting, status = (records[field] for field in SOURCE_FIELDS)
    _require(street.get('is_city_street') is True, 'City-street jurisdiction unconfirmed')
    _require(designation.get('designated_for_city_vehicles') is True and
             designation.get('space_id') == inventory['space_id'],
             'City Council designated-space association unconfirmed')
    _require(posting.get('posted_or_marked') is True and
             posting.get('space_id') == inventory['space_id'],
             'Posted-space association unconfirmed')
    _require(status.get('subject_city_vehicle') is False,
             'Non-City subject vehicle status unconfirmed')
    out = dict(inventory)
    out.update(city_street_source_id=street['source_id'],
               council_designation_source_id=designation['source_id'],
               posting_or_marking_source_id=posting['source_id'],
               posting_space_id=posting['space_id'],
               subject_status_source_id=status['source_id'],
               subject_city_vehicle=False,
               source_review_sha256=hashlib.sha256(
                   (attempt / 'review.json').read_bytes()).hexdigest(),
               source_review_status='source assertions joined; legal sufficiency unreviewed')
    return out
