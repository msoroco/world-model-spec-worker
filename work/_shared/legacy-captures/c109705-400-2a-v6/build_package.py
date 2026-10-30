"""Build an exact-ID analysis revision for the frozen original v6 capture."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def main(runtime_sha):
 contract=json.loads((ROOT/'inputs/legacy-captures/c109705-400-2a-selected-left-turn-v6.json').read_text())
 cfg=ROOT/'references/v6-capability/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/config.json'
 assert sha(cfg)==contract['original_config_sha256'];(HERE/'config.json').write_bytes(cfg.read_bytes())
 analyzer=(HERE/'analyze.py').read_text();start=analyzer.index('FROZEN_SOURCES=');end=analyzer.index('# The frozen input',start)
 analyzer=analyzer[:start]+'FROZEN_SOURCES='+repr({k:v['sha256'] for k,v in contract['source_files'].items()})+'\n'+analyzer[end:];(HERE/'analyze.py').write_text(analyzer)
 proposal=contract['original_case_proposal'];assert json.loads(cfg.read_text())['case']==proposal
 write(HERE/'proposals/cases.json',{'cell_id':contract['cell_id'],'actor':contract['actor'],'status':'draft','sweep_specs':[],'cases':[proposal]})
 files=[]
 for name in ('analyze.py','config.json','tests/test_legacy.py'):
  p=HERE/name
  if p.exists():files.append({'path':name,'content':p.read_text(),'source':str(p.relative_to(ROOT))})
 construction={'case_id':contract['case_id'],'cell_id':contract['cell_id'],'actor':contract['actor'],'entrypoint':'analyze.py','files':files,
  'recording_description':proposal['recording_description'],'measurement_plan':'Exact v6 source keys,900-frame joins, full-body approach offsets and source-derived route completion. No Native replay.',
  'static_checks':['Frozen original case identity and native construction hash','Source-based v6 geometry/body/trace/frame schema','Current analysis revision separate from original acquisition'],
  'termination_rules':['Saved-only completion or explicit missing-evidence feedback; never start Native capture'],
  'mechanisms':['Original source hash verification','Versioned selected analyzer through existing process-saved','Original/results/prior-version preservation'],
  'saved_only':True,'native_replay_prohibited':True}
 write(HERE/'construction.json',construction)
 manifest={'format':'worker-execution-manifest-v1','assignment_id':'legacy-c109705-400-2a-v6','runtime_manifest_sha256':runtime_sha,'processing_contract_version':2,'saved_only':True,
  'cases':[{'case_id':contract['case_id'],'kind':'capability','construction':'construction.json','construction_sha256':sha(HERE/'construction.json'),
  'native_construction_sha256':contract['original_construction_sha256'],'measurement_procedure':{'entrypoint':'analyze.py','output_schema':'worker-analysis-report-v1','analysis_revision':sha(HERE/'analyze.py'),'saved_only':True}}]}
 write(HERE/'execution-manifest.json',manifest)
 print('Isolated legacy case:',contract['case_id']);print('New analysis construction:',manifest['cases'][0]['construction_sha256'])
if __name__=='__main__':
 import argparse;p=argparse.ArgumentParser();p.add_argument('--runtime-sha',required=True);main(p.parse_args().runtime_sha)
