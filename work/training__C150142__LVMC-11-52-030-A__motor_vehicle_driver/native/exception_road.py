"""Add source-readable sign and mail-drop geometry to the red-curb road.

The Native run must still confirm that CARLA renders these OpenDRIVE objects in
all required source cameras. XML presence alone is only a CPU construction test.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

BASE=Path(__file__).resolve().parent/'red-curb-road.xodr'


def construct(case):
    if case.get('paint')!='red' or case.get('target_x_m')!=40:
        raise ValueError('Exception target differs from constructed red curb')
    root=ET.fromstring(BASE.read_text())
    road=root.find('road')
    if road is None or road.get('id')!='150142':
        raise ValueError('Original road identity changed')
    signs=case.get('sign_classes')
    if not isinstance(signs,list) or any(not isinstance(s,str) or not s for s in signs):
        raise ValueError('Invalid authored sign classes')
    if signs:
        container=ET.SubElement(road,'signals')
        sign=ET.SubElement(container,'signal',{
            'id':'15014201','name':'RED CURB - '+', '.join(signs),
            's':'40','t':'-7.5','zOffset':'2.0','hOffset':'0',
            'orientation':'+','dynamic':'no','country':'US',
            'type':'parking','subtype':'red_curb_exception',
            'value':'0','unit':'none','height':'0.8','width':'1.2'})
        ET.SubElement(sign,'userData',{'code':'displayed_classes',
                                      'value':','.join(signs)})
    if case.get('mailbox_requested'):
        objects=ET.SubElement(road,'objects')
        box=ET.SubElement(objects,'object',{
            'id':'15014202','name':'US_MAIL_DROP_BOX','type':'postbox',
            's':'40','t':'-7.4','zOffset':'0','hdg':'0',
            'length':'0.5','width':'0.4','height':'1.5',
            'orientation':'+'})
        ET.SubElement(box,'userData',{'code':'mail_service','value':'U.S. mail'})
    return '<?xml version="1.0" standalone="yes"?>\n'+ET.tostring(
        root,encoding='unicode')+'\n'


def readback(xml):
    root=ET.fromstring(xml)
    road=root.find('road')
    if road is None or road.get('id')!='150142':
        raise ValueError('Native road ID differs')
    marks=road.findall('.//laneSection/right/lane[@id="-2"]/roadMark')
    if [(float(m.get('sOffset')),m.get('color')) for m in marks]!=[
            (0.,'white'),(30.,'red'),(50.,'white')]:
        raise ValueError('Native red paint missing')
    signs=road.findall('./signals/signal')
    boxes=road.findall('./objects/object[@name="US_MAIL_DROP_BOX"]')
    if len(signs)>1 or len(boxes)>1:
        raise ValueError('Ambiguous red-curb sign or mailbox')
    classes=[]
    if signs:
        data=signs[0].find('./userData[@code="displayed_classes"]')
        if data is None or signs[0].get('s')!='40' or signs[0].get('t')!='-7.5':
            raise ValueError('Sign geometry or text readback missing')
        classes=data.get('value','').split(',')
    if boxes and (boxes[0].get('s')!='40' or boxes[0].get('t')!='-7.4'):
        raise ValueError('Mail-drop geometry changed')
    return {'red_curb':{'paint_color':'red','start_x_m':30,'end_x_m':50,
                        'curb_y_m':-7},
            'sign_readback':{'present':bool(signs),'displayed_classes':classes},
            'mailbox_readback':{'present':bool(boxes),'center_x_m':40,
                                'center_y_m':-7.4}}
