"""Standalone six-step return contract; no database, simulator or code execution."""
import ast
from pathlib import Path
from .common import read, sha, tree, digest, within


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(repo, complete=False, require_ready=False):
    repo = Path(repo)
    batch = read(repo/'batch.json')
    require(batch['mode'] == 'six_step_preparation', 'Wrong batch mode')
    for rel, checksum in batch['frozen_files'].items():
        require(sha(within(repo, rel)) == checksum, 'Changed frozen file: '+rel)
    allocated = []
    for path in sorted((repo/'partitions').glob('*.json')):
        allocated.extend(read(path)['assignment_ids'])
    require(len(allocated) == len(set(allocated)) and set(allocated) == set(batch['assignments']), 'Partition coverage/overlap')
    files = tree(repo)
    for rel in files:
        if rel in batch['frozen_files'] or rel == 'batch.json':
            continue
        parts = Path(rel).parts
        require(len(parts)>2 and parts[0]=='work' and parts[1] in (*batch['assignments'], '_shared'), 'Unapproved output: '+rel)
        path = within(repo, rel)
        require(path.stat().st_size <= 2*1024*1024, 'Oversized return')
        text = path.read_text()
        if path.suffix == '.py':
            ast.parse(text)
    results, all_ids = {}, set()
    for aid, item in batch['assignments'].items():
        folder = repo/'work'/aid
        if not (folder/'result.json').exists():
            require(not complete, 'Missing result: '+aid)
            continue
        result, original = read(folder/'result.json'), read(repo/'inputs'/aid/'assignment.json')
        require(result['assignment_id']==aid and result['input_sha256']==item['input_sha256'], 'Return identity/input mismatch')
        require(result['status'] in ('ready','partial','blocked'), 'Invalid return status')
        require(result.get('applied_update')==batch['update_version'], 'Unacknowledged current update')
        require((folder/'HANDOFF.md').is_file(), 'Missing handoff')
        require(result['status']=='ready' or result.get('reason'), 'Missing precise gap')
        plan = read(folder/'case-plan.json')
        require(plan['assignment_id']==aid and plan['actor']==original['actor'] and plan['cell_id']==original['cell_id'] and plan['law_id']==original['law_id'], 'Plan scope mismatch')
        for key in ('cases','comparisons','observations','sources','existing_evidence','runtime_uncertainties'):
            require(isinstance(plan.get(key),list), 'Missing/malformed plan '+key)
        require(plan['sources'] and plan['runtime_uncertainties'], 'Missing sources or explicit runtime limits')
        for ref in plan['sources']:
            require(isinstance(ref,dict) and ref.get('path') and ref.get('sha256'), 'Unversioned source reference')
            require(sha(within(repo,ref['path']))==ref['sha256'], 'Stale cited source')
        ids=set()
        for case in plan['cases']:
            cid=case.get('case_id')
            require(isinstance(cid,str) and cid.startswith(aid+'__') and cid not in all_ids, 'Duplicate/unqualified case ID')
            all_ids.add(cid);ids.add(cid)
            require(case.get('target_law_id') in (None,original['law_id']), 'Wrong case law')
        for comparison in plan['comparisons']:
            require(set(comparison.get('case_ids',[])) <= ids and len(comparison.get('case_ids',[]))>=2, 'Broken comparison members')
            require(comparison.get('deliberate_differences') and 'fixed_conditions' in comparison, 'Unspecified comparison isolation')
        if result['status']=='ready':
            if batch.get('runtime'):
                if result.get('readiness_kind') not in ('capability','delivery_prepared'):
                    raise ValueError('Declare first-run capability versus delivery preparation')
                from .execution_manifest import validate as validate_execution_manifest
                validate_execution_manifest(repo,aid)
            require(plan['cases'] and plan['observations'], 'Ready with no cases/observations')
            for filename in ('runner.py','config.json','construction.json','proposals/cases.json'):
                require((folder/filename).is_file(), 'Missing executable artifact '+filename)
            construction = read(folder/'construction.json')
            for key in ('entrypoint','files','measurement_plan','recording_description','static_checks','termination_rules','mechanisms'):
                require(key in construction, 'Missing construction contract '+key)
            require(construction.get('cell_id')==original['cell_id'] and construction.get('actor')==original['actor'], 'Construction identity mismatch')
            require(construction['entrypoint']=='runner.py', 'Noncanonical entrypoint')
            for entry in construction['files']:
                require(within(repo,entry['source']).read_text()==entry['content'] if entry.get('source') else within(folder,entry['path']).read_text()==entry['content'], 'Inline/materialized construction mismatch')
            require('runner.py' in {f['path'] for f in construction['files']}, 'Runner omitted from construction')
            proposal = read(folder/'proposals/cases.json')
            require(proposal.get('cell_id')==original['cell_id'] and proposal.get('actor')==original['actor'] and proposal.get('status')=='draft', 'Noncanonical cases proposal identity')
            require(isinstance(proposal.get('sweep_specs'),list) and isinstance(proposal.get('cases'),list), 'Missing canonical cases/sweeps')
            require({c.get('case_id') for c in proposal['cases']}==ids, 'Proposal/plan case coverage mismatch')
            for case in proposal['cases']:
                for key in ('target_law_id','target_type','rationale','variable_assignments','unresolved_judgment_calls','recording_description'):
                    require(key in case, 'Missing canonical case field '+key)
            config = read(folder/'config.json')
            require(config.get('actor')==original['actor'] and config.get('law_id')==original['law_id'], 'Wrong config identity')
            require(set(config.get('supported_case_ids',[]))==ids, 'Configuration does not cover cases')
            channels = {c['name'] for c in construction['recording_description']['channels']}
            required = {o['name'] for o in plan['observations'] if o.get('mandatory',True)}
            require(required <= channels, 'Missing mandatory capture channels')
            require(list((folder/'tests').glob('test*.py')), 'Missing CPU tests')
            require(result.get('tests'), 'Missing CPU test evidence')
            for test in result['tests']:
                require(test.get('exit_code')==0 and test.get('command'), 'CPU test did not pass')
                require(sha(within(folder,test['log']))==test['sha256'], 'Missing/changed test log')
        results[aid]=result
    if require_ready:
        require(len(results)==len(batch['assignments']) and all(r['status']=='ready' for r in results.values()), 'Preparation acceptance failed: partial/missing packages remain')
    return {'batch_id':batch['batch_id'],'results':results,'files':files,'package_sha256':digest(files),
            'verification':'Static contract only; explicitly run CPU tests before local adoption'}
