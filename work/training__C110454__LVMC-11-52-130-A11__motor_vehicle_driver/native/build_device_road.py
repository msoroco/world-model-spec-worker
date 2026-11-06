"""Create the exception-only authored official-device proposal road."""
from pathlib import Path
from xml.etree import ElementTree as ET

HERE=Path(__file__).resolve().parent
BASE=HERE/'road.xodr'
OUTPUT=HERE/'road_exception_device.xodr'
DEVICE_ID='620'

def build():
    root=ET.fromstring(BASE.read_text())
    road=next(r for r in root.findall('road') if r.attrib['id']=='2')
    signals=road.find('signals')
    if signals is None:raise ValueError('Destination road signals container absent')
    ET.SubElement(signals,'signal',{
        'id':DEVICE_ID,'name':'C110454_exception_stop_control_proposal',
        's':'1.0','t':'-6.2','zOffset':'0.0','hOffset':'0.0','pitch':'0.0','roll':'0.0',
        'dynamic':'no','orientation':'+','country':'US','type':'206','subtype':'0',
        'value':'0','height':'0.75','width':'0.75'})
    data=ET.tostring(root,encoding='unicode')+'\n'
    OUTPUT.write_text(data)
    return OUTPUT

if __name__=='__main__':
    print(build())
