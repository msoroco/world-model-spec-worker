"""Canonical explicit-case handoff; no dynamic sweep-index selection at dispatch."""
from pathlib import Path
from .common import read,sha,within


def validate(repo,assignment_id):
    repo=Path(repo).resolve();folder=repo/'work'/assignment_id
    manifest=read(folder/'execution-manifest.json');batch=read(repo/'batch.json')
    if manifest.get('format')!='worker-execution-manifest-v1' or manifest.get('assignment_id')!=assignment_id:
        raise ValueError('Execution manifest identity/format mismatch')
    runtime=repo/batch['runtime']['root']
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
        construction=read(source)
        if construction['case_id']!=ident:raise ValueError('Wrong selected construction')
        case=next(c for c in proposal['cases'] if c['case_id']==ident)
        if case.get('recording_description')!=construction['recording_description']:
            raise ValueError('Construction changed the capture contract')
        configs=[f for f in construction['files'] if f['path']=='config.json']
        if len(configs)!=1:raise ValueError('One config.json required')
        import json
        config=json.loads(configs[0]['content'])
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
    if not expected<=seen:raise ValueError('Nonbaseline case missing from execution manifest')
    return manifest
