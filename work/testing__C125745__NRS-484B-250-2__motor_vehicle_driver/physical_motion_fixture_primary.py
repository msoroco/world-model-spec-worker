"""Source-bound CPU classifier and lifecycle fixtures; no physical acceptance."""
import argparse
import base64
import copy
import hashlib
import json
import sys
import tempfile
import shutil
import zlib
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
sys.path.insert(0,str(REPO/'runtime/scenario_pipeline'))
from worker_exchange.common import sha
from worker_exchange.native_output import physical_result,seal_capture
from worker_exchange.saved_processing import record_native_exit,acknowledge_owner_release

DIAGNOSTICS={
 'stop_ego_left_near_time':'diagnostic.json',
 'stop_ego_right_near_time':'second-diagnostic.json',
 'stop_ego_left_separated':'third-diagnostic.json',
 'stop_opposite_left_turn':'fourth-diagnostic.json'}

def read(path):return json.loads(Path(path).read_text())
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

def construction_bytes(item):
 if 'construction_zlib_base64' in item:
  payload=zlib.decompress(base64.b64decode(item['construction_zlib_base64'],validate=True))
  if len(payload)!=item['construction_bytes']:raise ValueError('Construction length changed')
  return payload
 return item['construction_payload'].encode()

def proof_text(item,field):
 key=field+'_payload'
 if key in item:return item[key]
 raw=zlib.decompress(base64.b64decode(item[field+'_zlib_base64'],validate=True))
 if len(raw)!=item[field+'_bytes']:raise ValueError('Proof length changed')
 return raw.decode()

