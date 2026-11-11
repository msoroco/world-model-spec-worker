"""Exercise complete-loop validation with source hashes rebound after mutations."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import xml.etree.ElementTree as ET

import check

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent/'offline/bundles/reference/primary'
FILES=('assignment-source.json','case-plan.json','config.json',
       'right-exit-road.xodr','requested-tracks.jsonl','controller-intention.json')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def mutate(kind,root):
    road_path=root/'right-exit-road.xodr'
    document=ET.parse(road_path)
    node=document.getroot()
    if kind=='missing_loop':
        target=next(x for x in node.findall('road') if x.attrib['id']=='23')
        node.remove(target)
    elif kind=='broken_arc':
        target=next(x for x in node.findall('road') if x.attrib['id']=='23')
        target.find('./planView/geometry').attrib['length']='50'
    elif kind=='bad_junction_lane':
        junction=next(x for x in node.findall('junction') if x.attrib['id']=='100')
        junction.find('./connection/laneLink').attrib['to']='-3'
    else:raise ValueError(kind)
    document.write(road_path,encoding='unicode')
    config_path=root/'config.json';cfg=json.loads(config_path.read_text())
    cfg['road_sha256']=sha(road_path)
    config_path.write_text(json.dumps(cfg,indent=2)+'\n')

if check.check(SOURCE)['complete_circle_xml_geometry_authored'] is not True:
    raise ValueError('Complete-loop positive failed')
negative={}
with tempfile.TemporaryDirectory(prefix='c132497-topology-') as temporary:
    for kind in ('missing_loop','broken_arc','bad_junction_lane'):
        root=Path(temporary)/kind;root.mkdir()
        for name in FILES:shutil.copyfile(SOURCE/name,root/name)
        mutate(kind,root)
        try:check.check(root)
        except ValueError as error:
            if 'source hash' in str(error):
                raise ValueError('Topology negative rejected only by source hash') from error
            negative[kind]=str(error)
        else:raise ValueError('Changed roundabout topology accepted: '+kind)

print(json.dumps({'passed':True,'closed_loop_positive':1,
                  'rebound_source_negatives':negative,'original_native_observed':False}))
