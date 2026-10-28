"""Offline-verifiable physical assignment runner; CARLA imports stay lazy."""
import argparse,ast,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def speed_control(target,actual):
 error=target-actual
 return min(.75,max(0.,error*.3)), min(1.,max(0.,-error*.3))

def steering(position,yaw,target):
 desired=math.atan2(target[1]-position[1],target[0]-position[0]);error=(desired-yaw+math.pi)%(2*math.pi)-math.pi
 return max(-.7,min(.7,error*1.2))

def footprint_gap(a,b):return math.hypot(a[0]-b[0],a[1]-b[1])

def check():
 cfg=json.loads((ROOT/'config.json').read_text())
 assert cfg['actor']=='motor_vehicle_driver';assert cfg['supported_case_ids'];assert cfg['selected_case_id'] in cfg['supported_case_ids']
 for f in ROOT.rglob('*.py'):ast.parse(f.read_text())
 from execution import project,materialize_sweep
 from contracts import validate_output
 from recording import Recording,Resources
 import xml.etree.ElementTree as ET
 from geometry import build_road,route
 assert ET.fromstring(build_road()).findall('road');assert len(route(cfg['maneuver']))>10
 for case in cfg['cases']:
  assert case['case_id'] in cfg['supported_case_ids'];assert case['variable_assignments']['ego_speed']['value'] is None
 assert len(cfg['cameras'])==4
 assert all(isinstance(c['location'],list) and len(c['location'])==3 for c in cfg['cameras'])
 print(json.dumps({'offline_checks':'passed','simulation_started':False,'output_contract':'strict measured original capture + real encoded four-camera videos','externally_blocked_requirements':cfg['externally_blocked_requirements']}))

def main():
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--output-dir');p.add_argument('--host');p.add_argument('--port',type=int);p.add_argument('--case-id');p.add_argument('--sweep-index',type=int);args=p.parse_args()
 if args.check:check();return 0
 if not all((args.output_dir,args.host,args.port)):p.error('Require --output-dir PATH --host HOST --port PORT')
 from execution import execute,materialize_sweep
 cfg=json.loads((ROOT/'config.json').read_text())
 if args.case_id:cfg['selected_case_id']=args.case_id
 case=materialize_sweep(cfg,args.sweep_index)
 if case['target_type']=='baseline':p.error('Baseline is a neutral definition, never selected; supply a case construction, --case-id ID, or frozen --sweep-index 0..4')
 return execute(args,cfg,case,ROOT)
if __name__=='__main__':raise SystemExit(main())
