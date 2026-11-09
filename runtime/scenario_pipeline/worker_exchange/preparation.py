"""Standalone six-step return contract; no database, simulator or code execution."""
import ast
import shlex
from pathlib import Path
from .common import read, sha, tree, digest, within


def require(condition, message):
    if not condition:
        raise ValueError(message)


def selected_proposal_case_ids(proposal):
    """Neutral baselines define a comparison but are not delivery recordings."""
    return {case.get('case_id') for case in proposal['cases']
            if case.get('target_type') != 'baseline'}


def runtime_for(repo, batch):
    """Resolve the same source-hashed child runtime for worker and local checks."""
    import importlib.util
    repo = Path(repo).resolve()
    baseline = repo / batch['runtime']['root']
    pinned = batch['runtime'].get('source_manifest_sha256')
    if pinned and sha(baseline/'SOURCE-MANIFEST.json') != pinned:
        raise ValueError('Batch pinned runtime mismatch')
    overlay = repo / 'overlay.py'
    if not overlay.is_file() or not (repo / 'work/_shared/runtime-overlay/overlay.json').is_file():
        return baseline
    if sha(overlay) != batch['frozen_files'].get('overlay.py'):
        raise ValueError('Worker runtime resolver changed')
    spec = importlib.util.spec_from_file_location('_source_hashed_worker_overlay', overlay)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.ROOT.resolve() != repo:
        raise ValueError('Worker runtime resolver points to another repository')
    return module.effective_runtime()


