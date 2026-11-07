"""Reproduce the current Core map projection of the authored turn lane on CPU."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from traffic_spec_adapter.geometry import static_map
from shapely.geometry import Point, Polygon


def main():
    spec=importlib.util.spec_from_file_location('authored_geometry',HERE/'native/geometry.py')
    geometry=importlib.util.module_from_spec(spec);spec.loader.exec_module(geometry)
    source=geometry.open_drive()
    root=ET.fromstring(source)
    lane=root.find("./road[@id='1']/lanes/laneSection/right/lane[@id='-1']")
    if lane is None or lane.attrib['type']!='bidirectional':
        raise ValueError('Current authored bidirectional lane absent')
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c394300-core-map-') as temp:
        path=Path(temp)/'road.xodr';path.write_text(source)
        regions,_,keys=static_map(path)
    present=(1,0,-1) in keys
    if present:
        raise ValueError('Pinned adapter behavior changed; reassess center-lane projection')
    package_log=(HERE/'package-compatibility-witness_1.log').read_text().splitlines()
    if not package_log or not package_log[0].startswith('scratch '):
        raise ValueError('Current exact package fixture absent')
    package=Path(package_log[0][8:])/'output/converted/trace.json'
    scene=json.loads(package.read_text())['scenes'][0]
    converted_center=any(row.get('kind')=='lane' and
        Polygon(row['boundary']).covers(Point(-40,0)) for row in scene['structures'])
    if converted_center:
        raise ValueError('Current exact Core trace unexpectedly contains center turn lane')
    print(json.dumps({'authored_center_lane_type':lane.attrib['type'],
        'authored_turn_only_intent':lane.find("userData[@code='lane_use']").attrib['value'],
        'core_center_lane_key_present':present,
        'exact_v1_converted_center_lane_region_present':converted_center,
        'core_regions':len(regions),'core_lane_keys':len(keys),
        'scope':'CPU reproducer of pinned map projection; v1 package pass does not prove center-turn-lane Core structure'}))


if __name__=='__main__':main()
