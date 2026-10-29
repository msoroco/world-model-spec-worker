"""Canonical explicit-case handoff; no dynamic sweep-index selection at dispatch."""
from pathlib import Path
from .common import read,sha,within


def validate(repo,assignment_id):
    repo=Path(repo).resolve();folder=repo/'work'/assignment_id
    manifest=read(folder/'execution-manifest.json');batch=read(repo/'batch.json')
    if manifest.get('format')!='worker-execution-manifest-v1' or manifest.get('assignment_id')!=assignment_id:
        raise ValueError('Execution manifest identity/format mismatch')
    from .preparation import runtime_for
    runtime=runtime_for(repo,batch)
    from .atom_preflight import check_required_atoms
    if manifest.get('runtime_manifest_sha256')!=sha(runtime/'SOURCE-MANIFEST.json'):
        raise ValueError('Execution manifest binds another runtime')
    from .runtime_cli import verify
    verify(runtime)
    proposal=read(folder/'proposals/cases.json')
    if proposal.get('sweep_specs') and not proposal.get('sweeps_expanded'):
        raise ValueError('Expand sweeps with the main implementation before manifest generation')
    expected={c['case_id'] for c in proposal['cases'] if c['target_type']!='baseline'}
    entries=manifest.get('cases',[]);seen=set()
    if not entries:raise ValueError('No executable cases; baseline-only is not ready')
    for entry in entries:
        ident=entry['case_id']
        if ident in seen or ident not in expected:raise ValueError('Duplicate/undefined executable case')
        seen.add(ident)
        if entry.get('kind') not in ('capability','delivery'):raise ValueError('Declare research capability or delivery')
        source=within(folder,entry['construction'])
        if sha(source)!=entry.get('construction_sha256'):raise ValueError('Construction changed')
        if batch.get('exact_offline_receipts_required'):
            offline=entry.get('offline',{})
            if offline.get('exit_code')!=0 or offline.get('construction_sha256')!=entry['construction_sha256'] or not offline.get('command'):
                raise ValueError('Exact-case offline check missing: '+ident)
            if sha(within(folder,offline['log']))!=offline.get('log_sha256'):
                raise ValueError('Exact-case offline log changed: '+ident)
        if batch.get('update_version',0)>=2 and batch.get('full_branch_coverage_required'):
            from .physical_preparation import validate as validate_physical
            validate_physical(repo,folder,entry)
        construction=read(source)
        if construction['case_id']!=ident:raise ValueError('Wrong selected construction')
        case=next(c for c in proposal['cases'] if c['case_id']==ident)
        if case.get('recording_description')!=construction['recording_description']:
            raise ValueError('Construction changed the capture contract')
        configs=[f for f in construction['files'] if f['path']=='config.json']
        if len(configs)!=1:raise ValueError('One config.json required')
        import json
        config=json.loads(configs[0]['content'])
        check_required_atoms(runtime, config.get('required_atoms', []), config.get('source_packets', []))
        selected=config.get('case',{}).get('case_id') or config.get('selected_case_id')
        if selected!=ident:raise ValueError('Selected case not frozen in bundle')
        for item in construction['files']:
            if item.get('source') and within(repo,item['source']).read_text()!=item['content']:
                raise ValueError('Shared implementation source differs')
        if entry['kind']=='capability':
            procedure=entry.get('measurement_procedure')
            if not isinstance(procedure,dict) or not procedure.get('entrypoint') or not procedure.get('output_schema'):
                raise ValueError('Capability needs executable measured-results finalization procedure')
            if not within(folder,procedure['entrypoint']).is_file():
                raise ValueError('Capability analysis implementation missing')
        if batch.get('measurement_contract_required'):
            from .measurement_contract import validate as validate_measurements
            contract_path=within(folder,entry.get('measurement_contract',''))
            if not contract_path.is_file():raise ValueError('Missing exact-case measurement contract')
            analysis=next((f['content'] for f in construction['files'] if f['path']==entry['measurement_procedure']['entrypoint']),None)
            if analysis is None:raise ValueError('Finalizer absent from exact construction')
            plan=read(folder/'case-plan.json')
            validate_measurements(read(contract_path),plan['requirement_dispositions'],analysis,ident)
            recipe=within(repo,entry.get('fixture_recipe',''))
            from .fixture_recipe import inspect as inspect_fixture
            inspect_fixture(repo,recipe)
            handoff=entry.get('native_handoff',{})
            if handoff.get('python_env_var')!='CARLA_PYTHON' or handoff.get('host_env_var')!='CARLA_HOST' or handoff.get('port_env_var')!='CARLA_PORT':
                raise ValueError('Native handoff must use local runtime variables')
    if not expected<=seen:raise ValueError('Nonbaseline case missing from execution manifest')
    return manifest
