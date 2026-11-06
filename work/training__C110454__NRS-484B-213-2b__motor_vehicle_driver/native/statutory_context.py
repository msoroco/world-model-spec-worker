"""Source-bound railroad and one-way context gate; no statutory verdict."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

CASES={
 'rail_reference':('railroad_crossing',False,-20.0,True),
 'rail_contrast':('railroad_crossing',False,-20.0,True),
 'oneway_absent':('intersection',False,-7.0,False),
 'oneway_present':('intersection',True,-7.0,False),
}

def inspect(path:Path, case:str, original_frames:list[int], road_geometry:Path, authored_road:Path):
    path=Path(path)
    if not path.is_file():raise ValueError('Missing required source: statutory_context.json')
    if case not in CASES:raise ValueError('Unknown statutory alternative')
    packet=json.loads(path.read_text())
    zone,one_way,boundary,rail=CASES[case]
    if packet.get('source_kind')!='native_statutory_context_schema' or packet.get('case_suffix')!=case:
        raise ValueError('Statutory context identity differs')
    if packet.get('original_frames')!=original_frames:
        raise ValueError('Statutory context does not join all original frames')
    if any(packet.get(key)!=value for key,value in (
        ('zone_kind',zone),('one_way',one_way),('railroad_crossing',rail),('boundary_x_m',boundary))):
        raise ValueError('Statutory branch context differs')
    if not road_geometry.is_file():raise ValueError('Missing required source: road_geometry.json')
    survey=json.loads(road_geometry.read_text())
    if packet.get('native_map_sha256')!=survey.get('native_map_sha256'):
        raise ValueError('Native statutory map readback hash differs')
    if packet.get('road_directions_native')!=survey.get('road_directions_native'):
        raise ValueError('Native statutory lane directions differ')
    directions=packet['road_directions_native']
    expected=[1,0] if one_way else [-1,0]
    if directions.get('approach_opposing')!=expected or directions.get('destination_opposing')!=expected:
        raise ValueError('One-way Native direction survey differs')
    root=ET.fromstring(Path(authored_road).read_text())
    rails=root.findall(".//object[@id='701']")
    if bool(rails)!=rail or packet.get('railroad_crossing_object_id')!=('701' if rail else None):
        raise ValueError('Railroad crossing authored/native source differs')
    approach=next(r for r in root.findall('road') if r.attrib['id']=='1')
    lanes=approach.find('lanes/laneSection')
    left={l.attrib['id'] for l in lanes.find('left').findall('lane')}
    right={l.attrib['id'] for l in lanes.find('right').findall('lane')}
    if one_way and (left or right!={'-1','-2'}):
        raise ValueError('Authored one-way highway lanes differ')
    if not one_way and (left!={'1'} or right!={'-1'}):
        raise ValueError('Authored two-way highway lanes differ')
    if packet.get('legal_verdict') is not None or packet.get('physical_observation_claimed') is not False:
        raise ValueError('Statutory context claims unreviewed outcome')
    return {'case_suffix':case,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'road_geometry_sha256':hashlib.sha256(road_geometry.read_bytes()).hexdigest(),
        'authored_road_sha256':hashlib.sha256(Path(authored_road).read_bytes()).hexdigest(),
        'zone_kind':zone,'one_way':one_way,'railroad_crossing':rail,
        'original_frames':len(original_frames),'physical_observation_claimed':False,
        'applicability':'requires_independent_review','legal_verdict':None}
