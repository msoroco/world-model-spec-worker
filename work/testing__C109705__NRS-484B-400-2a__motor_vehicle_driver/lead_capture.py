import pathlib,json,copy
R=pathlib.Path.cwd();ids=json.loads((R/'partitions/demo-test-01.json').read_text())['assignment_ids']
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
finalizer='''"""Validate original retained capture. Unknown observations are explicit failures."""
import json,pathlib,argparse,hashlib

def rows(p):
 with p.open() as f:return [json.loads(line) for line in f if line.strip()]

def validate(root,recording):
 root=pathlib.Path(root);issues=[];hashes={}
 def read(name):
  path=root/name
  if not path.is_file():issues.append('missing '+name);return []
  hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest();return rows(path)
 trace=read('trace.jsonl');frames=read('video_frame_map.jsonl')
 if not trace:issues.append('empty original trace')
 if len(trace)!=len(frames):issues.append('trace/video frame count mismatch')
 for i,(t,f) in enumerate(zip(trace,frames)):
  if f.get('video_frame')!=i or f.get('carla_frame')!=t.get('frame') or f.get('time_s')!=t.get('time_s'):issues.append('frame join mismatch at '+str(i))
  if i and t['time_s']<=trace[i-1]['time_s']:issues.append('nonmonotonic original time')
 for c in recording['channels']:
  channel=read('channels/'+c['name']+'.jsonl')
  if len(channel)!=len(trace):issues.append('channel count '+c['name'])
  if any(v.get('value') is None for v in channel):issues.append('unavailable mandatory evidence '+c['name'])
  for t,v in zip(trace,channel):
   if v.get('time_s')!=t.get('time_s'):issues.append('channel time join '+c['name']);break
  rate=c['sampling_rate_hz']
  if any(abs((b['time_s']-a['time_s'])-1/rate)>.0001 for a,b in zip(channel,channel[1:])):issues.append('channel rate '+c['name'])
 for name in ('road.xodr','carla_recorder.log','capture/manifest.json','capture/evidence.jsonl'):
  if not (root/name).is_file():issues.append('missing '+name)
 return dict(passed=not issues,issues=issues,source_sha256=hashes,legal_verdict=None)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('output_dir');p.add_argument('--config',default=str(pathlib.Path(__file__).with_name('config.json')));a=p.parse_args();r=validate(a.output_dir,json.loads(pathlib.Path(a.config).read_text())['recording_description']);print(json.dumps(r,indent=2));raise SystemExit(0 if r['passed'] else 2)
'''
for aid in ids:
 w=R/'work'/aid;run=(w/'runner.py').read_text();(w/'finalize.py').write_text(finalizer)
 run=run.replace('streams=[];samples=[];others=[];halt_start=None;collisions=[]','streams=[];samples=[];others=[];halt_start=None;collisions=[];channel_streams={}')
 run=run.replace("physical=(out/'physical_samples.jsonl').open('x');streams.append(physical)","""physical=(out/'physical_samples.jsonl').open('x');streams.append(physical)
        (out/'channels').mkdir()
        for channel in case['recording_description']['channels']:
            stream=(out/'channels'/(channel['name']+'.jsonl')).open('x');channel_streams[channel['name']]=stream;streams.append(stream)
        (out/'context.json').write_text(json.dumps({'authored_context':case['variable_assignments']['authored_context']['value']}))""")
 run=run.replace("sample['time_s']=time_s;samples.append(sample);physical.write(json.dumps(sample)+'\\n')","""sample['time_s']=time_s;samples.append(sample);physical.write(json.dumps(sample)+'\\n')
            direct={'kin.position':sample['position_m'],'kin.heading':sample['heading_deg'],'kin.speed':sample['speed_mps'],'rel.surface_gap':sample['gap_m']}
            for name,stream in channel_streams.items():stream.write(json.dumps(dict(time_s=time_s,value=direct.get(name),missing_capability=None if name in direct else 'native atom projection not yet implemented; raw original evidence retained'))+'\\n')""")
 run=run.replace("result['recording_evidence']=[dict(name='kin.speed',unit='m/s',reference='kin.speed.jsonl')]","result['recording_evidence']=[dict(name=x['name'],unit=x['unit'],reference='channels/'+x['name']+'.jsonl') for x in case['recording_description']['channels']]")
 run=run.replace('if cap is not None:cap.close(confirmed=False)',"""if cap is not None:
            try:cap.close(confirmed=False)
            except Exception as cleanup_error:result['physical_failure_flags'].append('capture_cleanup: '+str(cleanup_error))""")
 (w/'runner.py').write_text(run)
 t='''import unittest,tempfile,pathlib,importlib.util,json
P=pathlib.Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('capture_validator',P/'finalize.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class CaptureTests(unittest.TestCase):
 def test_missing_capture_fails(self):
  with tempfile.TemporaryDirectory() as d:self.assertFalse(m.validate(d,{'channels':[]})['passed'])
 def test_null_mandatory_data_fails(self):
  with tempfile.TemporaryDirectory() as d:
   r=pathlib.Path(d);(r/'channels').mkdir();(r/'trace.jsonl').write_text(json.dumps({'frame':5,'time_s':1})+'\\n');(r/'video_frame_map.jsonl').write_text(json.dumps({'video_frame':0,'carla_frame':5,'time_s':1})+'\\n');(r/'channels/a.jsonl').write_text(json.dumps({'time_s':1,'value':None})+'\\n');v=m.validate(r,{'channels':[{'name':'a','sampling_rate_hz':20}]});self.assertIn('unavailable mandatory evidence a',v['issues'])
 def test_frame_mismatch_fails(self):
  with tempfile.TemporaryDirectory() as d:
   r=pathlib.Path(d);(r/'trace.jsonl').write_text(json.dumps({'frame':5,'time_s':1})+'\\n');(r/'video_frame_map.jsonl').write_text(json.dumps({'video_frame':0,'carla_frame':6,'time_s':1})+'\\n');self.assertIn('frame join mismatch at 0',m.validate(r,{'channels':[]})['issues'])
''';(w/'tests/test_capture.py').write_text(t)
 con=json.loads((w/'construction.json').read_text());con['files']=[dict(path=p,content=(w/p).read_text()) for p in ['runner.py','scenario.py','finalize.py','config.json','road-template.xodr']];dump(w/'construction.json',con)
 c=json.loads((w/'config.json').read_text());cases=json.loads((w/'proposals/cases.json').read_text())['cases']
 for case in cases[2:]:
  cc=copy.deepcopy(con);cc['case_id']=case['case_id'];cfg=copy.deepcopy(c);cfg['default_case_id']=case['case_id'];next(f for f in cc['files'] if f['path']=='config.json')['content']=json.dumps(cfg,indent=2)+'\n';dump(w/'constructions'/(case['case_id']+'.json'),cc)
 (w/'HANDOFF.md').write_text((w/'HANDOFF.md').read_text()+'\nExecutable measured-data validation: `python3.11 finalize.py OUTPUT_DIR` verifies original trace/camera joins, mandatory raw-channel completeness, sampling rates and capture artifacts, returning 2 for missing evidence. Runner now retains every requested channel with explicit null/missing capability where no truthful atom projection exists. These diagnostic streams never count as complete observations.\n')
