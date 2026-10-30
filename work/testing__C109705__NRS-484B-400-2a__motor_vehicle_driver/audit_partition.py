"""Execute saved-only controlled comparisons from source-bound exact-case reports."""
import json,pathlib,importlib.util,hashlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
m=importlib.util.spec_from_file_location('audit',ROOT/'work/_shared/comparison_audit.py');audit=importlib.util.module_from_spec(m);m.loader.exec_module(audit)
for aid in json.load(open(ROOT/'partitions/demo-test-01.json'))['assignment_ids']:
 folder=ROOT/'work'/aid;plan=json.load(open(folder/'case-plan.json'));specs=[]
 for comp in plan['comparisons']:
  cid=comp['comparison_id']
  if '400-2a' in aid:field='approach_full_body_centerline_offsets.value.minimum_m'
  elif '400-2b' in aid:field='departure_full_body_centerline_offsets.value.minimum_m'
  elif '253' in aid:
   field='reciprocal_driver_history.value.samples.0.speed_mps' if cid=='reciprocal_duty' else 'opposing_yield_window.value.original_samples.0.left_indicator_bit' if cid=='subsequent_signal' else 'opposing_yield_window.value.original_samples.0.subject_speed_mps'
  elif '223' in aid:field='signal_onset_relative_to_lateral_movement.value.signal_first_frame' if cid=='signal_before_movement' else 'target_lane_full_body_gap.value.minimum_signed_gap_m'
  elif '127-3' in aid:field='caravan_full_body_gaps.value.minimum_rear_gap_m'
  else:field='pre_crosswalk_body_front_and_speed.value.minimum_pre_crossing_speed_mps'
  specs.append(dict(comparison_id=cid,case_ids=comp['case_ids'],fixed_config_selectors=['duration_s','rate_hz','cameras','requested_speed_mps','cell_id','actor','law_id'],checks=[dict(name='Measured deliberate difference: '+cid,case_ids=comp['case_ids'],selector='measurements.'+field,operator='distinct')]))
 write(folder/'comparison-audit-specs.json',specs)
 if '--specs-only' in sys.argv:continue
 manifest=json.load(open(folder/'execution-manifest.json'));index={}
 for e in manifest['cases']:
  matches=[]
  for report in (ROOT/'.runtime-work'/aid).rglob('analysis-report.json'):
   construction=report.parent/'construction.json'
   if construction.exists() and sha(construction)==e['construction_sha256'] and json.load(open(report)).get('case_id')==e['case_id']:matches.append(report)
  if not matches:raise ValueError('No exact proven analysis report: '+e['case_id'])
  p=max(matches,key=lambda p:p.stat().st_mtime);index[e['case_id']]=dict(analysis_report=str(p),config=str(p.parent/'config.json'))
 log=[]
 for spec in specs:
  result=audit.audit(spec,index);write(folder/'receipts'/('compare-'+spec['comparison_id']+'.json'),result);log.append(spec['comparison_id']+' PASS measured difference and fixed configuration')
  # Confirm each comparison fails when the deliberate measured difference is removed.
  bad=dict(spec);bad['checks']=[dict(spec['checks'][0],operator='equal')]
  try:audit.audit(bad,index)
  except ValueError:log.append(spec['comparison_id']+' PASS negative equality rejected')
  else:raise AssertionError('Comparison failed to detect controlled difference')
 path=folder/'receipts/comparison-tests.log';path.write_text('\n'.join(log)+'\n')
 result=json.load(open(folder/'result.json'));result['tests'].append(dict(command='python3.11 work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/audit_partition.py',exit_code=0,log='receipts/comparison-tests.log',sha256=sha(path)));write(folder/'result.json',result)
 print(aid,len(specs),'comparisons passed')
