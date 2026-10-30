"""Explicit software-only Native-shaped map-landmark diagnostic authoring.

Call only while constructing a diagnostic fixture, before sealing. This does
not establish Native actor creation, crop inclusion, visibility or authority.
"""
import hashlib
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def augment_graph(graph, scene_path):
    scene_path = Path(scene_path)
    source_hash = hashlib.sha256(scene_path.read_bytes()).hexdigest()
    added = []
    for road in ET.parse(scene_path).getroot().findall('road'):
        for signal in road.findall('./signals/signal'):
            if signal.get('type') != '274':
                continue
            identity = signal.attrib['id']
            # Never overwrite original observations or duplicate their identities.
            if any(str(a.get('landmark_id')) == identity for _, a in graph.nodes(data=True)):
                continue
            station, offset = float(signal.attrib['s']), float(signal.attrib['t'])
            geometry = next((g for g in reversed(road.findall('./planView/geometry')) if float(g.attrib['s']) <= station), None)
            if geometry is None or geometry.find('line') is None:
                raise ValueError('Diagnostic landmark author supports explicit line geometry only')
            heading = float(geometry.attrib['hdg']); progress = station-float(geometry.attrib['s'])
            x = float(geometry.attrib['x'])+progress*math.cos(heading)-offset*math.sin(heading)
            y = float(geometry.attrib['y'])+progress*math.sin(heading)+offset*math.cos(heading)
            value = float(signal.attrib['value']); unit = signal.attrib['unit']
            if not all(math.isfinite(v) for v in (x,y,value)) or unit.lower() not in ('mph','km/h','m/s'):
                raise ValueError('Invalid diagnostic speed sign value/unit/position')
            node = 'diagnostic_landmark_'+identity
            if node in graph:
                raise ValueError('Diagnostic landmark node collision')
            graph.add_node(node, sem_class='landmark_'+signal.get('country','')+'_274_'+signal.get('subtype',''), landmark_id=identity,
                           landmark_type='274', landmark_value=value, landmark_unit=unit,
                           vertex=[x,-y,float(signal.get('zOffset','0'))],
                           diagnostic_fixture=True, diagnostic_authoring_source=str(scene_path.name),
                           diagnostic_authoring_sha256=source_hash,
                           diagnostic_scope='Software-authored map landmark; Native realization, crop inclusion, visibility and authority unverified')
            # No controlsTrafficOf/governs relationship is inferred from map authorship.
            added.append(node)
    return {'added_nodes':added,'scene_sha256':source_hash,'software_fixture_only':True,'physical_acceptance_claimed':False}
