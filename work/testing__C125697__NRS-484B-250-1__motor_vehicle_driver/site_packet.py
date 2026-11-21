"""Bind a median site candidate to retained, structured source reviews.

Hashes establish source identity, not statutory or physical acceptance.
"""
import hashlib
import json
from pathlib import Path


SOURCE_FIELDS = (
    'crossing_polygon_source', 'approach_geometry_source',
    'median_spacing_source', 'all_entrances_source',
    'signal_governance_source', 'signal_head_video_source',
)
CLAIMS = (
    'native_map_name', 'crossing_id', 'ego_highway_id',
    'other_highway_id', 'same_statutory_crossing',
    'crossing_polygon_xy_m', 'entrance_road_lanes',
)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source_path(base, reference):
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError('Nonempty site source path required')
    path = Path(reference)
    return path if path.is_absolute() else Path(base) / path


def _read_bound(path, digest, label):
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError('Hashed ' + label + ' required')
    if not path.is_file() or _sha(path) != digest:
        raise ValueError(label + ' missing or changed')
    return json.loads(path.read_text())


def verify_site_packet(config, base_dir):
    reference = config.get('site_review')
    if not isinstance(reference, dict) or set(reference) != {'path', 'sha256'}:
        raise ValueError('Hashed median site review packet required')
    packet_path = _source_path(base_dir, reference['path'])
    packet = _read_bound(packet_path, reference['sha256'], 'Median site packet')
    site = config.get('site')
    if (not isinstance(packet, dict) or
            packet.get('format') != 'worker-median-site-review' or
            packet.get('review_status') != 'reviewed_candidate' or
            packet.get('site') != site):
        raise ValueError('Selected site differs from reviewed candidate packet')
    if (not isinstance(site, dict) or
            any(site.get(key) in (None, '') for key in CLAIMS) or
            site['ego_highway_id'] == site['other_highway_id'] or
            site['same_statutory_crossing'] is not True):
        raise ValueError('One sourced crossing of distinct highways required')
    docs = packet.get('source_documents')
    if not isinstance(docs, dict) or set(docs) != set(SOURCE_FIELDS):
        raise ValueError('Complete median site source inventory required')
    verified = {}
    for field in SOURCE_FIELDS:
        item = docs[field]
        if not isinstance(item, dict) or set(item) != {'path', 'sha256'}:
            raise ValueError('Hashed site source required: ' + field)
        if site.get(field) != item['path']:
            raise ValueError('Site source reference differs: ' + field)
        path = _source_path(packet_path.parent, item['path'])
        document = _read_bound(path, item['sha256'], field)
        if (not isinstance(document, dict) or
                document.get('format') != 'worker-median-site-source' or
                document.get('source_role') != field or
                not isinstance(document.get('review_basis'), str) or
                not document['review_basis'].strip() or
                not isinstance(document.get('reviewed_site_fields'), dict)):
            raise ValueError('Structured review required: ' + field)
        claims = document['reviewed_site_fields']
        if not claims:
            raise ValueError('Missing reviewed source claims: ' + field)
        if any(key not in site or site[key] != value
               for key, value in claims.items()):
            raise ValueError('Site claim differs from source: ' + field)
        verified[field] = {'path': str(path), 'sha256': item['sha256'],
                           'reviewed_site_fields': sorted(claims)}
    required_claims = {
        'crossing_polygon_source': {'native_map_name', 'crossing_id',
                                    'crossing_polygon_xy_m', 'same_statutory_crossing'},
        'approach_geometry_source': {'ego_highway_id', 'other_highway_id'},
        'median_spacing_source': {'same_statutory_crossing'},
        'all_entrances_source': {'entrance_road_lanes'},
        'signal_governance_source': {'entrance_road_lanes'},
        'signal_head_video_source': {'entrance_road_lanes'},
    }
    for field, keys in required_claims.items():
        if not keys <= set(verified[field]['reviewed_site_fields']):
            raise ValueError('Missing reviewed source claims: ' + field)
    return {'packet_path': str(packet_path), 'packet_sha256': reference['sha256'],
            'source_documents': verified, 'physical_site_verified': False,
            'statutory_identity_verified': False}
