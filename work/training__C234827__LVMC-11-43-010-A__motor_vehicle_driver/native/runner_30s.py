"""Source-bound Native dispatch for one exact rotary-island delivery case."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(bundle):
    bundle=Path(bundle)
    config=json.loads((bundle/'config.json').read_text())
    assignment=json.loads((bundle/'assignment-source.json').read_text())
    if (config.get('format')!='c234827-rotary-delivery-v2' or
            config.get('selected_case_id')!=config.get('case_id') or
            config.get('case_id') not in (assignment['assignment_id']+'__witness_1',
                                          assignment['assignment_id']+'__witness_2') or
            (config.get('law_id'),config.get('cell_id'),config.get('actor'))!=
            ('LVMC-11-43-010-A','C234827','motor_vehicle_driver') or
            (config.get('rate_hz'),config.get('duration_s'))!=(20,30)):
        raise ValueError('Exact 30-second roundabout identity/duration differs')
    for key,name in (('assignment_sha256','assignment-source.json'),
                     ('road_sha256','road.xodr'),('island_geometry_sha256','island-geometry.json'),
                     ('tracks_sha256','requested-tracks.jsonl')):
        if config.get(key)!=sha(bundle/name):raise ValueError('Changed rotary source: '+name)
    road=ET.parse(bundle/'road.xodr').getroot()
    roads=road.findall('./road')
    if [int(item.attrib['id']) for item in roads]!=[1,2,3,4]:
        raise ValueError('Four connected rotary quarters absent')
    for index,item in enumerate(roads):
        lanes={int(x.attrib['id']):x.attrib['type'] for x in item.findall('.//lane')}
        previous=(index-1)%4+1;following=(index+1)%4+1
        predecessor=item.find('./link/predecessor');successor=item.find('./link/successor')
        if (lanes!={0:'none',-1:'driving',-2:'driving'} or
                item.find('./planView/geometry/arc') is None or
                predecessor is None or successor is None or
                predecessor.attrib.get('elementId')!=str(previous) or
                successor.attrib.get('elementId')!=str(following)):
            raise ValueError('Authored connected rotary geometry differs')
    rows=[json.loads(x) for x in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    if len(rows)!=600:raise ValueError('Continuous rotary request needs 600 frames')
    speed=config.get('requested_speed_mps')
    radius=config.get('requested_radius_m')
    if speed not in (8.0,6.0) or radius!=23.75:
        raise ValueError('Unsupported rotary controller/radius candidate')
    sign=config['requested_rotation_sign']
    if sign not in (-1,1) or sign!=(1 if config['case_id'].endswith('__witness_1') else -1):
        raise ValueError('Witness rotation sign differs')
    previous=None
    for i,row in enumerate(rows):
        expected=-math.pi/2+sign*speed*(i+1)/20/radius
        if (row['case_id']!=config['case_id'] or row['frame']!=i or
                abs(row['time_s']-(i+1)/20)>1e-6 or
                row['requested_rotation_sign']!=sign or
                row['ego_speed_mps']!=speed or row['requested_radius_m']!=radius or
                abs(row['ego_x_m']-radius*math.cos(expected))>1e-5 or
                abs(row['ego_y_m']-radius*math.sin(expected))>1e-5):
            raise ValueError('Requested rotary motion changed')
        angle=row['requested_unwrapped_angle_rad']
        if previous is not None and (angle-previous)*sign<=0:
            raise ValueError('Continuous rotation request interrupted')
        previous=angle
    return {'case_id':config['case_id'],'requested_frames':600,
            'source_bound':True,'native_executed':False,'physical_acceptance_claimed':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true')
    p.add_argument('--bundle',type=Path,default=Path.cwd())
    p.add_argument('--output-dir',type=Path);p.add_argument('--host');p.add_argument('--port',type=int)
    a=p.parse_args();checked=check(a.bundle)
    if a.check:print(json.dumps(checked));return
    if not a.output_dir or not a.host or not a.port:p.error('Native output, host and port required')
    from capture_30s import execute
    execute(a.bundle,a.output_dir,a.host,a.port,checked)


if __name__=='__main__':main()
