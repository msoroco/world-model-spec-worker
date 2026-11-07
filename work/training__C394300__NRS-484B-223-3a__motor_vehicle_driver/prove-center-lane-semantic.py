"""Check the 3(a) authored center-lane segments against exact Core output."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from shapely.geometry import Point,Polygon

FOLDER=Path(__file__).resolve().parent
SEGMENTS={1:(-40,0),14:(-9.5,0),2:(10,0)}


def sha(data):return hashlib.sha256(data).hexdigest()


def source_regions(xodr):
    root=ET.fromstring(xodr);regions=[]
    for road_id,point in SEGMENTS.items():
        road=root.find(f"./road[@id='{road_id}']")
        if road is None:raise ValueError('Source center-lane road absent')
        geometry=road.find('./planView/geometry')
        if geometry is None or geometry.find('line') is None or abs(float(geometry.attrib['hdg']))>1e-9:
            raise ValueError('Center-lane geometry changed')
        sections=road.findall('./lanes/laneSection')
        if len(sections)!=1 or float(sections[0].attrib['s'])!=0:
            raise ValueError('Center-lane section changed')
        lane=sections[0].find("./right/lane[@id='-1']")
        if lane is None or lane.attrib.get('type')!='bidirectional':
            raise ValueError('Bidirectional center lane absent')
        use=lane.find("userData[@code='lane_use']")
        if use is None or use.attrib.get('value')!='left_turn_only_both_directions':
            raise ValueError('Turn-only bidirectional lane designation absent')
        widths=lane.findall('width')
        if len(widths)!=1 or any(abs(float(widths[0].attrib.get(k,0)))>1e-9
                              for k in ('sOffset','b','c','d')):
            raise ValueError('Center-lane width profile changed')
        width=float(widths[0].attrib['a'])
        offsets=road.findall('./lanes/laneOffset')
        if width<=0 or len(offsets)!=1 or any(abs(float(offsets[0].attrib.get(k,0)))>1e-9
                    for k in ('s','a','b','c','d')):
            raise ValueError('Center-lane width or offset changed')
        x,y,length=(float(geometry.attrib[k]) for k in ('x','y','length'))
        if abs(length-float(road.attrib['length']))>1e-9:
            raise ValueError('Center-lane road length changed')
        polygon=Polygon(((x,y),(x+length,y),(x+length,y-width),(x,y-width)))
        if not polygon.is_valid or not polygon.covers(Point(*point)):
            raise ValueError('Center lane misses surveyed point')
        regions.append({'road_id':road_id,'lane_section':0,'lane_id':-1,
            'native_lane_type':'bidirectional','authored_use':use.attrib['value'],
            'boundary':[[float(a),float(b)] for a,b in list(polygon.exterior.coords)[:-1]],
            'area_m2':round(polygon.area,6),'survey_point_xy_m':list(point),
            'source_xodr_sha256':sha(xodr.encode())})
    return regions


def check_converted(regions,converted):
    scenes=converted.get('scenes',[])
    if not scenes:raise ValueError('Converted Core scenes absent')
    coverage=[]
    for region in regions:
        point=Point(*region['survey_point_xy_m'])
        count=sum(any(row.get('kind')=='lane' and Polygon(row['boundary']).covers(point)
                      for row in scene['structures']) for scene in scenes)
        coverage.append({'road_id':region['road_id'],'point':region['survey_point_xy_m'],
                         'core_scenes_covering_point':count})
    return {'core_scene_count':len(scenes),'source_regions':regions,
        'source_semantics_checked':True,'coverage':coverage,
        'core_semantics_passed':all(row['core_scenes_covering_point']==len(scenes)
                                    for row in coverage)}


def main():
    source=(FOLDER/'draft-construction/scene.xodr').read_text()
    regions=source_regions(source)
    lines=(FOLDER/'probe-package-controlled_1-primary.log').read_text().splitlines()
    if not lines or not lines[0].startswith('scratch '):
        raise ValueError('Exact package log absent')
    converted_path=Path(lines[0][8:])/'output/converted/trace.json'
    converted_bytes=converted_path.read_bytes()
    result=check_converted(regions,json.loads(converted_bytes))
    result['converted_trace_sha256']=sha(converted_bytes)
    result['scope']='authored source and exact synthetic Core output; no Native or physical proof'
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
