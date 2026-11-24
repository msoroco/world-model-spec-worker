"""Compare authored crosswalk vertices with the loaded Native map readback.

Matching vertices are a geometry prerequisite, not proof of paint visibility,
curb identity, municipal jurisdiction, or a legal route classification.
"""
from __future__ import annotations

import hashlib
import math

from crossing_geometry import point, validate_scene


def audit_crosswalk_map(scene, map_obj, vertex_tolerance_m=0.5):
    validate_scene(scene)
    if not isinstance(vertex_tolerance_m, (int, float)) or not math.isfinite(vertex_tolerance_m) or not 0 < vertex_tolerance_m <= 1:
        raise ValueError('Native crosswalk vertex tolerance invalid')
    original_xodr = map_obj.to_opendrive()
    if not isinstance(original_xodr, str) or not original_xodr:
        raise ValueError('loaded Native OpenDRIVE missing')
    loaded_hash = hashlib.sha256(original_xodr.encode('utf-8')).hexdigest()
    if loaded_hash != scene.get('map_source_sha256'):
        raise ValueError('loaded Native map source differs from exact scene')
    observed = map_obj.get_crosswalks()
    if not isinstance(observed, (list, tuple)) or len(observed) < 4:
        raise ValueError('Native crosswalk vertex readback missing')
    vertices = []
    for location in observed:
        xyz = (float(location.x), float(location.y), float(location.z))
        if not all(math.isfinite(value) for value in xyz):
            raise ValueError('nonfinite Native crosswalk vertex')
        vertices.append([xyz[0], xyz[1]])
    polygon_matches = []
    for polygon in scene['crosswalk_boundaries_xy_m']:
        matched = []
        for raw in polygon:
            authored = point(raw)
            distance = min(math.dist(authored, candidate) for candidate in vertices)
            if distance > vertex_tolerance_m:
                raise ValueError('authored crosswalk vertex absent from Native map')
            matched.append(distance)
        polygon_matches.append({'vertices': len(polygon),
                                'maximum_vertex_readback_gap_m': max(matched)})
    return {'case_id': scene['case_id'], 'loaded_map_sha256': loaded_hash,
            'native_crosswalk_vertices': len(vertices),
            'authored_polygon_readbacks': polygon_matches,
            'curb_identity': 'unverified', 'paint_visibility': 'unverified',
            'municipal_jurisdiction': 'unverified',
            'legal_route_classification': 'unresolved'}
