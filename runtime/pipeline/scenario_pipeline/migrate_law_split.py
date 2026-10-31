"""Stage/apply an approved law split without replaying or relabeling captures."""
from collections import Counter, defaultdict
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import time

from batch_pipeline.store import atomic
from pipeline_paths import OUTPUT_ROOT, PROJECT_ROOT
from recording_store import identity, locked, sha

SETS=('demo-train','demo-test','full-train','full-test','held-out')
CORPUS='repo_prep/nevada_sydney/pipeline/traffic-spec-agent/laws'
DEFAULT_POLICY=Path(__file__).parent/'data/law_splits/demo-overlap-v3.json'


def packed(value):return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
def digest_bytes(value):return hashlib.sha256(value).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def records(path):return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def assert_idle(root):
    for path in (root/'state').glob('*.sqlite'):
        db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=5)
        try:
            tables={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'jobs' in tables and db.execute("SELECT 1 FROM jobs WHERE status='running' AND lease_until>? LIMIT 1",(time.time(),)).fetchone():
                raise ValueError('Active job: '+str(path))
            if 'resource_leases' in tables and db.execute("SELECT 1 FROM resource_leases WHERE owner!='unavailable' AND expires>? LIMIT 1",(time.time(),)).fetchone():
                raise ValueError('Active lease: '+str(path))
        finally:db.close()


def build_plan(root,project,policy_path=DEFAULT_POLICY):
    root=Path(root).resolve();project=Path(project).resolve();policy=read(policy_path)
    version=policy['version'];package=root/'inputs/planning'/('law-split-'+version)
    corpus=project/CORPUS
    inputs={};desired={};artifacts={};snapshots={}
    def consume(path):
        path=Path(path);data=path.read_bytes();inputs[str(path)]=digest_bytes(data);return data
    for rel,expected in policy['baseline_corpus_sha256'].items():
        if digest_bytes(consume(project/rel))!=expected:raise ValueError('Corpus proposal baseline changed: '+rel)
    if sha(corpus/'full_list/laws.jsonl')!=policy['baseline_full_list_sha256']:raise ValueError('Full corpus changed')
    for rel,expected in policy['baseline_planning_sources'].items():
        if digest_bytes(consume(root/rel))!=expected:raise ValueError('Reviewed mapping source changed: '+rel)
    baseline={s:records(corpus/'example'/s/'laws.jsonl') for s in ('train','test','demo')}
    raw={r['id']:line for s in ('train','test') for line in (corpus/'example'/s/'laws.jsonl').read_text().splitlines(keepends=True) if line.strip() for r in [json.loads(line)]}
    laws={r['id']:r for s in ('train','test') for r in baseline[s]}
    old_train={r['id'] for r in baseline['train']};old_held={r['id'] for r in baseline['test']}
    held=set(policy['approved_heldout_ids']);train=set(laws)-held;demo=set(policy['protected_demo_ids'])
    constraints=policy['constraints']
    if len(train)!=constraints['training_laws'] or len(held)!=constraints['heldout_laws'] or len(laws)!=constraints['total_laws']:
        raise ValueError('Wrong corpus cardinality')
    if not demo<=train or {r['id'] for r in baseline['demo']}!=demo:raise ValueError('Protected demo changed')
    protected={str(corpus/'example/demo/laws.jsonl'):sha(corpus/'example/demo/laws.jsonl')}
    demo_defs=corpus/'example/demo/definitions.jsonl'
    if demo_defs.exists():
        if policy.get('protected_demo_definitions_sha256') and sha(demo_defs)!=policy['protected_demo_definitions_sha256']:raise ValueError('Demo definitions changed')
        protected[str(demo_defs)]=sha(demo_defs)
    catalog=root/'inputs/catalog/vocabulary_catalog.json'
    protected[str(catalog)]=sha(catalog)
    scopes={};selections={}
    for set_id in SETS:
        for filename in ('scope.json','selection.json'):
            path=root/'sets'/set_id/filename;data=consume(path)
            snapshots['sets/'+set_id+'/'+filename]=data
            (scopes if filename=='scope.json' else selections)[set_id]=json.loads(data)
            if set_id.startswith('demo-'):protected[str(path)]=digest_bytes(data)
        if (root/'sets'/set_id/'completion.json').exists():raise ValueError('Finalized set requires a new set name: '+set_id)
    for path in (root/'sets/index.json',root/'work/index.json'):
        consume(path);snapshots[str(path.relative_to(root))]=path.read_bytes()
    for set_id in ('demo-train','demo-test'):
        parent='full-train' if set_id=='demo-train' else 'full-test'
        if not all(m in selections[parent]['members'] for m in selections[set_id]['members']):raise ValueError('Full set lost demo membership')
    new_train_order=[r['id'] for r in baseline['train'] if r['id'] in train]+[r['id'] for r in baseline['test'] if r['id'] in train]
    new_held_order=[r['id'] for r in baseline['test'] if r['id'] in held]+[r['id'] for r in baseline['train'] if r['id'] in held]
    desired[corpus/'example/train/laws.jsonl']=''.join(raw[x] for x in new_train_order).encode()
    desired[corpus/'example/test/laws.jsonl']=''.join(raw[x] for x in new_held_order).encode()
    # Promoted bus, roundabout and headlamp laws need their existing definitions.
    defs=corpus/'example/train/definitions.jsonl';held_defs=corpus/'example/test/definitions.jsonl'
    if defs.exists() and held_defs.exists():
        current=consume(defs);extra=consume(held_defs);seen={r['id'] for r in records(defs)}
        lines=[line for line in extra.decode().splitlines(keepends=True) if line.strip() and json.loads(line)['id'] not in seen]
        desired[defs]=current+(b'\n' if current and not current.endswith(b'\n') else b'')+''.join(lines).encode()
    source_members=[]
    for set_id in ('full-train','full-test','held-out'):
        for member in selections[set_id]['members']:source_members.append((set_id,member))
    members={x:[] for x in ('full-train','full-test','held-out')};migrations=[];excluded=[];metas={}
    for source_set,source in source_members:
        law=source['law_id']
        if law not in laws or (source_set=='held-out' and law in demo):
            excluded.append({'source_set':source_set,'member':source,'reason':'outside_core_corpus' if law not in laws else 'protected_demo_historical_heldout'})
            continue
        target='held-out' if law in held else ('full-test' if source_set=='full-test' else 'full-train')
        target_split={'held-out':'heldout','full-test':'testing','full-train':'training'}[target]
        member=dict(source)
        if member.get('recording_id') and member.get('status')=='accepted':
            rid=member['recording_id'];folder=root/'recordings'/rid
            metas.setdefault(rid,read(folder/'metadata.json'))
            for name in ('video.webm','trace.json'):
                if not (folder/name).is_file():raise ValueError('Missing pair: '+rid)
            if metas[rid]['status']!='accepted':raise ValueError('Source recording is not accepted')
        if source['split']!=target_split:
            if not member.get('recording_id'):raise ValueError('Moved selection has no stable recording/attempt identity')
            meta=metas.get(member['recording_id'],{})
            before=package/'before/sets'/source_set/'selection.json'
            proof={'version':version,'source_set':source_set,'source_member':source,
                   'source_selection':str(before.relative_to(root)),'source_selection_sha256':inputs[str(root/'sets'/source_set/'selection.json')],
                   'target_split':target_split,'target_identity':{k:source.get(k) for k in ('recording_id','law_id','cell_id','actor','case_id','campaign')},
                   'law_record_sha256':identity(laws[law]),'video_sha256':meta.get('video_sha256'),'trace_sha256':meta.get('trace_sha256')}
            data=packed(proof);sha_=digest_bytes(data);path=package/'receipts'/('membership-'+sha_+'.json')
            artifacts[path]=data;migrations.append(sha_)
            member.pop('historical_split_exception',None)
            member['split']=target_split
            member['partition_migration_receipt']={'path':str(path.relative_to(root)),'sha256':sha_}
            member['split_provenance']={'version':version,'reason':'Approved law-corpus repartition; capture-time metadata preserved'}
        members[target].append(member)
    # All existing reviewed witnesses follow their LAW, never whole-cell ownership.
    assignments={x:[] for x in members}
    for source_set in assignments:
        for old in scopes[source_set]['assignments']:
            law=old['law_id'];target='held-out' if law in held else ('full-test' if source_set=='full-test' else 'full-train')
            item=dict(old,law_partition='heldout' if law in held else 'training',scenario_partition={'full-train':'training','full-test':'testing','held-out':'heldout'}[target],origin_role=scopes[source_set]['split'])
            if target!=source_set:item['partition_migration_version']=version
            if law in laws:assignments[target].append(item)
    reviews={r['law_id']:r for r in policy['testing_reviews']}
    promoted=old_held-held
    if set(reviews)!=promoted:raise ValueError('Every promoted law needs a reviewed testing witness')
    cell_rows={c['cell_id']:c for c in read(catalog)['cells']}
    actor_reviews=read(root/'inputs/planning/focused-coverage-20261016-v1/selected-actor-reviews.json')
    candidates=read(root/'inputs/planning/focused-coverage-20261016-v1/candidates.json')
    for law in sorted(promoted):
        review=reviews[law];cell=cell_rows[review['testing_cell']]
        if review['verdict']!='accept_conditional' or review['quote']!=laws[law]['text']:raise ValueError('Invalid testing review: '+law)
        if {k:cell[k] for k in review['fixed_facts']}!=review['fixed_facts']:raise ValueError('Testing cell facts changed')
        available=set(cell.get('grounding_by_party',{}))|set(cell.get('candidate_ego_parties',[]))|set(actor_reviews.get(cell['cell_id'],{}).get('available_actors',[]))
        if review['actor'] not in available:raise ValueError('Unreviewed actor')
        if not any(identity(c)==review['candidate_sha256'] for c in candidates if c['law']==law and c['cell']==cell['cell_id'] and c['actor']==review['actor']):raise ValueError('Candidate provenance changed')
        training_cells={a['cell_id'] for a in assignments['full-train'] if a['law_id']==law}|{m['cell_id'] for m in members['full-train'] if m['law_id']==law}
        if cell['cell_id'] in training_cells:raise ValueError('Testing cell already supplies training evidence: '+law)
        path=package/'reviews'/(law+'.json');artifacts[path]=packed(review)
        assignments['full-test'].append({'law_id':law,'cell_id':cell['cell_id'],'actor':review['actor'],'branch':review['branch'],
            'source':str(path.relative_to(root)),'source_sha256':digest_bytes(artifacts[path]),'coverage_status':'pending_recording',
            'relevance_review':'accept_conditional','physical_feasibility':'unverified','required_context':review['required_context'],
            'law_partition':'training','scenario_partition':'testing','origin_role':'new_testing_witness','recording_ids':[]})
    for set_id in members:
        # Imported accepted cases may be additional reviewed finite constructions,
        # distinct from the original law-first representative witness.
        for m in members[set_id]:
            key=(m['law_id'],m['cell_id'],m['actor'])
            if not any((a['law_id'],a['cell_id'],a['actor'])==key for a in assignments[set_id]):
                assignments[set_id].append({'law_id':key[0],'cell_id':key[1],'actor':key[2],'source':'preserved_accepted_membership',
                    'coverage_status':'pending_current_requirement_review','law_partition':'heldout' if set_id=='held-out' else 'training',
                    'scenario_partition':{'held-out':'heldout','full-train':'training','full-test':'testing'}[set_id],'recording_ids':[]})
        scope=dict(scopes[set_id]);scope.update(source_version=version,law_split_version=version,law_ids=sorted(held if set_id=='held-out' else train),
            assignments=assignments[set_id],reviewed_coverage_complete=False,historical_split_exceptions=[],ownership_policy='law_cell_actor_assignment')
        scope['recorded_law_ids']=sorted({m['law_id'] for m in members[set_id]})
        scope['historical_laws_outside_planned_scope']=[]
        scope['scope_cell_ids']=sorted({a['cell_id'] for a in assignments[set_id]})
        scope['precomputed_cell_ids']=scope['scope_cell_ids']
        split={'full-train':'training','full-test':'testing','held-out':'heldout'}[set_id]
        scope['precomputed_cells_source']=str((package/(split+'-cells.json')).relative_to(root))
        scope['cells_without_reviewed_assignments']=[]
        for a in assignments[set_id]:
            a['recording_ids']=sorted({m['recording_id'] for m in members[set_id] if m.get('status')=='accepted' and (m['law_id'],m['cell_id'],m['actor'])==(a['law_id'],a['cell_id'],a['actor'])})
        desired[root/'sets'/set_id/'scope.json']=packed(scope)
        selection=dict(selections[set_id]);selection.update(frozen=True,members=members[set_id],scope_sha256=identity(scope),source_version=version,law_split_version=version,reviewed_coverage_complete=False)
        desired[root/'sets'/set_id/'selection.json']=packed(selection)
        artifacts[package/(split+'-cells.json')]=packed(scope['scope_cell_ids'])
    for law in train:
        tr={a['cell_id'] for a in assignments['full-train'] if a['law_id']==law}
        te={a['cell_id'] for a in assignments['full-test'] if a['law_id']==law}
        if not tr or not te or tr&te:raise ValueError('Missing or overlapping per-law train/test witnesses: '+law)
    occupancy=defaultdict(lambda:defaultdict(set))
    for set_id,items in assignments.items():
        for a in items:occupancy[a['cell_id']][set_id].add(a['law_id'])
    overlaps=[{'cell_id':cell,'assignments':{k:sorted(v) for k,v in roles.items()}} for cell,roles in sorted(occupancy.items()) if len(roles)>1]
    artifacts[package/'law-cell-assignments.json']=packed(assignments)
    artifacts[package/'overlaps.json']=packed(overlaps)
    artifacts[package/'excluded-active-memberships.json']=packed(excluded)
    for rel,data in snapshots.items():artifacts[package/'before'/rel]=data
    for path in list(desired):
        if str(path) not in inputs:consume(path)
        backup=package/'before/project'/path.relative_to(project)
        artifacts[backup]=path.read_bytes()
    artifacts[package/'policy.json']=packed(policy)
    manifest={'version':version,'training_law_ids':sorted(train),'heldout_law_ids':sorted(held),'protected_demo_ids':sorted(demo),
              'membership_migrations':sorted(migrations),'ownership':'law_cell_actor_assignment','cell_disjoint':False,
              'source_hashes':inputs,'protected_hashes':protected,'policy_sha256':digest_bytes(packed(policy)),
              'law_record_sha256':{law:identity(record) for law,record in laws.items()},'assignments':'law-cell-assignments.json',
              'new_testing_reviews':len(reviews),'native_executions':0}
    manifest_path=package/'manifest.json';artifacts[manifest_path]=packed(manifest)
    index=read(root/'sets/index.json');index.update(law_split_manifest=str(manifest_path.relative_to(root)),law_split_manifest_sha256=digest_bytes(artifacts[manifest_path]),
        law_split_version=version,cell_disjoint=False,ownership='law_cell_actor_assignment',overlap_report=str((package/'overlaps.json').relative_to(root)))
    index['historical_overlap_recordings_v1']=index.pop('historical_overlap_recordings',0)
    index['sources']={'law_split_manifest':str(manifest_path.relative_to(root)),'sha256':index['law_split_manifest_sha256']}
    desired[root/'sets/index.json']=packed(index)
    planning_pointer=root/'inputs/planning/current.json'
    if planning_pointer.exists():
        pointer=json.loads(consume(planning_pointer));artifacts[package/'before/planning-current.json']=planning_pointer.read_bytes()
        pointer.update(law_split_manifest=index['law_split_manifest'],law_split_version=version,active_assignment_policy='law_cell_actor_assignment')
        desired[planning_pointer]=packed(pointer)
    summary={'version':version,'training_laws':len(train),'heldout_laws':len(held),'moved_to_heldout':sorted(held-old_held),'moved_to_training':sorted(promoted),
        'members':{k:len(v) for k,v in members.items()},'accepted_pairs':{k:sum(m['status']=='accepted' for m in v) for k,v in members.items()},'membership_migrations':len(migrations),'new_testing_reviews':len(reviews),
        'recovery_pairs':sum(e['reason']=='outside_core_corpus' for e in excluded),'historical_demo_heldout_pairs':sum(e['reason']=='protected_demo_historical_heldout' for e in excluded),
        'overlap_cells':len(overlaps),'demo_unchanged':True,'native_executions':0}
    return {'root':root,'project':project,'package':package,'desired':desired,'artifacts':artifacts,'inputs':inputs,'protected':protected,'summary':summary}


def recover_transaction(root):
    path=root/'state/law-split-transaction.json'
    if not path.exists():return
    tx=read(path)
    if tx['status']!='applying':return
    for item in tx['changes']:
        target=Path(item['target']);backup=Path(item['backup'])
        if sha(target) not in (item['before_sha256'],item['after_sha256']):raise ValueError('Concurrent edit prevents rollback: '+str(target))
        if sha(backup)!=item['before_sha256']:raise ValueError('Rollback backup changed')
        target.write_bytes(backup.read_bytes())
    backup=Path(tx['navigation_backup'])
    if sha(backup)!=tx['navigation_sha256']:raise ValueError('Navigation rollback backup changed')
    (root/'work/index.json').write_bytes(backup.read_bytes())
    tx['status']='rolled_back';atomic(path,tx)
    from organize_work import render_navigation
    render_navigation(root,read(root/'work/index.json'),{s:read(root/'sets'/s/'selection.json')['members'] for s in SETS})


def migrate(root=None,project=None,policy_path=DEFAULT_POLICY,*,apply=False):
    root=(Path(root) if root is not None else OUTPUT_ROOT).resolve();project=(Path(project) if project is not None else PROJECT_ROOT).resolve()
    if read(policy_path)['version']=='demo-overlap-v3':
        from law_split import active_manifest
        current=active_manifest(root)
        if not current or current['version']!='demo-overlap-v3':
            raise ValueError('Current v3 assignments have not been activated; refusing historical roster migration')
        for key in ('training_law_ids','heldout_law_ids'):
            if set(current[key])!=set(read(policy_path)[key]):
                raise ValueError('Active roster differs: '+key)
        from lean_work import verify
        report=verify(root,root/'work',read(root/'work/index.json'))
        return dict(version=current['version'],mode='verify',verification=report)
    with ExitStack() as stack:
        if apply:
            for name in ('runtime-edit','law-split-migration','set-organization','workspace-navigation'):
                stack.enter_context(locked(root/'state'/(name+'.lock')))
            for set_id in SETS:stack.enter_context(locked(root/'state'/('set-'+set_id+'.lock')))
            recover_transaction(root)
        from law_split import active_manifest
        current=active_manifest(root)
        if current and current['version']==read(policy_path)['version']:
            if current['policy_sha256']!=digest_bytes(packed(read(policy_path))):raise ValueError('Active policy changed; create a new version')
            receipt=read(root/'state/law-split-migration.json')
            # Live selections/navigation may advance after cutover. Validate the
            # frozen migration artifacts and corpus, never restore a stale set.
            immutable=dict(receipt['artifact_hashes'])
            immutable.update((name,digest) for name,digest in receipt['active_hashes'].items()
                             if root not in Path(name).parents)
            for name,digest in immutable.items():
                if sha(Path(name))!=digest:raise ValueError('Frozen migration output changed; create a new version: '+name)
            return receipt
        assert_idle(root)
        plan=build_plan(root,project,policy_path)
        if not apply:return dict(plan['summary'],mode='dry-run')
        # Recovery review operates on saved evidence only and precedes cutover.
        from recover_core_evidence import audit_recovery
        recovery=audit_recovery(root,plan['package'],set(read(policy_path)['approved_heldout_ids']),{r['id'] for r in records(project/CORPUS/'full_list/laws.jsonl')})
        plan['artifacts'][plan['package']/'recovery-summary.json']=packed(recovery)
        plan['artifacts'][plan['package']/'recovery-inventory.json']=(plan['package']/'recovery-inventory.json').read_bytes()
        for path,data in plan['artifacts'].items():
            path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists() and path.read_bytes()!=data:raise ValueError('Immutable staged artifact differs: '+str(path))
            if not path.exists():path.write_bytes(data)
        for path,expected in plan['inputs'].items():
            if sha(path)!=expected:raise ValueError('Input changed before cutover: '+path)
        assert_idle(root)
        changes=[]
        for path,data in plan['desired'].items():
            backup=plan['package']/'transaction-before'/path.relative_to(project)
            backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(path.read_bytes())
            changes.append({'target':str(path),'backup':str(backup),'before_sha256':sha(path),'after_sha256':digest_bytes(data)})
        tx={'status':'applying','version':plan['summary']['version'],'changes':changes,
            'navigation_backup':str(plan['package']/'before/work/index.json'),'navigation_sha256':plan['inputs'][str(root/'work/index.json')]}
        atomic(root/'state/law-split-transaction.json',tx)
        try:
            # The set index is the final activation pointer.
            for path,data in plan['desired'].items():
                if path==root/'sets/index.json':continue
                temp=path.with_name(path.name+'.law-split-tmp');temp.write_bytes(data);temp.replace(path)
            pointer=root/'sets/index.json';temp=pointer.with_name('index.json.law-split-tmp');temp.write_bytes(plan['desired'][pointer]);temp.replace(pointer)
            # Protect demo data and original catalog, including concurrent progress.
            for path,expected in plan['protected'].items():
                if sha(path)!=expected:raise ValueError('Protected demo/catalog changed: '+path)
            from organize_work import refresh_workspaces
            refresh_workspaces(root,_lock_held=True)
            tx['status']='complete';atomic(root/'state/law-split-transaction.json',tx)
        except BaseException:
            recover_transaction(root)
            raise
        from organize_work import refresh_workspaces
        # Release the navigation lock before the public refresh helper takes it.
        # All other migration/runtime/set locks remain owned until this returns.
        # Navigation uses current set metadata and never changes recording bytes.
        receipt=dict(plan['summary'],completed=True,mode='apply',recovery=recovery,
            manifest=str((plan['package']/'manifest.json').relative_to(root)),
            active_hashes={str(path):sha(path) for path in plan['desired']},protected_hashes=plan['protected'],
            artifact_hashes={str(path):sha(path) for path in plan['artifacts']})
        atomic(root/'state/law-split-migration.json',receipt)
        return receipt
