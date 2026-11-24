import json,pathlib,shlex,subprocess,sys
root=pathlib.Path.cwd();folder=root/'work/testing__C144550__NRS-484B-223-1b__motor_vehicle_driver';manifest=json.loads((folder/'execution-manifest.json').read_text());script=folder/'delivery_source_audit.py'
for entry in manifest['cases']:
 case=entry['case_id'];slug=case.split('__')[-1];tokens=shlex.split(entry['post_capture']['command']);source=(root/tokens[tokens.index('--attempt')+1]).resolve()
 positive=[str(root/'.venv-cpu/bin/python'),str(script),'--attempt',str(source),'--case',case]
 p=subprocess.run(positive,capture_output=True,text=True,cwd=root);(folder/(('first' if slug=='left_signal_before_clear_gap' else slug)+'-delivery-source-positive.log')).write_text(p.stdout+p.stderr)
 if p.returncode:raise RuntimeError(slug+' positive failed: '+p.stderr[-500:])
 target=(root/'.runtime-work'/('c144550-audit-negative-'+slug)).resolve();target.mkdir(parents=True,exist_ok=True)
 for name in ('config.json','result.json','analysis-report.json','compatibility.json','acquisition-provenance.json','four-view-receipt.json','lane_context.json','lane_history.jsonl','video_frames.jsonl','trace.jsonl','overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'):
  q=target/name
  if q.is_symlink():q.unlink()
  q.symlink_to(source/name)
 (target/'capture').mkdir(exist_ok=True)
 original=(source/'capture/evidence.jsonl').read_bytes();altered=original.replace(b'"actor_id":101',b'"actor_id":999',1)
 if altered==original:raise RuntimeError(slug+' mutation did not change original')
 (target/'capture/evidence.jsonl').write_bytes(altered)
 negative=[str(root/'.venv-cpu/bin/python'),str(script),'--attempt',str(target),'--case',case]
 n=subprocess.run(negative,capture_output=True,text=True,cwd=root);(folder/(('first' if slug=='left_signal_before_clear_gap' else slug)+'-delivery-source-negative.log')).write_text(n.stdout+n.stderr)
 if n.returncode==0 or 'Original source changed: capture/evidence.jsonl' not in n.stderr:raise RuntimeError(slug+' negative did not reject changed original: '+n.stderr[-500:])
 print(slug,'positive=pass','negative=expected-rejection',flush=True)
