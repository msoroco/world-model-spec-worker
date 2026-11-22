"""Verify a selected median site against retained, hash-bound review sources.

This checks provenance and internal consistency. It does not establish a real
crossing, an official sign, or legal acceptance.
"""
import hashlib
import json
from pathlib import Path


SOURCE_CLAIMS = {
    'crossing_geometry_source': ('native_map_name', 'intersection_id',
                                 'crossing_polygon_xy_m', 'same_statutory_crossing',
                                 'approaches', 'ego_yield_line_xy_m'),
    'all_entrances_source': ('intersection_id', 'all_entrance_road_lanes'),
    'sign_governance_source': ('yield_sign', 'all_entrance_road_lanes'),
    'sign_face_video_source': ('yield_sign',),
    'median_spacing_source': ('intersection_id', 'same_statutory_crossing'),
}


def _bound_json(root, ref, label):
    if not isinstance(ref, dict) or set(ref) != {'path', 'sha256'}:
        raise ValueError('Hashed ' + label + ' reference required')
    relative = Path(ref['path'])
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError(label + ' must be local to assignment')
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(label + ' source missing')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != ref['sha256']:
        raise ValueError(label + ' SHA mismatch')
    return json.loads(data), path


def verify_site_packet(config, assignment_dir):
    root = Path(assignment_dir)
    scene, packet_path = _bound_json(root, config.get('site_packet'), 'Site packet')
    if (not isinstance(scene, dict) or
            scene.get('format') != 'worker-yield-median-site-review' or
            scene.get('review_status') != 'reviewed_candidate'):
        raise ValueError('Structured reviewed median site packet required')
    refs = scene.get('source_refs')
    docs = scene.get('source_documents')
    if (not isinstance(refs, dict) or set(refs) != set(SOURCE_CLAIMS) or
            not isinstance(docs, dict) or set(docs) != set(SOURCE_CLAIMS)):
        raise ValueError('Complete site source inventory required')
    for role, required in SOURCE_CLAIMS.items():
        document, source_path = _bound_json(root, docs[role], role)
        if refs[role] != str(source_path.relative_to(root.resolve())):
            raise ValueError(role + ' reference differs from bound source')
        if (not isinstance(document, dict) or
                document.get('format') != 'worker-yield-median-site-source' or
                document.get('source_role') != role or
                not isinstance(document.get('review_basis'), str) or
                not document['review_basis'].strip() or
                not isinstance(document.get('reviewed_site_fields'), dict)):
            raise ValueError('Structured review source required: ' + role)
        claims = document['reviewed_site_fields']
        if not set(required) <= set(claims):
            raise ValueError('Missing reviewed site claims: ' + role)
        if any(scene.get(key) != value for key, value in claims.items()):
            raise ValueError('Site differs from reviewed source: ' + role)
    return scene