def run(kind,case,output):
 manifest=read(HERE/'execution-manifest.json')
 entry=next(e for e in manifest['cases'] if e['case_id']==case)
 construction_path=HERE/entry['construction']
 if sha(construction_path)!=entry['construction_sha256']:raise ValueError('Exact primary construction changed')
 construction=read(construction_path)
 config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
 if config['selected_case_id']!=case:raise ValueError('Exact case config differs')
 suffix=case.split('__')[-1]
 source_path=HERE/DIAGNOSTICS[suffix]
 sources=read(source_path)['files']
 criterion=config['physical_completion']
 if (criterion['criterion']!='intersection_clearance' or
     criterion['motion_source']!='crossing_history.jsonl' or
     criterion['body_key']!='ego.body_vertices_xy_m' or
     criterion['intersection_polygon_xy_m']!=json.loads(sources['junction_context.json'])['intersection_polygon_xy_m']):
    raise ValueError('Bundled physical completion criterion differs')
 with tempfile.TemporaryDirectory(prefix='c125745-motion-') as tmp:
  attempt=Path(tmp)
  write(attempt/'config.json',config)
  for name in ('trace.jsonl','video_frames.jsonl','crossing_history.jsonl'):
   (attempt/name).write_text(sources[name])
  write(attempt/'acquisition-provenance.json',{'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,
      'scope':'Synthetic CPU classifier fixture; no Native physical acceptance'})
  if kind=='lifecycle':
   claims=read(HERE/'result.json')['tests']
   saved=[]
   for claim in claims:
    command=claim.get('command','');log=claim.get('log','')
    if ('runtime.py process-saved' in command and '--case '+case+' ' in command and
        ('-primary-' in log or log.startswith('primary-')) and claim.get('exit_code')==0):
     path=HERE/log
     if path.is_file() and sha(path)==claim.get('sha256'):
      data=read(path)
      if data.get('passed') is True and data.get('recorded_only') is True:
       saved.append((path,data))
   if not saved:raise ValueError('Current exact primary saved-processing claim missing')
   saved_path,saved_data=saved[-1]
   write(attempt/'construction.json',construction)
   (attempt/'runner.py').write_text(next(f['content'] for f in construction['files'] if f['path']=='runner.py'))
   try:
    seal_capture(attempt,frames=60,restoration={'restored':True},errors=[],
        encoder_exit_codes={'fixture_encoder':1},context={'diagnostic_fixture':True})
   except ValueError as error:
    if 'unclosed/failed encoders' not in str(error):raise
   else:raise AssertionError('Failed encoder was sealed')
   sealed=seal_capture(attempt,frames=60,restoration={'restored':True},errors=[],
      encoder_exit_codes={'fixture_encoder':0},context={'diagnostic_fixture':True})
   try:acknowledge_owner_release(attempt,attempt/'owner-release.json',True)
   except ValueError as error:
    if 'Native process has not exited' not in str(error):raise
   else:raise AssertionError('Premature owner release passed')
   native=record_native_exit(attempt)
   owner=acknowledge_owner_release(attempt,attempt/'owner-release.json',True)
   events=sealed['events']+[native['event'],owner['event'],saved_data['events'][0]]
   expected=['capture_finished','encoders_closed','restoration_verified','native_exit',
             'owner_released','saved_processing_started']
   if events!=expected:raise AssertionError('Saved processing lifecycle order differs')
   result={'case_id':case,'events':events,'diagnostic_fixture':True,
       'failed_encoder_rejected':True,'premature_release_rejected':True,
       'saved_processing_log_sha256':sha(saved_path)}
   write(output,result);return result
  motion=attempt/'crossing_history.jsonl'
  if kind=='missing_evidence':motion.unlink()
  else:
   rows=[json.loads(line) for line in motion.read_text().splitlines()]
   first=copy.deepcopy(rows[0]['ego']['body_vertices_xy_m'])
   for i,row in enumerate(rows):
    offset=29*i/(len(rows)-1) if kind=='complete_motion' else 0
    row['ego']['body_vertices_xy_m']=[[x+offset,y] for x,y in first]
   motion.write_text(''.join(json.dumps(row)+'\n' for row in rows))
  result=physical_result(attempt,{'target_checks':[]})
  expected={'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}[kind]
  check=result['physical_checks']['maneuver']
  if (check['status']!=expected or result['maneuver_completed']!=(expected=='met') or
      not check['method'] or not check['sources'] or result['physical_acceptance_claimed'] is not False):
   raise AssertionError('Physical classifier fixture differs: '+kind)
  write(output,result)
  return {'case_id':case,'fixture':kind,'maneuver_status':expected,'diagnostic_fixture':True,
      'source_hashes':check['sources']}

def run_staged(kind,case,attempt,output,candidate=None,canonical_saved_receipt=None):
 """Exercise a staged sweep's source-bound CPU classifier; no Native claim."""
 index=read(HERE/'sweep-constructions/index.json')
 point=next(x for x in index['constructions']
            if x['case_id']==case or x.get('qualified_primary',{}).get('case_id')==case)
 qualified=point.get('qualified_primary',{})
 exact=qualified if qualified.get('case_id')==case else point
 if candidate:
  if exact is not qualified:raise ValueError('Qualified fallback requires qualified case')
  fallback=next(x for x in point['qualified_fallbacks']['candidates'] if x['id']==candidate)
  payload=construction_bytes(fallback)
  expected_hash=fallback['construction_sha256']
  if hashlib.sha256(payload).hexdigest()!=expected_hash:raise ValueError('Fallback construction changed')
  construction=json.loads(payload)
 else:
  expected_hash=exact.get('construction_sha256',exact.get('sha256'))
  if 'construction_payload' in exact or 'construction_zlib_base64' in exact:
   payload=construction_bytes(exact)
   if hashlib.sha256(payload).hexdigest()!=expected_hash:raise ValueError('Staged construction changed')
   construction=json.loads(payload)
  else:
   construction_path=HERE/exact['construction']
   if sha(construction_path)!=expected_hash:raise ValueError('Staged construction changed')
   construction=read(construction_path)
 if construction['case_id']!=case:raise ValueError('Staged case mismatch')
 embedded=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
 config=read(attempt/'config.json')
 if config!=embedded:raise ValueError('Attempt config differs from construction')
 receipt=read(attempt/'compatibility.json')
 if receipt.get('passed') is not True or receipt.get('case_id')!=case or receipt.get('construction_sha256')!=expected_hash:
  raise ValueError('Current exact compatibility receipt missing')
 if receipt.get('candidate_id')!=(candidate or 'primary'):raise ValueError('Compatibility candidate differs')
 with tempfile.TemporaryDirectory(prefix='c125745-staged-motion-') as tmp:
  fixture=Path(tmp)
  for name in ('config.json','trace.jsonl','video_frames.jsonl','crossing_history.jsonl','junction_context.json'):
   shutil.copyfile(attempt/name,fixture/name)
  write(fixture/'acquisition-provenance.json',{'provenance_kind':'native','diagnostic_fixture':True,
       'scope':'Staged synthetic CPU classifier fixture; no Native physical acceptance'})
  if kind=='lifecycle':
   if exact is not qualified:raise ValueError('Staged lifecycle requires qualified saved claim')
   saved=(fallback if candidate else qualified)['current_runtime_proof']['recorded_only_saved']
   payload=proof_text(saved,'receipt').encode()
   if hashlib.sha256(payload).hexdigest()!=saved['receipt_sha256']:
    raise ValueError('Qualified saved receipt changed')
   saved_sha=saved['receipt_sha256']
   if canonical_saved_receipt:
    manifest_entry=next(e for e in read(HERE/'execution-manifest.json')['cases'] if e['case_id']==case)
    manifest_candidate=next(c for c in manifest_entry['candidates'] if c['id']==candidate)
    bound=manifest_candidate['post_capture']
    if HERE/bound['test_log']!=canonical_saved_receipt.resolve():
     raise ValueError('Canonical saved receipt path differs from manifest')
    payload=canonical_saved_receipt.read_bytes()
    saved_sha=hashlib.sha256(payload).hexdigest()
    if saved_sha!=bound['test_log_sha256']:
     raise ValueError('Canonical saved receipt hash differs from manifest')
   saved_data=json.loads(payload)
   if (saved_data.get('passed') is not True or saved_data.get('recorded_only') is not True or
       saved_data.get('case_id')!=case or saved_data.get('candidate_id')!=(candidate or 'primary') or
       saved_data.get('native_revision',{}).get('construction_sha256')!=expected_hash):
    raise ValueError('Qualified saved claim differs')
   write(fixture/'construction.json',construction)
   (fixture/'runner.py').write_text(next(f['content'] for f in construction['files'] if f['path']=='runner.py'))
   frames=len((fixture/'video_frames.jsonl').read_text().splitlines())
   try:
    seal_capture(fixture,frames=frames,restoration={'restored':True},errors=[],
                 encoder_exit_codes={'fixture_encoder':1},context={'diagnostic_fixture':True})
   except ValueError as error:
    if 'unclosed/failed encoders' not in str(error):raise
   else:raise AssertionError('Failed encoder was sealed')
   sealed=seal_capture(fixture,frames=frames,restoration={'restored':True},errors=[],
                       encoder_exit_codes={'fixture_encoder':0},context={'diagnostic_fixture':True})
   try:acknowledge_owner_release(fixture,fixture/'owner-release.json',True)
   except ValueError as error:
    if 'Native process has not exited' not in str(error):raise
   else:raise AssertionError('Premature owner release passed')
   native=record_native_exit(fixture)
   owner=acknowledge_owner_release(fixture,fixture/'owner-release.json',True)
   events=sealed['events']+[native['event'],owner['event'],saved_data['events'][0]]
   expected=['capture_finished','encoders_closed','restoration_verified',
             'native_exit','owner_released','saved_processing_started']
   if events!=expected:raise AssertionError('Saved processing lifecycle order differs')
   result={'case_id':case,'candidate_id':candidate or 'primary','events':events,
           'diagnostic_fixture':True,'captured_frames':frames,
           'failed_encoder_rejected':True,'premature_release_rejected':True,
           'saved_processing_receipt_sha256':saved_sha}
   write(output,result)
   return result
  motion=fixture/'crossing_history.jsonl'
  if kind=='missing_evidence':motion.unlink()
  else:
   rows=[json.loads(line) for line in motion.read_text().splitlines()]
   first=copy.deepcopy(rows[0]['ego']['body_vertices_xy_m'])
   for i,row in enumerate(rows):
    offset=29*i/(len(rows)-1) if kind=='complete_motion' else 0
    row['ego']['body_vertices_xy_m']=[[x+offset,y] for x,y in first]
   motion.write_text(''.join(json.dumps(row)+'\n' for row in rows))
  result=physical_result(fixture,{'target_checks':[]})
  expected={'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}[kind]
  check=result['physical_checks']['maneuver']
  if check['status']!=expected or result['maneuver_completed']!=(expected=='met') or result['physical_acceptance_claimed'] is not False:
   raise AssertionError('Staged physical classifier differs: '+kind)
  write(output,result)
  return {'case_id':case,'fixture':kind,'maneuver_status':expected,'diagnostic_fixture':True,'source_hashes':check['sources']}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--kind',required=True,choices=('complete_motion','incomplete_motion','missing_evidence','lifecycle'))
 p.add_argument('--case',required=True);p.add_argument('--output',required=True,type=Path)
 p.add_argument('--staged-attempt',type=Path)
 p.add_argument('--candidate',choices=('fallback1','fallback2','fallback3'))
 p.add_argument('--canonical-saved-receipt',type=Path)
 a=p.parse_args();a.output.parent.mkdir(parents=True,exist_ok=True)
 print(json.dumps(run_staged(a.kind,a.case,a.staged_attempt,a.output,a.candidate,a.canonical_saved_receipt) if a.staged_attempt else run(a.kind,a.case,a.output),sort_keys=True))
