"""Pinned source-map parser and reflected route audit; no CARLA execution."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from geometry import authored_route,native_route,open_drive
from traffic_spec_adapter.geometry import static_map
from shapely.geometry import Point


def run():
    source=open_drive()
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c104538-map-audit-') as temp:
        path=Path(temp)/'road.xodr';path.write_text(source)
        regions,polygons,lanes=static_map(path)
    if set(lanes)!={(1,0,-1),(1,0,1)} or len(regions)!=3:
        raise ValueError('Pinned parser did not recover opposed driving lanes')
    root=ET.fromstring(source);signal=root.find('road/signals/signal')
    if signal is None or signal.attrib.get('name')!='no_u_turn_prohibition_proposal':
        raise ValueError('Authored prohibition cue missing')
    pavement=polygons[3]
    records=[]
    for suffix in ('witness_1','witness_2'):
        native=native_route(suffix);authored=authored_route(suffix)
        if len(native)!=len(authored) or any((x,-y)!=tuple(a) for (x,y),a in zip(native,authored)):
            raise ValueError('Authored/Native route reflection mismatch')
        if not all(pavement.covers(Point(*point)) for point in authored):
            raise ValueError('Pinned authored roadway excludes route point')
        records.append({'case_suffix':suffix,'route_points':len(native),
                        'start_native_xy_m':native[0],'end_native_xy_m':native[-1]})
    return {'passed':True,'pinned_source_map_regions':len(regions),
            'authored_map_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'records':records,'official_sign_native_readback':False,
            'physical_vehicle_turn_verified':False}


if __name__=='__main__':print(json.dumps(run(),indent=2))
