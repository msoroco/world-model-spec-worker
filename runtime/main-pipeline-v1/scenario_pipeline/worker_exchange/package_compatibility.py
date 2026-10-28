"""Actual package analysis -> existing native validation -> Core -> video, CPU only."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path
from .common import read,write,sha,within,tree,digest
from .runtime_cli import materialize,execution_env,process,render
from .native_output import validate_result

def run(manifest,case,fixture,output,library,validator):
    manifest=Path(manifest).resolve();output=Path(output).resolve();library=Path(library).resolve();validator=Path(validator).resolve()
    entries=[c for c in read(manifest)['cases'] if c['case_id']==case]
    if len(entries)!=1:raise ValueError('Select exact case')
    entry=entries[0];procedure=entry.get('measurement_procedure',{})
    analysis_path=procedure.get('entrypoint')
    if not analysis_path:raise ValueError('Executable finalization entrypoint required')
    fixture=Path(fixture).resolve();fixture_hash=digest(tree(fixture))
    proposal=materialize(manifest,case,output)
    for p in fixture.iterdir():
        if p.name in ('result.json','analysis-report.json','compatibility.json'):raise ValueError('Fixture cannot supply outputs')
        if (output/p.name).exists():raise ValueError('Fixture shadows package: '+p.name)
        if p.is_dir():shutil.copytree(p,output/p.name)
        else:shutil.copyfile(p,output/p.name)
    proposal_case=next(c for c in read(manifest.parent/'proposals/cases.json')['cases'] if c['case_id']==case)
    config=read(output/'config.json')
    request={'case':proposal_case,'cell':{'cell_id':config['cell_id']},'actor':config['actor']}
    analysis=within(output,analysis_path)
    before=digest(tree(output/'capture'))
    acquisition={p:sha(output/p) for p in tree(fixture)}
    implementation={f['path']:sha(output/f['path']) for f in proposal['files']}
    with (output/'compatibility-analysis.log').open('w') as log:
        subprocess.run([sys.executable,str(analysis),'--attempt',str(output),'--output',str(output/'analysis-report.json')],cwd=output,env=execution_env(),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
    if before!=digest(tree(output/'capture')) or any(sha(output/p)!=h for p,h in acquisition.items()):raise ValueError('Analysis rewrote original acquisition')
    if any(sha(output/p)!=h for p,h in implementation.items()):raise ValueError('Analysis rewrote frozen implementation/configuration')
    result=validate_result(read(output/'result.json'))
    if result.get('case_id')!=case:raise ValueError('Analysis returned another case')
    from batch_pipeline.carla import validate_attempt
    from .media import audit
    mapping_sha=sha(output/result['video_frame_map_reference'])
    count=len((output/result['trace_reference']).read_text().splitlines())
    audits={ref:audit(within(output,ref),count,mapping_sha256=mapping_sha,receipt=output/('source-%d.json'%i)) for i,ref in enumerate(result['video_references'])}
    validate_attempt(output,request,proposal,{'recorded_exit_code':0},{},source_audits=audits)
    process(output,output/'converted',library,validator)
    video=render(output,output/'converted',request['case'])
    audit(video['video'],count,receipt=output/'final-decode.json')
    receipt={'format':'worker-package-compatibility-v1','case_id':case,'construction_sha256':entry['construction_sha256'],'runtime_manifest_sha256':read(manifest)['runtime_manifest_sha256'],'fixture_sha256':fixture_hash,'passed':True,'checks':['actual_analysis','native_validation','mandatory_observations','lean_decoder','render','final_decode','acquisition_unchanged'],'scope':'diagnostic software compatibility only','analysis_sha256':sha(analysis),'fixture_manifest':tree(fixture),'log_sha256':sha(output/'compatibility-analysis.log')}
    write(output/'compatibility.json',receipt);return receipt

CHECKS={'actual_analysis','native_validation','mandatory_observations','lean_decoder','render','final_decode','acquisition_unchanged'}

def check_receipts(repo,folder,manifest):
    """Static receipt verification; local takeover independently reruns the command."""
    for entry in manifest['cases']:
        spec=entry.get('compatibility',{})
        if not spec.get('receipt') or not spec.get('sha256') or not spec.get('fixture') or not spec.get('log'):raise ValueError('Missing package compatibility proof: '+entry['case_id'])
        path=within(folder,spec['receipt'])
        if sha(path)!=spec['sha256']:raise ValueError('Compatibility receipt changed')
        proof=read(path)
        if proof.get('format')!='worker-package-compatibility-v1' or proof.get('passed') is not True or not CHECKS<=set(proof.get('checks',[])):raise ValueError('Incomplete package compatibility proof')
        for key,value in [('case_id',entry['case_id']),('construction_sha256',entry['construction_sha256']),('runtime_manifest_sha256',manifest['runtime_manifest_sha256'])]:
            if proof.get(key)!=value:raise ValueError('Stale compatibility '+key)
        if sha(within(folder,spec['log']))!=proof.get('log_sha256'):raise ValueError('Compatibility analysis log changed')
        fixture=within(repo,spec['fixture'])
        if digest(tree(fixture))!=proof.get('fixture_sha256'):raise ValueError('Compatibility fixture changed')
        construction=read(within(folder,entry['construction']))
        analysis=entry['measurement_procedure']['entrypoint']
        files={f['path']:f['content'] for f in construction['files']}
        import hashlib
        if analysis not in files or hashlib.sha256(files[analysis].encode()).hexdigest()!=proof.get('analysis_sha256'):raise ValueError('Compatibility analysis changed')
        acquisition=entry.get('acquisition',{})
        config=json.loads(files['config.json'])
        required=set(config.get('required_atoms',[]))|{c['name'] for c in construction['recording_description']['channels']}
        if not required<=set(acquisition):raise ValueError('Mandatory observation lacks acquisition implementation')
        for atom in required:
            source=acquisition[atom]
            if source.get('entrypoint') not in files or not source.get('method') or not source.get('evidence'):raise ValueError('Incomplete acquisition source: '+atom)
    return True

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--case',required=True);p.add_argument('--fixture',required=True);p.add_argument('--output',required=True);p.add_argument('--library',required=True);p.add_argument('--validator',required=True);a=p.parse_args();print(json.dumps(run(a.manifest,a.case,a.fixture,a.output,a.library,a.validator),indent=2))
if __name__=='__main__':main()
