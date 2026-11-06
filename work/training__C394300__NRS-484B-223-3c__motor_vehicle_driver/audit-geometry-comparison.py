"""Independent saved audit of the three unselected 3(c) route drafts."""
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

HERE=Path(__file__).resolve().parent
OUT=HERE/'draft-construction'
EXPECTED={'below_50_ft':45,'at_50_ft':50,'above_50_ft':55}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    map_path=OUT/'scene.xodr'
    root=ET.fromstring(map_path.read_text())
    roads={int(road.attrib['id']):road for road in root.findall('road')}
    assert set(roads)=={1,4,13}
    assert roads[13].find('planView/geometry/arc') is not None
    assert root.find('junction/connection').attrib['incomingRoad']=='4'
    assert root.find('junction/connection').attrib['connectingRoad']=='13'
    assert [(link.attrib['from'],link.attrib['to']) for link in root.findall('junction/connection/laneLink')]==[('-1','-1')]
    routes={case:json.loads((OUT/f'route-{case}.json').read_text()) for case in EXPECTED}
    assert all(len(route)==2050 for route in routes.values())
    first=routes['below_50_ft']
    for route in routes.values():
        assert route[:550]==first[:550], 'Turn approach differs across boundary probes'
        assert all(math.isclose(point[0],other[0],abs_tol=1e-9)
                   for point,other in zip(route,first)), 'Longitudinal path differs'
        assert all(point[1]==0 for point in route[550:]
                   if point[0]<-56), 'Center-lane approach changed'
    first_lateral={case:next(point[0] for point in route[550:] if point[1]<0)
                   for case,route in routes.items()}
    assert first_lateral['below_50_ft']<first_lateral['at_50_ft']<first_lateral['above_50_ft']
    assert abs(first_lateral['at_50_ft']-first_lateral['below_50_ft']-5*.3048)<.11
    assert abs(first_lateral['above_50_ft']-first_lateral['at_50_ft']-5*.3048)<.11
    proof=json.loads((OUT/'geometry-check.json').read_text())
    assert proof['passed'] is True and proof['native_center_lane_design_verified'] is False
    assert proof['native_connector_identity_verified'] is False
    print(json.dumps({'status':'authored_geometry_comparison_pass',
                      'map_sha256':sha(map_path), 'shared_turn_prefix_points':550,
                      'first_lateral_x_m':first_lateral,
                      'scope':'saved authored construction only; no CARLA or Native designation'},indent=2))


if __name__=='__main__':
    audit()
