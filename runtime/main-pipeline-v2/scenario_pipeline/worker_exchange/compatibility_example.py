"""Build a tiny executable example around retained diagnostic data, never delivery."""
from pathlib import Path
import json,shutil
from .common import read,write,sha,tree
from .native_output import frame_record

ANALYSIS='''import argparse,json
from pathlib import Path
from worker_exchange.native_output import write_result
p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True);a=p.parse_args();root=Path(a.attempt)
cfg=json.loads((root/'config.json').read_text());case=cfg['case']
rows=[json.loads(s) for s in (root/'trace.jsonl').read_text().splitlines()]
measured=rows[-1]['speed_mps'];requested=case['variable_assignments']['speed']['value']
(root/'speed.jsonl').write_text(''.join(json.dumps({'time_s':r['time_s'],'value':r['speed_mps']})+'\\n' for r in rows))
result={'case_id':case['case_id'],'measured_values':{'speed':measured},'target_checks':[{'target':'speed','requested':requested,'measured':measured,'method':'original last velocity sample','tolerance':0.1,'matched':abs(measured-requested)<=0.1,'physical_cause_confirmed':False,'cause_evidence':'trace.jsonl'}],'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,'termination_reason':'diagnostic subset only','physical_failure_flags':{'detection_validated':False},'trace_reference':'trace.jsonl','video_references':['raw.mkv'],'video_frame_map_reference':'video_frames.jsonl','recording_description':case['recording_description'],'recording_evidence':[{'name':'kin.speed','unit':'m/s','reference':'speed.jsonl'}],'realized_observables':{}}
write_result(root,result)
Path(a.output).write_text(json.dumps({'scope':'diagnostic fixture only','physical_acceptance':False}))
'''

def build(runtime,destination):
    runtime=Path(runtime).resolve();root=Path(destination).resolve();root.mkdir(parents=True,exist_ok=False)
    fixture=root/'fixtures/retained';shutil.copytree(runtime/'fixtures/retained-speed',fixture)
    # Explicit diagnostic adaptation of the supplied subset, never original evidence.
    for name in ('config.json','result.json','case.json'):(fixture/name).unlink()
    rows=[json.loads(s) for s in (fixture/'trace.jsonl').read_text().splitlines()]
    (fixture/'video_frames.jsonl').write_text(''.join(json.dumps(frame_record(i,r['frame'],r['time_s']))+'\n' for i,r in enumerate(rows)))
    provenance=read(fixture/'fixture-provenance.json');provenance['diagnostic_adaptations']=['canonical frame-map fixture written from retained source identities; config/result supplied by example package'];write(fixture/'fixture-provenance.json',provenance)
    case_id='diagnostic__output_contract__case'
    desc={'channels':[{'name':'kin.speed','unit':'m/s','sampling_rate_hz':20,'method':'native actor velocity','time_window':'entire original run','reference_frame':'CARLA world','uncertainty':'diagnostic retained 20Hz samples'}],'context_inputs':[],'limitations':['Three-frame software test only; incomplete motion and unknown physical cause.']}
    case={'case_id':case_id,'target_law_id':None,'target_type':'boundary_probe','variable_assignments':{'speed':{'value':5.0,'unit':'m/s','kind':'controller'}},'recording_description':desc}
    config={'case':case,'selected_case_id':case_id,'cell_id':'diagnostic','actor':'motor_vehicle_driver','required_atoms':['kin.speed']}
    files=[{'path':'config.json','content':json.dumps(config)},{'path':'analyze.py','content':ANALYSIS},{'path':'runner.py','content':'import argparse\np=argparse.ArgumentParser();p.add_argument("--check",action="store_true");a=p.parse_args();assert a.check\n'},{'path':'tests/test_output.py','content':'import unittest\nfrom worker_exchange.native_output import frame_record\nclass T(unittest.TestCase):\n def test_identity(self):self.assertEqual(frame_record(0,3,0)["carla_frame"],3)\n'}]
    bundle={'case_id':case_id,'cell_id':'diagnostic','actor':'motor_vehicle_driver','entrypoint':'runner.py','recording_description':desc,'files':files}
    write(root/'construction.json',bundle);write(root/'proposals/cases.json',{'cases':[case]})
    write(root/'execution-manifest.json',{'format':'worker-execution-manifest-v1','runtime_manifest_sha256':sha(runtime/'SOURCE-MANIFEST.json'),'cases':[{'case_id':case_id,'kind':'capability','construction':'construction.json','construction_sha256':sha(root/'construction.json'),'measurement_procedure':{'entrypoint':'analyze.py','output_schema':'diagnostic'}}]})
    return root/'execution-manifest.json',case_id,fixture

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--runtime',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(build(a.runtime,a.output))
