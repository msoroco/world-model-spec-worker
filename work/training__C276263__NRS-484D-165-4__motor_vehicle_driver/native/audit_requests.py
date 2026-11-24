"""Independent source and fixed-condition audit of parked lamp proposals."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from parked_lamps import measure

BASE=Path(__file__).resolve().parents[1]
SOURCE=Path(__file__).resolve().parent
PREFIX=BASE.name

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def audit():
 road=SOURCE/'sloped-curb-road.xodr'
 node=ET.parse(road).getroot().find('road')
 grade=float(node.find('./elevationProfile/elevation').get('b'))
 if grade!=.04 or node.get('length')!='120':
  raise ValueError('Authored grade/road extent differs')
 lanes={(x.get('id'),x.get('type')) for x in node.findall('./lanes/laneSection/right/lane')}
 if {('-1','driving'),('-2','parking'),('-3','sidewalk')}-lanes:
  raise ValueError('Parking lane or curb-side context absent')
 proof={};fixed=[]
 for suffix,state in (('probe_a','low_beam'),('probe_b','high_beam')):
  path=BASE/'draft-native'/suffix/'construction.json'
  c=json.loads(path.read_text());files={x['path']:x['content'] for x in c['files']}
  cfg=json.loads(files['config.json'])
  if (c['case_id']!=PREFIX+'__'+suffix or cfg['road_sha256']!=sha(road)
      or files['sloped-curb-road.xodr']!=road.read_text()
      or cfg['requested_beam_state']!=state):
   raise ValueError('Construction/source binding differs')
  rows=[json.loads(x) for x in files['requested-track.jsonl'].splitlines()]
  m=measure(rows,'authored_native_request')
  if (m['requested_beam_state']!=state or m['frames']!=600
      or m['beam_depressed_or_dimmed_observed'] is not False):
   raise ValueError('Beam request evidence differs')
  conditions=[(r['ego_center_xyz_m'],r['ego_speed_mps'],r['requested_headlamp_lit'],
               r['requested_parking_lane_id']) for r in rows]
  fixed.append(conditions)
  proof[suffix]={'construction_sha256':sha(path),'requested_beam_state':state,
                 'frame_count':m['frames']}
 if fixed[0]!=fixed[1]:raise ValueError('Parking/vehicle conditions differ')
 return {'format':'c276263-parked-lamp-request-comparison-v1',
         'road_sha256':sha(road),'road_grade':grade,'probes':proof,
         'fixed_conditions':['same sloped road and curb lane',
                             'same parked pose and 600-frame zero-speed request',
                             'same four cameras and lighted-headlamp request'],
         'deliberate_difference':'requested low versus high headlamp beam state',
         'beam_aim_and_intensity_observed':False,
         'actual_parking_observed':False,'original_native_observed':False,
         'legal_verdict':None}

if __name__=='__main__':print(json.dumps(audit(),indent=2))