def check(repo, complete=False, require_ready=False, assignment=None):
    repo = Path(repo)
    batch = read(repo/'batch.json')
    require(batch.get('format') == 'worker-batch' and batch.get('mode') == 'six_step_preparation', 'Wrong batch format/mode')
    require(1 <= batch.get('max_workers', 4) <= 8, 'Invalid worker count')
    for rel, checksum in batch['frozen_files'].items():
        require(sha(within(repo, rel)) == checksum, 'Changed frozen file: '+rel)
    if batch.get('reference_catalog'):
        catalog = read(within(repo, batch['reference_catalog']))
        require(catalog.get('format')=='worker-reference-catalog', 'Invalid reference catalog')
        for source in catalog['items']:
            require(sha(within(repo, source['path']))==source['sha256'], 'Changed source reference')
    allocated = set()
    memberships = set()
    partitions = [read(path) for path in sorted((repo/'partitions').glob('*.json'))]
    roles = {'demo-train': 'training', 'full-train': 'training',
             'demo-test': 'testing', 'full-test': 'testing', 'held-out': 'heldout'}
    for partition in partitions:
        target_set = partition.get('set_id')
        require(target_set in roles, 'Partition needs an active target set')
        for aid in partition['assignment_ids']:
            require((target_set, aid) not in memberships, 'Partition coverage/overlap')
            memberships.add((target_set, aid))
            allocated.add(aid)
            original = read(repo/'inputs'/aid/'assignment.json')
            require(original.get('role') == roles[target_set] and
                    original.get('local_snapshot',{}).get('scope_hashes',{}).get(target_set) == partition.get('scope_sha256'),
                    'Assignment does not match frozen target scope')
    require(allocated == set(batch['assignments']), 'Partition coverage/overlap')
    if batch.get('full_branch_coverage_required'):
        for filename in ('branch-sources.json', 'candidate-cells.json'):
            require((repo/'inputs/coverage'/filename).is_file(), 'Missing frozen coverage input: '+filename)
    from .branch_coverage import assignments, assignment_path
    items = assignments(repo, batch) if batch.get('full_branch_coverage_required') else batch['assignments']
    if assignment is not None:
        require(assignment in items, 'Unknown assignment: '+assignment)
    all_items = items
    files = tree(repo)
    returned=[rel for rel in files if rel.startswith('work/')]
    require(len(returned)<=batch.get('max_return_files',1000), 'Return contains too many generated files')
    forbidden={'.png','.jpg','.jpeg','.pkl','.mkv','.webm','.mp4','.ass','.lock','.uasset','.uexp'}
    for rel in returned:
        require(Path(rel).suffix.lower() not in forbidden, 'Generated binary/media belongs in ignored runtime work: '+rel)
        require(not any(part.startswith(('compatibility-','offline-')) for part in Path(rel).parts),
                'Generated diagnostic directory belongs in ignored runtime work: '+rel)
    for rel in files:
        if rel in batch['frozen_files'] or rel == 'batch.json':
            continue
        parts = Path(rel).parts
        require(len(parts)>2 and parts[0]=='work' and parts[1] in (*all_items, '_shared'), 'Unapproved output: '+rel)
        path = within(repo, rel)
        require(path.stat().st_size <= 2*1024*1024, 'Oversized return')
        from .portable import inspect_file
        inspect_file(path)
        if path.suffix == '.py':
            ast.parse(path.read_text())
    if assignment is not None:
        items = {assignment: items[assignment]}
    results, all_ids = {}, set()
    for aid, item in items.items():
        folder = repo/'work'/aid
        from .portable import validate_imports
        validate_imports(repo, aid)
        if not (folder/'result.json').exists():
            require(not complete, 'Missing result: '+aid)
            continue
        result, original = read(folder/'result.json'), read(assignment_path(repo,aid,item))
        require(result['assignment_id']==aid and result['input_sha256']==item['input_sha256'], 'Return identity/input mismatch')
        require(result['status'] in ('ready','partial','blocked'), 'Invalid return status')
        require(result.get('applied_update')==batch['update_version'], 'Unacknowledged current update')
        require((folder/'HANDOFF.md').is_file(), 'Missing handoff')
        require(result['status']=='ready' or result.get('reason'), 'Missing precise gap')
        if result['status']=='ready':
            require(isinstance(original.get('summary'),dict) and
                    original['summary'].get('id')==original['law_id'],
                    'Ready assignment needs its exact-law summary')
        plan = read(folder/'case-plan.json')
        require(plan['assignment_id']==aid and plan['actor']==original['actor'] and plan['cell_id']==original['cell_id'] and plan['law_id']==original['law_id'], 'Plan scope mismatch')
        for key in ('cases','comparisons','observations','sources','existing_evidence','runtime_uncertainties'):
            require(isinstance(plan.get(key),list), 'Missing/malformed plan '+key)
        require(plan['sources'] and plan['runtime_uncertainties'], 'Missing sources or explicit runtime limits')
        if result['status'] != 'ready' and (folder/'construction.json').is_file():
            draft = read(folder/'construction.json')
            for key in ('law_id', 'cell_id', 'actor'):
                require(key not in draft or draft[key] == original[key], 'Partial construction scope mismatch: '+key)
            for entry in draft.get('files', []):
                target = within(repo, entry['source']) if entry.get('source') else within(folder, entry['path'])
                if target.is_file() and 'content' in entry:
                    require(target.read_text() == entry['content'], 'Partial construction content mismatch: '+entry['path'])
        no_capture = result.get('readiness_kind') == 'existing_evidence'
        if result['status'] == 'ready':
            from .branch_coverage import validate_evidence
            validate_evidence(repo, aid, plan, no_capture)
        if (result['status']=='ready' and not no_capture) or plan.get('requirement_dispositions'):
            if original.get('branch'):
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
        if batch.get('full_branch_coverage_required') and result['status']=='ready' and not no_capture:
            require(all(d['status']=='selected_required' and d.get('case_ids') and set(d['case_ids']) <= ids for d in plan.get('requirement_dispositions',[])), 'Full branch ready plans cannot leave requirements pending or unassigned to cases')
        for comparison in plan['comparisons']:
            require(set(comparison.get('case_ids',[])) <= ids and len(comparison.get('case_ids',[]))>=2, 'Broken comparison members')
            require(comparison.get('deliberate_differences') and 'fixed_conditions' in comparison, 'Unspecified comparison isolation')
        if no_capture and result['status'] == 'ready':
            results[aid] = result
            continue
        if result['status']=='ready':
            command=result.get('first_gpu_delivery_command','')
            try:tokens=shlex.split(command)
            except ValueError:tokens=[]
            def argument(option):
                return tokens[tokens.index(option)+1] if option in tokens and tokens.index(option)+1<len(tokens) else None
            require('execute-delivery' in tokens and
                    argument('--python')=='$CARLA_PYTHON' and
                    argument('--host')=='$CARLA_HOST' and
                    argument('--port')=='$CARLA_PORT' and
                    argument('--case') in ids and
                    argument('--job')=='$JOB_ID' and
                    argument('--db')=='$DB' and
                    argument('--run')=='$RUN' and
                    argument('--assignment')==aid,
                    'First GPU command must dispatch one canonical exact job')
            require(batch.get('runtime'), 'Executable package needs the pinned runtime')
            if result['status']=='ready' and result.get('readiness_kind') != 'delivery_prepared':
                raise ValueError('Delivery return must declare delivery_prepared readiness')
            from .execution_manifest import validate as validate_execution_manifest
            executable=validate_execution_manifest(repo,aid)
            from .semantic_delivery import validate as validate_semantic_delivery
            validate_semantic_delivery(folder,original,executable)
            from .delivery_handoff import validate_case as validate_delivery_case
            for delivery_entry in executable['cases']:
                validate_delivery_case(folder,delivery_entry,original.get('selection_targets'))
            from .package_compatibility import check_receipts
            check_receipts(repo,folder,executable)
            require(plan['cases'] and plan['observations'], 'Ready with no cases/observations')
            for filename in ('runner.py','config.json','construction.json','proposals/cases.json'):
                require((folder/filename).is_file(), 'Missing executable artifact '+filename)
            construction = read(folder/'construction.json')
            from .identity_preflight import validate as validate_identity
            validate_identity(construction, original['law_id'], original['cell_id'])
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
            require(selected_proposal_case_ids(proposal)==ids, 'Proposal/plan case coverage mismatch')
            for case in proposal['cases']:
                for key in ('target_law_id','target_type','rationale','variable_assignments','unresolved_judgment_calls','recording_description'):
                    require(key in case, 'Missing canonical case field '+key)
            config = read(folder/'config.json')
            if result['status']=='ready':
                from .capture import PROFILE
                camera_plan = plan.get('camera_plan')
                require(isinstance(camera_plan, dict) and
                        camera_plan.get('profile') == PROFILE['version'] and
                        camera_plan.get('duration_s') == config.get('duration_s') and
                        isinstance(camera_plan.get('coverage'), list) and camera_plan['coverage'],
                        'Missing exact camera and duration plan')
                names = ('overview', 'approach', 'reference_corner', 'driver_reference')
                sizes = [PROFILE['overview'], *PROFILE['detail_views']]
                cameras = config.get('cameras')
                require(isinstance(cameras, list) and len(cameras) == 4 and
                        [(c.get('name'), c.get('width'), c.get('height')) for c in cameras] ==
                        [(name, *size) for name, size in zip(names, sizes)] and
                        all(c.get('pose_strategy') and c.get('fov_deg') for c in cameras),
                        'Four-view capture configuration differs from profile')
                require({c.get('view') for c in camera_plan['coverage']} <= set(names) and
                        all(c.get('subject') and c.get('interval') and c.get('view') for c in camera_plan['coverage']),
                        'Camera coverage plan lacks subjects, views or intervals')
                require(camera_plan.get('composition') == 'synchronized_four_view_primary',
                        'Four-view capture needs synchronized primary composition')
            if batch.get('runtime'):
                from .atom_preflight import check_required_atoms
                check_required_atoms(runtime_for(repo,batch), config.get('required_atoms', []), config.get('source_packets', []), config)
            require(config.get('actor')==original['actor'] and config.get('law_id')==original['law_id'], 'Wrong config identity')
            require(set(config.get('supported_case_ids',[]))==ids, 'Configuration does not cover cases')
            channels = {c['name'] for c in construction['recording_description']['channels']}
            if result['status']=='ready' or original.get('source_observation_terms'):
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
    all_ready = len(results)==len(items) and all(r['status']=='ready' for r in results.values())
    if assignment is None and complete and all_ready and batch.get('full_branch_coverage_required'):
        from .branch_coverage import validate as validate_branches
        validate_branches(repo,batch,items,require_ready)
    if assignment is None and complete and items and all_ready:
        from .delivery_handoff import validate_queue
        capture_items = {aid: item for aid, item in items.items() if results[aid].get('readiness_kind') != 'existing_evidence'}
        if capture_items:
            validate_queue(repo,capture_items)
    if require_ready:
        require(len(results)==len(items) and all(r['status']=='ready' for r in results.values()), 'Preparation acceptance failed: partial/missing packages remain')
    return {'batch_id':batch['batch_id'],'results':results,'files':files,'package_sha256':digest(files),
            'verification':'Static contract only; explicitly run CPU tests before local adoption'}
