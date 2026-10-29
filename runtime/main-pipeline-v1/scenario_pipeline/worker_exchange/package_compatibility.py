"""Actual package analysis -> existing native validation -> Core -> video, CPU only."""
import argparse,json,shutil,subprocess,sys,tempfile
from pathlib import Path
from .common import read,write,sha,within,tree,digest
from .runtime_cli import materialize,execution_env,process,render
from .native_output import validate_result

PACKET_FILES = {
    'scenario_geometry': 'scenario_geometry.json',
    'scenario_rule_evidence': 'scenario_rule_evidence.jsonl',
    'environment_calibration': 'environment_calibration.json',
    'surface_provenance': 'surface_provenance.json',
}


def check_source_packets(config, paths):
    packets=config.get('source_packets',[])
    if not isinstance(packets,list) or any(p not in PACKET_FILES for p in packets):
        raise ValueError('Unknown source packet declaration')
    missing={PACKET_FILES[p] for p in packets}-set(paths)
    if missing:raise ValueError('Diagnostic fixture missing declared source packet: '+','.join(sorted(missing)))

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
    check_source_packets(config, tree(fixture))
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


def run_recipe(manifest,case,output,library,validator):
    """Exercise selected measurements and a missing case source, then Core/video."""
    from .fixture_recipe import materialize
    from .measurement_contract import validate,verify_report
    manifest=Path(manifest).resolve();output=Path(output).resolve();repo=manifest.parents[2]
    if repo/'.runtime-work' not in output.parents:
        raise ValueError('Generated compatibility output belongs in ignored .runtime-work')
    entry=next((e for e in read(manifest)['cases'] if e['case_id']==case),None)
    if entry is None:raise ValueError('Select exact case')
    folder=manifest.parent;contract_path=within(folder,entry['measurement_contract'])
    recipe_path=within(repo,entry['fixture_recipe'])
    contract=read(contract_path)
    construction=read(within(folder,entry['construction']))
    analysis_code=next(f['content'] for f in construction['files'] if f['path']==entry['measurement_procedure']['entrypoint'])
    plan=read(folder/'case-plan.json')
    validate(contract,plan['requirement_dispositions'],analysis_code,case)
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix='fixture-') as temporary:
        fixture=Path(temporary)/'positive';source=materialize(repo,recipe_path,fixture)
        receipt=run(manifest,case,fixture,output,library,validator)
        measurements=verify_report(contract,read(output/'analysis-report.json'),fixture)
        negative=Path(temporary)/'negative'
        proposal=materialize_case(manifest,case,negative,fixture)
        removed=contract['negative']['remove'][0]
        if removed not in tree(fixture):raise ValueError('Negative source absent from positive fixture')
        within(negative,removed).unlink()
        analysis=within(negative,entry['measurement_procedure']['entrypoint'])
        failure=subprocess.run([sys.executable,str(analysis),'--attempt',str(negative),'--output',str(negative/'analysis-report.json')],
                               cwd=negative,env=execution_env(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                               universal_newlines=True,timeout=300)
        (output/'negative-analysis.log').write_text(failure.stdout)
        expected=contract['negative']['error_contains']
        if failure.returncode==0 or expected not in failure.stdout:
            raise ValueError('Negative case-source fixture did not fail as specified')
    receipt.update(format='worker-package-compatibility-v2',
                   checks=receipt['checks']+['selected_measurements','negative_case_source'],
                   fixture_recipe_sha256=source['recipe_sha256'],fixture_base_sha256=source['base_sha256'],
                   measurement_contract_sha256=sha(contract_path),analysis_report_sha256=sha(output/'analysis-report.json'),
                   measurement_keys=sorted(measurements),measurement_examples=measurements,negative_removed=removed,
                   negative_error_contains=expected,negative_log_sha256=sha(output/'negative-analysis.log'))
    write(output/'compatibility.json',receipt)
    return receipt


def materialize_case(manifest,case,destination,fixture):
    from .runtime_cli import materialize
    proposal=materialize(manifest,case,destination)
    for source in fixture.iterdir():
        target=destination/source.name
        if target.exists():raise ValueError('Fixture shadows negative package')
        if source.is_dir():shutil.copytree(source,target)
        else:shutil.copyfile(source,target)
    return proposal

CHECKS={'actual_analysis','native_validation','mandatory_observations','lean_decoder','render','final_decode','acquisition_unchanged'}

def check_receipts(repo,folder,manifest):
    """Static receipt verification; local takeover independently reruns the command."""
    batch=read(Path(repo)/'batch.json') if (Path(repo)/'batch.json').is_file() else {}
    strict=batch.get('measurement_contract_required',False)
    for entry in manifest['cases']:
        spec=entry.get('compatibility',{})
        if not spec.get('receipt') or not spec.get('sha256') or not spec.get('log') or (not strict and not spec.get('fixture')):raise ValueError('Missing package compatibility proof: '+entry['case_id'])
        path=within(folder,spec['receipt'])
        if sha(path)!=spec['sha256']:raise ValueError('Compatibility receipt changed')
        proof=read(path)
        expected_format='worker-package-compatibility-v2' if strict else 'worker-package-compatibility-v1'
        required_checks=CHECKS|({'selected_measurements','negative_case_source'} if strict else set())
        if proof.get('format')!=expected_format or proof.get('passed') is not True or not required_checks<=set(proof.get('checks',[])):raise ValueError('Incomplete package compatibility proof')
        for key,value in [('case_id',entry['case_id']),('construction_sha256',entry['construction_sha256']),('runtime_manifest_sha256',manifest['runtime_manifest_sha256'])]:
            if proof.get(key)!=value:raise ValueError('Stale compatibility '+key)
        if sha(within(folder,spec['log']))!=proof.get('log_sha256'):raise ValueError('Compatibility analysis log changed')
        if strict:
            from .fixture_recipe import materialize
            from .measurement_contract import validate,verify_report
            recipe=within(repo,entry['fixture_recipe'])
            with tempfile.TemporaryDirectory() as temporary:
                fixture=Path(temporary)/'fixture';source=materialize(repo,recipe,fixture)
                if source['fixture_sha256']!=proof.get('fixture_sha256') or source['recipe_sha256']!=proof.get('fixture_recipe_sha256') or source['base_sha256']!=proof.get('fixture_base_sha256'):
                    raise ValueError('Compatibility fixture recipe changed')
                config_source=read(within(folder,entry['construction']))
                config=json.loads(next(f['content'] for f in config_source['files'] if f['path']=='config.json'))
                check_source_packets(config,tree(fixture))
                contract_path=within(folder,entry['measurement_contract']);contract=read(contract_path)
                plan=read(folder/'case-plan.json')
                analysis_code=next(f['content'] for f in config_source['files'] if f['path']==entry['measurement_procedure']['entrypoint'])
                validate(contract,plan['requirement_dispositions'],analysis_code,entry['case_id'])
                verify_report(contract,{'measurements':proof.get('measurement_examples')},fixture)
        else:
            fixture=within(repo,spec['fixture'])
            if digest(tree(fixture))!=proof.get('fixture_sha256'):raise ValueError('Compatibility fixture changed')
        construction=read(within(folder,entry['construction']))
        analysis=entry['measurement_procedure']['entrypoint']
        files={f['path']:f['content'] for f in construction['files']}
        import hashlib
        if analysis not in files or hashlib.sha256(files[analysis].encode()).hexdigest()!=proof.get('analysis_sha256'):raise ValueError('Compatibility analysis changed')
        acquisition=entry.get('acquisition',{})
        config=json.loads(files['config.json'])
        if not strict:check_source_packets(config, tree(fixture))
        if strict:
            if proof.get('measurement_contract_sha256')!=sha(contract_path) or proof.get('measurement_keys')!=sorted(r['output_key'] for r in contract['requirements']):
                raise ValueError('Selected measurement proof changed')
            negative=entry.get('negative',{})
            if sha(within(folder,negative['log']))!=proof.get('negative_log_sha256') or proof.get('negative_removed')!=contract['negative']['remove'][0] or proof.get('negative_error_contains')!=contract['negative']['error_contains']:
                raise ValueError('Negative case-source proof changed')
            if contract['negative']['error_contains'] not in within(folder,negative['log']).read_text():
                raise ValueError('Negative log lacks expected case-source error')
        required=set(config.get('required_atoms',[]))|{c['name'] for c in construction['recording_description']['channels']}
        if not required<=set(acquisition):raise ValueError('Mandatory observation lacks acquisition implementation')
        for atom in required:
            source=acquisition[atom]
            if source.get('entrypoint') not in files or not source.get('method') or not source.get('evidence'):raise ValueError('Incomplete acquisition source: '+atom)
    return True

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--case',required=True);p.add_argument('--fixture');p.add_argument('--output',required=True);p.add_argument('--library',required=True);p.add_argument('--validator',required=True);p.add_argument('--recipe',action='store_true');a=p.parse_args()
    if a.recipe:result=run_recipe(a.manifest,a.case,a.output,a.library,a.validator)
    else:
        if not a.fixture:p.error('--fixture required without --recipe')
        result=run(a.manifest,a.case,a.fixture,a.output,a.library,a.validator)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
