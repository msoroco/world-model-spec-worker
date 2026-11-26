"""Select exact parked lamp drafts without asserting physical acceptance."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
AID=ROOT.name
NAMES=('runner.py','parked_lamps.py','finalize_original.py','finalize_saved.py','sloped-curb-road.xodr')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')

def main():
    cases=[]
    for suffix in ('probe_a','probe_b'):
        case=AID+'__'+suffix
        draft=json.loads((ROOT/'draft-native'/suffix/'construction.json').read_text())
        cfg=json.loads(next(item['content'] for item in draft['files'] if item['path']=='config.json'))
        cfg.update(assignment_id=AID,candidate_id='primary',physical_completion={},
                   physical_acceptance_claimed=False)
        desc={'channels':[{'name':name,'unit':unit,'method':method,
                           'reference_frame':'original parked subject at C276263 sloped curb',
                           'sampling_rate_hz':20,'time_window':'600 frames / 30 s',
                           'uncertainty':'50 ms sampling; original pixel review required'}
                          for name,unit,method in (
                              ('drv.standing_or_parked','state','original parked activity review and body pose'),
                              ('sig.headlamp','state','original post-tick lamp readback and pixel review'),
                              ('kin.velocity','m/s','original post-tick three-axis velocity'),
                              ('rel.occupies','state','original full footprint and curb lane readback'))],
              'context_inputs':[],
              'limitations':['Low-beam request alone does not prove depressed or dimmed',
                             'Synthetic fixtures do not establish original physical beam or legal outcome']}
        cfg['recording_description']=desc
        files=[{'path':name,'content':(ROOT/'native'/name).read_text()} for name in NAMES]
        files.append({'path':'road.xodr','content':(ROOT/'native/sloped-curb-road.xodr').read_text()})
        files += [{'path':'config.json','content':json.dumps(cfg,indent=2,ensure_ascii=False)+'\n'},
                  {'path':'tests/test_offline.py','content':'''import json\nimport unittest\nfrom pathlib import Path\nimport runner\n\nclass SelectedLamp(unittest.TestCase):\n def test_exact(self):\n  cfg=json.loads(Path('config.json').read_text())\n  self.assertEqual(cfg['selected_case_id'],cfg['assignment_id']+'__'+cfg['case_id'].rsplit('__',1)[-1])\n  self.assertEqual(runner.check() if hasattr(runner,'check') else cfg['frames'],600)\n'''}]
        construction={'format':'worker-construction','assignment_id':AID,
                      'case_id':case,'law_id':'NRS-484D-165-4','cell_id':'C276263',
                      'actor':'motor_vehicle_driver','entrypoint':'runner.py',
                      'files':files,'recording_description':desc,
                      'measurement_plan':draft['measurement_plan'],
                      'static_checks':draft['static_checks'],
                      'termination_rules':draft['termination_rules'],
                      'mechanisms':draft['mechanisms']}
        construction_path=ROOT/('selected-'+suffix+'-construction.json')
        write(construction_path,construction)
        contract={'format':'worker-measurement-contract','case_id':case,'status':'selected',
                  'requirements':[{'disposition_index':0,'requirement':'NRS-484D-165-4',
                                   'source':'NRS 484D.165(4)','kind':'measured',
                                   'method':'measure_parked_lamps',
                                   'output_key':'parked_headlamp_observation',
                                   'value_type':'object','inputs':list(('native-rows.jsonl','lamp-review.jsonl',
                                           'parking-context.json','video_frames.jsonl','trace.jsonl','capture/evidence.jsonl'))}],
                  'negative':{'remove':['lamp-review.jsonl'],
                              'error_contains':'Missing required source: lamp-review.jsonl'}}
        contract_path=ROOT/('selected-'+suffix+'-measurement-contract.json')
        write(contract_path,contract)
        cases.append({'case_id':case,'kind':'delivery','construction':construction_path.name,
                      'construction_sha256':sha(construction_path),
                      'fixture_recipe':f'work/{AID}/native/diagnostic/{suffix}/fixture-recipe.json',
                      'measurement_contract':contract_path.name,
                      'measurement_procedure':{'entrypoint':'finalize_saved.py'},
                      'native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'},
                      'candidate_risk':{'status':'physical','reason':'Original parked activity and beam pixel review needed.'},
                      'candidates':[]})
    write(ROOT/'selected-draft-execution-manifest.json',
          {'format':'worker-execution-manifest','assignment_id':AID,
           'runtime_manifest_sha256':sha(Path('runtime/SOURCE-MANIFEST.json')),
           'status':'selected_cpu_proofs_pending','cases':cases,
           'original_native_observed':False,'delivery_ready':False})

if __name__=='__main__':main()
