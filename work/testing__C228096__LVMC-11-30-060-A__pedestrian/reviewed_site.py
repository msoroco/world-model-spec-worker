"""Require reviewed original outside-crosswalk sources before Native mutation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ASSIGNMENT = 'testing__C228096__LVMC-11-30-060-A__pedestrian'
REQUIRED = {'opendrive', 'roadway', 'crosswalk_inventory', 'pedestrian_route',
            'vehicle_routes', 'prohibited_place', 'cameras'}
CAMERAS = {'overview', 'approach', 'reference_corner', 'driver_reference'}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inside(point: list, polygon: list) -> bool:
    if (not isinstance(point, list) or len(point) != 2
            or not isinstance(polygon, list) or len(polygon) < 3):
        raise ValueError('reviewed crossing polygon or point invalid')
    x, y = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        if not isinstance(current, list) or len(current) != 2:
            raise ValueError('reviewed crossing polygon vertex invalid')
        px, py = previous
        cx, cy = current
        if (cy > y) != (py > y):
            edge_x = cx + (y - cy) * (px - cx) / (py - cy)
            if x < edge_x:
                inside = not inside
        previous = current
    return inside


def load_review(packet: str | Path, source_root: str | Path, case_id: str) -> dict:
    packet = Path(packet).resolve()
    source_root = Path(source_root).resolve()
    review = json.loads(packet.read_text())
    if (review.get('assignment_id') != ASSIGNMENT or review.get('case_id') != case_id
            or review.get('cell_id') != 'C228096'):
        raise ValueError('reviewed outside-crosswalk source identity differs')
    provenance = review.get('source_provenance', {})
    if (provenance.get('kind') != 'original_reviewed_site'
            or provenance.get('diagnostic_fixture') is not False
            or not provenance.get('reviewer') or not provenance.get('citation')):
        raise ValueError('external original reviewed crossing site provenance required')
    sources = review.get('sources')
    if not isinstance(sources, dict) or not REQUIRED <= set(sources):
        raise ValueError('reviewed outside-crosswalk source inventory incomplete')
    loaded = {}
    for name in sorted(REQUIRED):
        item = sources[name]
        if not isinstance(item, dict) or not item.get('path') or not item.get('sha256'):
            raise ValueError('reviewed crossing source binding missing: ' + name)
        path = (source_root / item['path']).resolve()
        if not path.is_relative_to(source_root) or not path.is_file():
            raise ValueError('reviewed crossing source path invalid: ' + name)
        if sha(path) != item['sha256']:
            raise ValueError('reviewed crossing source hash differs: ' + name)
        loaded[name] = path.read_text() if name == 'opendrive' else json.loads(path.read_text())
    roadway = loaded['roadway']
    inventory = loaded['crosswalk_inventory']
    route = loaded['pedestrian_route']
    place = loaded['prohibited_place']
    vehicles = loaded['vehicle_routes']
    if (not roadway.get('roadway_id') or not roadway.get('roadway_polygon_xy_m')
            or not roadway.get('intersection_polygons_xy_m')):
        raise ValueError('original roadway and intersection geometry required')
    if (inventory.get('roadway_id') != roadway['roadway_id']
            or not isinstance(inventory.get('marked_crosswalk_polygons_xy_m'), list)
            or not isinstance(inventory.get('unmarked_intersection_crosswalk_polygons_xy_m'), list)
            or not inventory.get('classification_method')):
        raise ValueError('both original crosswalk categories require reviewed inventory')
    if (route.get('roadway_id') != roadway['roadway_id']
            or not route.get('crossing_point_id') or not route.get('pedestrian_actor_id')
            or not route.get('crossing_point_xy_m')
            or not route.get('approach_xy_m') or not route.get('exit_xy_m')
            or route.get('within_marked_crosswalk') is not False
            or route.get('within_unmarked_intersection_crosswalk') is not False):
        raise ValueError('reviewed pedestrian route is not proven outside both crosswalk categories')
    point = route['crossing_point_xy_m']
    if not _inside(point, roadway['roadway_polygon_xy_m']):
        raise ValueError('reviewed crossing point is not within roadway')
    for category in ('marked_crosswalk_polygons_xy_m',
                     'unmarked_intersection_crosswalk_polygons_xy_m'):
        if any(_inside(point, polygon) for polygon in inventory[category]):
            raise ValueError('reviewed crossing point lies within ' + category)
    if (place.get('crossing_point_id') != route['crossing_point_id']
            or type(place.get('prohibited_place_under_11_30_070')) is not bool
            or not place.get('source_review')):
        raise ValueError('11.30.070 place exception needs independent source review')
    if (not isinstance(vehicles.get('vehicle_actor_ids'), list)
            or not vehicles.get('roadway_inventory_method')
            or not vehicles.get('routes_xy_m')):
        raise ValueError('all roadway vehicle inventory and routes required')
    cameras = loaded['cameras']
    if not isinstance(cameras, dict) or set(cameras) != CAMERAS:
        raise ValueError('four reviewed camera poses required')
    for name, pose in cameras.items():
        if (not isinstance(pose, dict) or len(pose.get('location_xyz_m', [])) != 3
                or len(pose.get('pitch_yaw_roll_deg', [])) != 3):
            raise ValueError('reviewed camera pose invalid: ' + name)
    return {'review': review, 'packet_sha256': sha(packet),
            'sources': loaded, 'source_root': str(source_root)}
