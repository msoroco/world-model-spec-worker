"""Apply tested update002 analysis/capture repair, preserving all case/branch plans."""
import ast,hashlib,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'work/_shared'))
import update002_tools as t
import runtime002

def main():
 runtime=runtime002.prepare_runtime();runtime002.activate_runtime(ROOT,runtime)
 from worker_exchange.native_output import default_descriptor
 spec=importlib.util.spec_from_file_location('tail_migration',ROOT/'work/testing__C125714__NRS-484B-250-1__motor_vehicle_driver/build_migration_sources.py');migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
 before=t.read(ROOT/'.runtime-work/update002/originals/branch-plan.json');after=t.read(ROOT/'work/_shared/branch-coverage.json')
 assert before==after,'Branch/comparison plan changed'
 total=0
 for path in sorted((ROOT/'work').glob('*/execution-manifest.json')):
  folder=path.parent;manifest=t.read(path);old=t.read(ROOT/'.runtime-work/update002/originals'/folder.name/'manifest.json')
  assert [e['case_id'] for e in manifest['cases']]==[e['case_id'] for e in old['cases']]
  for i,e in enumerate(manifest['cases']):
   original=t.read(ROOT/'.runtime-work/update002/originals'/folder.name/('construction-'+str(i)+'.json'))
   runner=next(f['content'] for f in original['files'] if f['path']=='runner.py');analyzer=next(f['content'] for f in original['files'] if f['path']=='analyze.py')
   newrunner,prepare=migration.migrate_runner(runner);newanalyzer=t.annotate_analyzer(analyzer,prepare)
   ast.parse(newrunner);ast.parse(newanalyzer);t.update_case(folder,e,newrunner,newanalyzer)
   bundle=t.read(folder/e['construction']);config_item=next(f for f in bundle['files'] if f['path']=='config.json');cfg=json.loads(config_item['content']);cfg['physical_completion']=default_descriptor(cfg);cfg['processing_contract_version']=2
   text=json.dumps(cfg,indent=2)+'\n';config_item['content']=text;(folder/e['construction']).parent.joinpath('config.json').write_text(text)
   t.write(folder/e['construction'],bundle);e['construction_sha256']=t.sha(folder/e['construction'])
   e['native_handoff'].update(capture_only=True,resource_owner='local_operator',owner_release_receipt_required=True)
   e['measurement_procedure'].update(analysis_revision=t.sha((folder/e['construction']).parent/'analyze.py'),saved_only=True)
   total+=1
  manifest['runtime_manifest_sha256']=t.sha(runtime/'SOURCE-MANIFEST.json');manifest['processing_contract_version']=2;t.write(path,manifest)
  result=t.read(folder/'result.json');result.update(applied_update=2,status='partial',reason='Update002 exact-case revalidation in progress',tests=[]);t.write(folder/'result.json',result)
 print('Migrated exact cases:',total);assert total==236
 t.write(ROOT/'work/_shared/update002-migration.json',{'format':'worker-update002-migration-v1','cases':total,'branch_plan_preserved':True,'branch_coverage_sha256':t.sha(ROOT/'work/_shared/branch-coverage.json'),'runtime_manifest_sha256':t.sha(runtime/'SOURCE-MANIFEST.json'),'bootstrap_sha256':t.sha(ROOT/'work/_shared/runtime002.py'),'capture_only':True,'saved_only_processing':True,'carla_executed':False})
if __name__=='__main__':main()
