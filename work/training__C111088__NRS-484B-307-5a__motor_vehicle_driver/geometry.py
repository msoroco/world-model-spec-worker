"""C111088 authored sole-arrow/other-vehicle conflict geometry; CPU proposal."""
from __future__ import annotations
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
INTERSECTION=(-7.,-7.,7.,7.)
CROSSWALK=(-3.5,-12.,3.5,-10.)
STOP_LINE_Y=-14.
EGO_STOP_CENTER_Y=-17.
ARROW_FRAME=100
OTHER_CLEAR_FRAME=169
def road_xml():return (HERE/'road.xodr').read_text()
def ego_y(frame,other_present):
    if frame<ARROW_FRAME:return -25+8*frame/ARROW_FRAME
    if other_present and frame<OTHER_CLEAR_FRAME:return EGO_STOP_CENTER_Y
    start=OTHER_CLEAR_FRAME if other_present else ARROW_FRAME
    return min(20.,EGO_STOP_CENTER_Y+37*(frame-start)/200)
def other_x(frame):
    return -24+.2*frame
def body(x,y,heading):
    if heading=='north':return [[x-1.1,y-2.6],[x+1.1,y-2.6],[x+1.1,y+2.6],[x-1.1,y+2.6]]
    if heading=='east':return [[x-2.6,y-1.1],[x+2.6,y-1.1],[x+2.6,y+1.1],[x-2.6,y+1.1]]
    raise ValueError('Unknown straight heading')
def overlap(vertices,region):
    xs=[v[0] for v in vertices];ys=[v[1] for v in vertices]
    return max(0,min(max(xs),region[2])-max(min(xs),region[0]))*max(0,min(max(ys),region[3])-max(min(ys),region[1]))
def check():
    root=ET.fromstring(road_xml())
    if len(root.findall('junction/connection'))!=2 or len(root.findall(".//object[@type='crosswalk']"))!=1 or len(root.findall('.//signal'))!=2:
        raise ValueError('Authored sole-arrow junction context differs')
    names={s.attrib['name'] for s in root.findall('.//signal')}
    if names!={'south-sole-green-straight-arrow-proposal','west-prior-green-then-red-proposal'}:
        raise ValueError('Authored signal proposals differ')
    if overlap(body(1.75,ego_y(100,False),'north'),CROSSWALK):
        raise ValueError('Ego stop-line body touches crosswalk')
    if not overlap(body(other_x(100),-1.75,'east'),INTERSECTION):
        raise ValueError('Prior-entered other vehicle not in conflict at arrow onset')
    if overlap(body(other_x(OTHER_CLEAR_FRAME),-1.75,'east'),INTERSECTION):
        raise ValueError('Other vehicle not clear at release frame')
    if ego_y(120,True)!=EGO_STOP_CENTER_Y or ego_y(120,False)<=EGO_STOP_CENTER_Y:
        raise ValueError('Controlled yield timing differs')
    return {'passed':True,'cell_id':'C111088','law_id':'NRS-484B-307-5a',
            'scope':'authored signal/route proposal and synthetic timing only; no Native aspect or lawfulness observed',
            'arrow_frame':ARROW_FRAME,'other_vehicle_prior_entry_frame':72,
            'other_vehicle_clear_frame':OTHER_CLEAR_FRAME,
            'comparison_variable':'lawful_conflict_participant_present',
            'native_or_legal_outcome_claimed':False}
if __name__=='__main__':print(json.dumps(check(),indent=2))
