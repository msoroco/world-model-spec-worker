"""Controlled railroad and one-way saved-source polarity negatives."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
from xml.etree import ElementTree as ET

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from geometry_statutory import CASES,open_drive
from statutory_context import inspect

def write(path,value):path.write_text(json.dumps(value,sort_keys=True)+'\n')

def main():
    frames=list(range(1000,1480));rows=[]
    with tempfile.TemporaryDirectory(dir=HERE.parents[1]/'.runtime-work',prefix='c110454-213-source-') as temp:
        root=Path(temp);packet_path=root/'statutory_context.json';survey_path=root/'road_geometry.json';road_path=root/'road.xodr'
        for suffix,spec in CASES.items():
            one_way=spec['one_way'];rail=suffix.startswith('rail_')
            directions={'approach_forward':[1,0],
                'approach_opposing':[1,0] if one_way else [-1,0],
                'destination_forward':[1,0],
                'destination_opposing':[1,0] if one_way else [-1,0]}
            survey={'native_map_sha256':'a'*64,'road_directions_native':directions,
                'approach_boundary_x_m':spec['boundary_x_m']}
            packet={'source_kind':'native_statutory_context_schema','case_suffix':suffix,
                'zone_kind':spec['zone'],'one_way':one_way,'railroad_crossing':rail,
                'railroad_crossing_object_id':'701' if rail else None,
                'boundary_x_m':spec['boundary_x_m'],'native_map_sha256':'a'*64,
                'original_frames':frames,'road_directions_native':directions,
                'physical_observation_claimed':False,'legal_verdict':None}
            write(survey_path,survey);write(packet_path,packet);road_path.write_text(open_drive(suffix))
            passed=inspect(packet_path,suffix,frames,survey_path,road_path)
            if passed['applicability']!='requires_independent_review':raise ValueError('Unreviewed applicability claimed')
            changed=json.loads(json.dumps(packet))
            if rail:changed['railroad_crossing']=False
            elif one_way:changed['one_way']=False
            else:changed['road_directions_native']['approach_opposing']=[1,0]
            write(packet_path,changed)
            try:inspect(packet_path,suffix,frames,survey_path,road_path)
            except ValueError as error:negative=str(error)
            else:raise ValueError('Changed statutory source passed: '+suffix)
            write(packet_path,packet)
            root_xml=ET.fromstring(road_path.read_text())
            if rail:
                object_node=root_xml.find(".//object[@id='701']")
                for parent in root_xml.iter():
                    if object_node in list(parent):parent.remove(object_node);break
            else:
                approach=next(r for r in root_xml.findall('road') if r.attrib['id']=='1')
                lane=approach.find('lanes/laneSection/right/lane')
                lane.attrib['id']='-9'
            road_path.write_text(ET.tostring(root_xml,encoding='unicode'))
            try:inspect(packet_path,suffix,frames,survey_path,road_path)
            except ValueError as error:asset_negative=str(error)
            else:raise ValueError('Changed authored road passed: '+suffix)
            rows.append({'case_suffix':suffix,'positive_source_complete':True,
                'changed_context_negative':negative,'changed_road_negative':asset_negative,
                'physical_observation_claimed':False,'legal_verdict':None})
    return {'format':'c110454-213-controlled-statutory-source-v1','passed':True,'rows':rows,
        'scope':'synthetic source identity only; actual Native geometry and legal exception pending'}

if __name__=='__main__':print(json.dumps(main(),indent=2))
