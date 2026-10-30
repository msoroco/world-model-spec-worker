"""Recompute the nearest sampled visible stopping point from original ray packets."""
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
helper=ROOT/'work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/package_builder.py'
m=importlib.util.spec_from_file_location('builder',helper);b=importlib.util.module_from_spec(m);m.loader.exec_module(b)
folder=ROOT/'work/testing__C331230__NRS-484A-450-2__motor_vehicle_driver'
spec=json.loads((folder/'package-spec.json').read_text());oldplan=json.loads((folder/'case-plan.json').read_text())
old=""" return {'samples':data['samples'],'resolution_m':data['resolution_m'],'scope':data['scope']}"""
new=""" cfg=json.loads(required(root,'config.json').read_text())
 if cfg['stop_reference']!='nearest_sight':return {'applicable':False,'reference_kind':cfg['stop_reference'],'sample_count':len(data['samples'])}
 clear=[s for s in data['samples'] if s.get('rays') and all(r.get('clear') is True and not r.get('hits') for r in s['rays'])]
 if not clear:raise ValueError('No sampled clear stopping viewpoint')
 nearest=max(clear,key=lambda s:s['candidate_eye_m'][0])
 return {'applicable':True,'samples':data['samples'],'resolution_m':data['resolution_m'],
  'nearest_sampled_clear_eye_m':nearest['candidate_eye_m'],'source_frame':nearest['source_frame'],
  'selection_method':'greatest approach x before west intersection boundary, among viewpoints with clear rays to both through-road targets',
  'scope':data['scope']}"""
if old not in spec['analysis']:raise ValueError('Unexpected sight method')
spec['analysis']=spec['analysis'].replace(old,new)
spec['runner']=spec['runner'].replace("sight.append({'candidate_eye_m':", "sight.append({'source_frame':world.get_snapshot().frame,'candidate_eye_m':")
for case in spec['cases']:
 for sample in case['fixture']['sight_samples.json']['samples']:sample['source_frame']=21714
spec['dispositions'][2]['cases']=['nearest_sight_halt','nearest_sight_rolling']
spec['test']+='''
class SightSelection(unittest.TestCase):
 def test_select_closest_clear_sample_and_reject_all_blocked(self):
  import json
  from analyze import nearest_sight_samples
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'config.json').write_text(json.dumps({'stop_reference':'nearest_sight'}))
   samples=[{'candidate_eye_m':[x,1.75,1.5],'source_frame':21714,'rays':[{'clear':clear,'hits':[] if clear else [{'label':'obstruction'}]}]} for x,clear in [(-10,True),(-8,True),(-7.5,False)]]
   path=root/'sight_samples.json';path.write_text(json.dumps({'samples':samples,'resolution_m':.25,'scope':'test'}))
   self.assertEqual(nearest_sight_samples(root)['nearest_sampled_clear_eye_m'][0],-8)
   self.assertEqual(nearest_sight_samples(root)['source_frame'],21714)
   for s in samples:s['rays'][0]['clear']=False
   path.write_text(json.dumps({'samples':samples,'resolution_m':.25,'scope':'test'}))
   with self.assertRaisesRegex(ValueError,'No sampled clear'):nearest_sight_samples(root)
'''
b.write(folder/'package-spec.json',spec);b.build(spec)
plan=json.loads((folder/'case-plan.json').read_text());plan['source_observation_mapping']=oldplan['source_observation_mapping'];b.write(folder/'case-plan.json',plan)
b.prove(folder,ROOT/'runtime/main-pipeline-v1/library',ROOT/'.runtime-work/decoder/.lake/build/bin/adapterCheck')
