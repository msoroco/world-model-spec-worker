import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
root=Path('work/testing__C111260__NRS-484B-270-5a__motor_vehicle_driver');manifest_path=root/'execution-manifest.json';m=json.loads(manifest_path.read_text())
python=str(Path('.venv-cpu/bin/python').absolute());env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1';env['TMPDIR']=str(Path('.runtime-work/c111260-5a-tmp').resolve());env['SCENARIO_PIPELINE_OUTPUT_ROOT']=str(Path('.runtime-work/c111260-5a-output').resolve())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for e in m['cases']:
 suffix=e['case_id'].split('__')[-1];source=Path('.runtime-work/c111260-5a-compat')/suffix/'primary';items=[]
 for kind in ('complete_motion','incomplete_motion','missing_evidence'):
  output=Path('.runtime-work/c111260-5a-physical')/suffix/kind
  if output.exists():shutil.rmtree(output)
  output.mkdir(parents=True)
  for name in ('site.json','history.json','camera-frames.json','encounter-packet.json','acquisition-provenance.json','video_frames.jsonl','config.json','overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'):
   shutil.copy2(source/name,output/name)
  rows=json.loads((output/'history.json').read_text())
  if kind!='missing_evidence':
   for index,row in enumerate(rows):
    fraction=index/(len(rows)-1)
    row['ego_position_xy_m']=[-20+40*fraction if kind=='complete_motion' else -20+4*fraction,0]
    row['rider_position_xy_m']=[0,-20+40*fraction if kind=='complete_motion' else -20+4*fraction]
  (output/'history.json').write_text(json.dumps(rows,indent=2)+'\n')
  packet=json.loads((output/'encounter-packet.json').read_text());packet['history']['sha256']=sha(output/'history.json')
  (output/'encounter-packet.json').write_text(json.dumps(packet,indent=2)+'\n')
  cmd=[python,str(root/'analysis.py'),'--attempt',str(output),'--output',str(output/'analysis-report.json')]
  r=subprocess.run(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
  log=root/f'proof-physical-{suffix}-{kind}.log';log.write_text((r.stdout.rstrip() or f'analysis.py {kind} exit_code={r.returncode}')+'\n')
  if r.returncode:print('FAILED',suffix,kind,r.stdout[-2000:],flush=True);sys.exit(r.returncode)
  result=json.loads((output/'result.json').read_text());expected={'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}[kind]
  if result['physical_checks']['maneuver']['status']!=expected:print('WRONG STATUS',suffix,kind,result['physical_checks']['maneuver'],flush=True);sys.exit(1)
  target=root/f'proof-physical-{suffix}-{kind}-result.json';shutil.copy2(output/'result.json',target)
  items.append({'kind':kind,'command':' '.join(cmd),'exit_code':0,'log':log.name,'log_sha256':sha(log),'result':target.name,'result_sha256':sha(target)})
  print('PASS',suffix,kind,flush=True)
 lifecycle_root=Path('.runtime-work/c111260-5a-lifecycle')/suffix
 if lifecycle_root.exists():shutil.rmtree(lifecycle_root)
 lifecycle_root.mkdir(parents=True)
 construction=json.loads((root/e['construction']).read_text())
 for name in ('config.json','construction.json','runner.py'):
  if name=='construction.json':source_file=root/e['construction'];shutil.copy2(source_file,lifecycle_root/name)
  elif name=='runner.py':(lifecycle_root/name).write_text(next(f['content'] for f in construction['files'] if f['path']==name))
  else:(lifecycle_root/name).write_text(next(f['content'] for f in construction['files'] if f['path']==name))
 (lifecycle_root/'acquisition-provenance.json').write_text(json.dumps({'provenance_kind':'synthetic_fixture','diagnostic_fixture':True})+'\n')
 (lifecycle_root/'trace.jsonl').write_text(''.join(json.dumps({'frame':300+i,'time_s':i/20})+'\n' for i in range(900)))
 (lifecycle_root/'video_frames.jsonl').write_text(''.join(json.dumps({'video_frame':i,'carla_frame':300+i,'time_s':i/20})+'\n' for i in range(900)))
 from worker_exchange.native_output import seal_capture
 from worker_exchange.saved_processing import record_native_exit,acknowledge_owner_release,copy_sources
 lines=[]
 try:record_native_exit(lifecycle_root)
 except (FileNotFoundError,ValueError):lines.append('reject native exit before capture seal')
 else:raise ValueError('premature native exit accepted')
 seal_capture(lifecycle_root,frames=900,restoration={'restored':True,'settings_readback':'CPU protocol fixture'},errors=[],encoder_exit_codes={'diagnostic':0})
 try:acknowledge_owner_release(lifecycle_root,lifecycle_root/'owner-release.json',True)
 except (FileNotFoundError,ValueError):lines.append('reject owner release before native exit')
 else:raise ValueError('premature owner release accepted')
 record_native_exit(lifecycle_root)
 acknowledge_owner_release(lifecycle_root,lifecycle_root/'owner-release.json',True)
 stage=lifecycle_root.parent/(suffix+'-saved-stage')
 if stage.exists():shutil.rmtree(stage)
 stage.mkdir()
 copy_sources(lifecycle_root,stage)
 lines.append('capture_finished encoders_closed restoration_verified native_exit owner_released saved_processing_started')
 lifecycle_log=root/f'proof-physical-{suffix}-lifecycle.log';lifecycle_log.write_text('\n'.join(lines)+'\n')
 lifecycle={'events':['capture_finished','encoders_closed','restoration_verified','native_exit','owner_released','saved_processing_started'],'exit_code':0,'log':lifecycle_log.name,'log_sha256':sha(lifecycle_log)}
 receipt=root/f'physical-preparation-{suffix}.json';receipt.write_text(json.dumps({'case_id':e['case_id'],'construction_sha256':e['construction_sha256'],'fixtures':items,'lifecycle':lifecycle,'scope':'synthetic fixture and closure protocol only'},indent=2)+'\n')
 e['physical_preparation']={'receipt':receipt.name,'sha256':sha(receipt)}
manifest_path.write_text(json.dumps(m,indent=2,ensure_ascii=False)+'\n')
