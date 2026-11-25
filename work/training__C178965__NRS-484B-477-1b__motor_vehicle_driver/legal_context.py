"""Copy an independently reviewed legal-context packet into the original attempt.

The authored OpenDRIVE road does not by itself establish public-highway or
ordinance facts. This module never fills absent facts from the scene design.
"""
import hashlib
import json
from pathlib import Path

REQUIRED = (
    'public_highway_source_id', 'city_block_source_id',
    'rear_access_source_id', 'abutting_property_source_id',
    'non_culdesac_source_id', 'local_jurisdiction_source_id',
    'local_ordinance_review_source_id', 'other_alley_scope_review_source_id',
    'halt_purpose_review_source_id', 'occupant_activity_review_source_id',
    'traffic_conflict_review_source_id', 'official_direction_review_source_id',
)


def review_source(path, destination):
    source = Path(path)
    if not source.is_file():
        raise ValueError('Independent alley/ordinance source packet missing')
    raw = source.read_bytes()
    packet = json.loads(raw)
    if packet.get('format') != 'c178965-independent-alley-context-v1':
        raise ValueError('Independent alley/ordinance source format differs')
    if packet.get('review_status') != 'independently_reviewed' or not packet.get('reviewer'):
        raise ValueError('Alley/ordinance source lacks independent review')
    references = packet.get('references')
    if not isinstance(references, list) or not references:
        raise ValueError('Alley/ordinance source references missing')
    for item in references:
        if not isinstance(item, dict) or not item.get('path') or not item.get('sha256'):
            raise ValueError('Alley/ordinance source reference incomplete')
    if any(not isinstance(packet.get(key), str) or not packet[key].strip() for key in REQUIRED):
        raise ValueError('Alley/ordinance source fact binding missing')
    if packet.get('ordinance_effect') not in ('no_override_found', 'override_found', 'undetermined'):
        raise ValueError('Alley/ordinance effect review missing')
    if packet.get('site_match_review') not in ('matched', 'not_matched', 'undetermined'):
        raise ValueError('Native alley site-match review missing')
    target = Path(destination)
    if target.exists():
        raise ValueError('Independent alley/ordinance source already copied')
    target.write_bytes(raw)
    return {'source_packet_sha256': hashlib.sha256(raw).hexdigest(),
            'review_status': packet['review_status'],
            'ordinance_effect': packet['ordinance_effect'],
            'site_match_review': packet['site_match_review'],
            **{key: packet[key] for key in REQUIRED}}
