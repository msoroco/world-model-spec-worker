"""Bind reviewed intersection geometry to the original Native OpenDRIVE map."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_retained(packet_path, source_path, scene):
    packet_path=Path(packet_path);source_path=Path(source_path)
    packet=json.loads(packet_path.read_text())
    source=source_path.read_bytes()
    if packet.get('format')!='c111125-reviewed-map-installation-v1':
        raise ValueError('map review format invalid')
    if not packet.get('reviewer') or packet.get('review_method')!='original-opendrive-and-installed-signal-review':
        raise ValueError('independent map installation review missing')
    if not source or packet.get('map_sha256')!=sha(source):
        raise ValueError('reviewed OpenDRIVE source hash mismatch')
    root=ET.fromstring(source)
    if root.tag!='OpenDRIVE':raise ValueError('source is not OpenDRIVE')
    route=packet.get('route')
    if not isinstance(route,dict) or type(route.get('road_id')) is not int or type(route.get('lane_id')) is not int:
        raise ValueError('reviewed route identity missing')
    if not any(road.get('id')==str(route['road_id']) for road in root.findall('road')):
        raise ValueError('reviewed road absent from original OpenDRIVE')
    for key in ('intersection_bounds_m','adjacent_crosswalk_bounds_m','stop_line_x_m'):
        if packet.get(key)!=scene[key]:
            raise ValueError('reviewed map geometry differs from authored scene: '+key)
    if not packet.get('geometry_source_ref') or not packet.get('signal_installation_source_ref'):
        raise ValueError('reviewed geometry or signal installation source reference missing')
    return {'packet_sha256':sha(packet_path.read_bytes()),'map_sha256':sha(source),
            'road_id':route['road_id'],'lane_id':route['lane_id'],'reviewer':packet['reviewer']}


def validate(packet_path, source_path, scene, mapping, carla):
    receipt=verify_retained(packet_path,source_path,scene)
    source=Path(source_path).read_bytes()
    if source!=mapping.to_opendrive().encode('utf-8'):
        raise ValueError('reviewed OpenDRIVE differs from live Native map')
    points=[]
    for x in (scene['approach_x_m'],scene['stop_line_x_m'],scene['exit_x_m']):
        wp=mapping.get_waypoint(carla.Location(x=x,y=0,z=0))
        if wp is None or (wp.road_id,wp.lane_id)!=(receipt['road_id'],receipt['lane_id']):
            raise ValueError('reviewed route differs from original driving waypoints')
        points.append([wp.road_id,wp.lane_id])
    return {**receipt,'sampled_waypoints':points}
