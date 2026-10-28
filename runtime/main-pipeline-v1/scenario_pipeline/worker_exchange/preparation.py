"""Standalone six-step return contract; no database, simulator or code execution."""
import ast
from pathlib import Path
from .common import read, sha, tree, digest, within


def require(condition, message):
    if not condition:
        raise ValueError(message)


def runtime_for(repo, batch):
    """Use a verified worker overlay only in the actual worker checkout."""
    from .common import sha
    baseline = repo / batch['runtime']['root']
    if not (repo / 'overlay.py').is_file():
        return baseline
    from overlay import ROOT, effective_runtime
    if repo.resolve() != ROOT.resolve():
        return baseline
    effective = effective_runtime()
    if sha(baseline/'SOURCE-MANIFEST.json') != batch['runtime']['source_manifest_sha256']:
        raise ValueError('Batch pinned runtime mismatch')
    return effective


def check(repo, complete=False, require_ready=False):
    repo = Path(repo)
    batch = read(repo/'batch.json')
    require(batch['mode'] == 'six_step_preparation', 'Wrong batch mode')
    for rel, checksum in batch['frozen_files'].items():
        require(sha(within(repo, rel)) == checksum, 'Changed frozen file: '+rel)
    if batch.get('reference_catalog'):
        catalog = read(within(repo, batch['reference_catalog']))
        require(catalog.get('format')=='worker-reference-catalog-v1', 'Invalid reference catalog')
        for source in catalog['items']:
            require(sha(within(repo, source['path']))==source['sha256'], 'Changed source reference')
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
        if path.suffix == '.py':
            ast.parse(path.read_text())
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
        if batch.get('selected_branch_dispositions_required'):
            require(plan.get('selected_branch') == original['branch'], 'Selected witness branch changed')
            dispositions = plan.get('requirement_dispositions')
            require(isinstance(dispositions,list) and dispositions, 'Missing requirement dispositions')
            require(any(d.get('status')=='selected_required' for d in dispositions), 'No selected branch requirement')
            for disposition in dispositions:
                require(disposition.get('requirement') and disposition.get('source') and
                        disposition.get('status') in ('selected_required','alternative_pending','exception_pending') and
                        disposition.get('evidence_or_gap'), 'Incomplete requirement disposition')
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
        executable_required = batch.get('all_executable_required') and result['status']!='blocked'
        if result['status']=='ready' or executable_required:
            if batch.get('runtime'):
                if result['status']=='ready' and result.get('readiness_kind') not in ('capability','delivery_prepared'):
                    raise ValueError('Declare first-run capability versus delivery preparation')
                from .execution_manifest import validate as validate_execution_manifest
                executable=validate_execution_manifest(repo,aid)
                if batch['runtime'].get('package_compatibility_required'):
                    from .package_compatibility import check_receipts
                    check_receipts(repo,folder,executable)
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
            if batch.get('runtime'):
                from .atom_preflight import check_required_atoms
                check_required_atoms(runtime_for(repo,batch), config.get('required_atoms', []), config.get('source_packets', []))
            require(config.get('actor')==original['actor'] and config.get('law_id')==original['law_id'], 'Wrong config identity')
            require(set(config.get('supported_case_ids',[]))==ids, 'Configuration does not cover cases')
            channels = {c['name'] for c in construction['recording_description']['channels']}
            if batch.get('source_observation_mapping_required'):
                terms = {item['term'] for item in original.get('source_observation_terms', [])}
                mapping = plan.get('source_observation_mapping')
                require(isinstance(mapping, dict) and set(mapping) == terms,
                        'Every source observation term needs an evidence mapping')
                for term, evidence in mapping.items():
                    require(isinstance(evidence, dict) and evidence.get('evidence') and
                            isinstance(evidence.get('channels'), list) and
                            isinstance(evidence.get('source_refs'), list) and
                            (evidence['channels'] or evidence['source_refs']),
                            'Incomplete source observation mapping: '+term)
                    require(set(evidence['channels']) <= channels,
                            'Source observation mapping names uncaptured channel: '+term)
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
    if complete and batch.get('runtime_selftest_required'):
        proof = read(repo/'work/_shared/runtime-proof.json')
        runtime = runtime_for(repo,batch)
        require(proof.get('format')=='worker-runtime-proof-v1' and
                proof.get('runtime_manifest_sha256')==sha(runtime/'SOURCE-MANIFEST.json'),
                'Runtime selftest proof binds another runtime')
        require(proof.get('exit_code')==0 and proof.get('command') and
                sha(within(repo,proof['log']))==proof.get('log_sha256'),
                'Runtime selftest log missing/changed')
        receipt_path=within(repo,proof['verification_receipt'])
        require(sha(receipt_path)==proof.get('verification_sha256'),
                'Runtime selftest receipt missing/changed')
        receipt=read(receipt_path)
        require(receipt.get('source_manifest_sha256')==proof['runtime_manifest_sha256'] and
                receipt.get('passed') is True and receipt.get('decoder_validated') is True and
                receipt.get('rendered_video_decoded') is True and
                len(receipt.get('negative_fixtures',[]))>=3 and
                all(n.get('rejected') is True for n in receipt['negative_fixtures']),
                'Runtime selftest incomplete')
    return {'batch_id':batch['batch_id'],'results':results,'files':files,'package_sha256':digest(files),
            'verification':'Static contract only; explicitly run CPU tests before local adoption'}
