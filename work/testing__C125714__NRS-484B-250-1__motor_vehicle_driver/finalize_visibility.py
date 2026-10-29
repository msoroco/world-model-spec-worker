"""Bind law visibility to retained original RGB/instance calibration, never fog/grid labels."""
import importlib.util,json,pathlib,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[2];aid='testing__C179789__NRS-484B-600-1a__motor_vehicle_driver';f=ROOT/'work'/aid
s=importlib.util.spec_from_file_location('b',ROOT/'work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/package_builder.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
spec=json.loads((f/'package-spec.json').read_text());analysis=spec['analysis']
helper='''def read_calibrated_visibility(root):
    source=required(root,'environment_calibration.json');cal=json.loads(source.read_text());sources={'environment_calibration.json':hashlib.sha256(source.read_bytes()).hexdigest()};samples=[]
    for sample in cal['samples']:
      for channel in ('rgb','instance'):
        path=required(root,sample[channel]['path']);digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=sample[channel]['sha256']:raise ValueError('Calibration original image hash mismatch: '+sample[channel]['path'])
        sources[sample[channel]['path']]=digest
      samples.append({'calibration_native_frame':sample['frame'],'sample_range_m':sample['longitudinal_range_m'],'target_pixels':sample['target_pixels'],'weber_contrast':sample['weber_contrast'],'contrast_detected':sample['contrast_detected'],'rgb_source':sample['rgb'],'instance_source':sample['instance']})
    return {'visibility_m':cal['visibility_m'],'distance_kind':cal['distance_kind'],'method':cal['method'],'original_contrast_samples':samples,'calibration_weather':cal['weather'],'uncertainty':cal['uncertainty'],'not_geometric_sight_distance':True,'not_a_legal_visibility_threshold':True},sources

'''
analysis=analysis.replace('def statutory_observations(p):',helper+'def statutory_observations(p):').replace("'weather_rows':p['weather_rows']", "'visibility_calibration':p['visibility_calibration'],'weather_rows':p['weather_rows']")
analysis=analysis.replace('    measurements={}','    visibility,calibration_hashes=read_calibrated_visibility(root)\n    p[\'visibility_calibration\']=visibility\n    measurements={}')
# In this finalizer measurements starts empty. All actual source bindings carry original calibration/image SHA receipts.
assert 'visibility,calibration_hashes=' in analysis
analysis=analysis.replace("'sources':{'case_observation.json':h}","'sources':{'case_observation.json':h,**calibration_hashes}").replace('"sources":{"case_observation.json":h}', '"sources":{"case_observation.json":h,**calibration_hashes}')
run=spec['runner'].replace("'precipitation_native':t['weather']['precipitation']", "'fog_density_native':t['weather']['fog_density'],'precipitation_native':t['weather']['precipitation']")
spec.update(runner=run,analysis=analysis)
cal=json.loads((ROOT/'runtime/main-pipeline-v1/fixtures/retained-speed/environment_calibration.json').read_text());inputs=['case_observation.json','environment_calibration.json']+[s[c]['path'] for s in cal['samples'] for c in ['rgb','instance']]
spec['dispositions'][0]['measurement']['inputs']=inputs
for c in spec['cases']:
 p=c['fixture']['case_observation.json'];p['target_visibility_samples_m']=[25,50,100,200,400]
 for row in p['weather_rows']:row['fog_density_native']=c['config'].get('fog_density',2)
b.write(f/'package-spec.json',spec);b.build(spec)
plan=json.loads((f/'case-plan.json').read_text());plan['source_observation_mapping']['env.visibility']['evidence']='Existing environment_acquisition.calibrate captures original RGB and instance target-mask images; saved finalizer verifies every image SHA, reads contrast/detection observations and sampled visibility lower bound from environment_calibration.json. Fog-density weather and geometric ray sight distance remain separate.';plan['source_observation_mapping']['env.visibility']['source_refs'] += ['runtime/main-pipeline-v1/scenario_pipeline/worker_exchange/environment_acquisition.py'];b.write(f/'case-plan.json',plan)
print('actual original-image visibility source binding complete')
