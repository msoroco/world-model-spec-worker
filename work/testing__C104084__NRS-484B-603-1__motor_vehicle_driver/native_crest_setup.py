"""Lazy Native map loading and source-bound C104084 route setup.

This helper is called by a future capture runner. It does not import or connect
to CARLA itself, and it never treats an authored map as observed vehicle motion.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from crest_route import survey_map_pair


def _road_profile(text):
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise ValueError('valid original OpenDRIVE XML required') from error
    road = root.find(".//road[@id='603']")
    if road is None:
        raise ValueError('original C104084 crest road 603 missing')
    profile = road.find('elevationProfile/elevation')
    if profile is None or float(profile.get('s', 'nan')) != 0:
        raise ValueError('original crest elevation profile missing')
    coefficients = tuple(float(profile.get(key)) for key in ('a', 'b', 'c', 'd'))
    if not all(math.isfinite(value) for value in coefficients):
        raise ValueError('finite original crest profile required')
    driving = {int(lane.get('id')) for lane in road.findall('.//lane')
               if lane.get('type') == 'driving'}
    if not {-1, 1}.issubset(driving):
        raise ValueError('two opposite original driving lanes required')
    return float(road.get('length')), coefficients


def load_and_bind(client, map_path, *, expected_file_sha256):
    """Load exact authored XODR, then verify the loaded Native geometry.

    The returned map hash comes from Native `to_opendrive`, not the authored
    file. It must be retained in the acquisition packet before frame capture.
    """
    source = Path(map_path).read_bytes()
    if hashlib.sha256(source).hexdigest() != expected_file_sha256:
        raise ValueError('authored crest map file hash differs')
    authored_profile = _road_profile(source.decode('utf-8'))
    world = client.generate_opendrive_world(source.decode('utf-8'))
    native_map = world.get_map()
    loaded_text = native_map.to_opendrive()
    if _road_profile(loaded_text) != authored_profile:
        raise ValueError('loaded Native crest geometry differs from authored source')
    first = native_map.get_waypoint_xodr(603, -1, 230.0)
    opposite = native_map.get_waypoint_xodr(603, 1, 270.0)
    if first is None or opposite is None:
        raise ValueError('original opposing spawn lanes unavailable')
    native_sha256 = hashlib.sha256(loaded_text.encode('utf-8')).hexdigest()
    routes = survey_map_pair(native_map, first, opposite,
                             expected_map_sha256=native_sha256, step_m=5.0, count=9)
    return {'world': world, 'map_file_sha256': expected_file_sha256,
            'native_map_sha256': native_sha256, 'routes': routes,
            'native_spawn_stations': {'ego_road_s_m': 230.0,
                                      'other_road_s_m': 270.0},
            'limitation': 'Loaded map and lane continuity only; vehicle motion and visibility require original capture.'}
