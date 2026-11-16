"""Source-bound Native junction district review for signal-distance planning.

This binds a reviewed source polygon, without claiming legal classification.
"""
import hashlib
import json
from pathlib import Path
from shapely.geometry import Polygon


def verify_district_site_packet(context, native_map_name, packet_path):
    """Bind a selected Native junction to a reviewed district polygon source.

    This is a source and geometry check, not a legal district determination.
    The source document must be independently reviewed before a real capture.
    """
    packet_path = Path(packet_path)
    packet = json.loads(packet_path.read_text())
    if (packet.get('format') != 'c109749-district-site-review-v1'
            or packet.get('review_status') != 'candidate_reviewed'
            or packet.get('native_map_name') != native_map_name
            or packet.get('native_junction_id') != context['native_junction_id']
            or packet.get('junction_polygon_xy_m') != context['intersection_polygon_xy_m']):
        raise ValueError('Reviewed district packet differs from selected Native junction')
    source = packet.get('district_source')
    if not isinstance(source, dict) or set(source) != {'path', 'sha256'}:
        raise ValueError('Hashed independent district source required')
    source_path = Path(source['path'])
    if not source_path.is_absolute():
        source_path = packet_path.parent / source_path
    if (not source_path.is_file()
            or hashlib.sha256(source_path.read_bytes()).hexdigest() != source['sha256']):
        raise ValueError('District source missing or changed')
    document = json.loads(source_path.read_text())
    if (document.get('format') != 'c109749-district-polygon-source-v1'
            or document.get('native_map_name') != native_map_name
            or document.get('district_class') != 'business_or_residential'
            or not isinstance(document.get('review_basis'), str)
            or not document['review_basis'].strip()
            or not isinstance(document.get('source_origin'), str)
            or not document['source_origin'].strip()
            or type(document.get('diagnostic_only')) is not bool):
        raise ValueError('District source identity or review basis invalid')
    district = Polygon(document.get('polygon_xy_m', []))
    junction = Polygon(context['intersection_polygon_xy_m'])
    if (district.is_empty or not district.is_valid or junction.is_empty
            or not junction.is_valid or not district.covers(junction)):
        raise ValueError('District polygon does not cover selected Native junction')
    return {'native_map_name': native_map_name,
            'native_junction_id': context['native_junction_id'],
            'district_class': document['district_class'],
            'packet_sha256': hashlib.sha256(packet_path.read_bytes()).hexdigest(),
            'source_sha256': source['sha256'],
            'diagnostic_only': document['diagnostic_only'],
            'physical_district_verified': False,
            'legal_verdict_asserted': False}

