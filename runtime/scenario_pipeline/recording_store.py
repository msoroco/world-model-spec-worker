"""Canonical recording storage and metadata-only, end-of-set finalization."""
import csv
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import zipfile
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor

from batch_pipeline.store import atomic
from pipeline_paths import OUTPUT_ROOT, require_artifact_path

TERMINAL = {'accepted', 'failed', 'unsupported', 'unselected'}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def recording_path(run, job, attempt, root=None):
    root = Path(root) if root is not None else OUTPUT_ROOT
    if int(attempt)<1:raise ValueError('Attempt number must be positive')
    return root / 'recordings' / identity({'campaign': run, 'job': int(job), 'attempt': int(attempt)})


def attempt_path(run, job, attempt, root=None):
    return recording_path(run, job, attempt, root) / 'evidence'


def stored_attempt_path(store, job_id, attempt):
    """Operational location belongs to the attempt, never an immutable artifact."""
    row = store.db.execute('SELECT metadata FROM attempts WHERE job_id=? AND number=?',
                           (job_id, attempt)).fetchone()
    if not row or not row[0]:
        raise ValueError('Attempt has no registered location')
    return Path(json.loads(row[0])['directory'])


def safe_name(value):
    if not isinstance(value, str) or not value or value in ('.', '..') or Path(value).name != value or '\\' in value:
        raise ValueError('Expected a single nonempty name')
    return value


@contextmanager
def locked(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def begin_recording(run, job, attempt, cell, actor, case, root=None):
    folder = recording_path(run, job, attempt, root)
    (folder / 'evidence').mkdir(parents=True, exist_ok=False)
    atomic(folder / 'metadata.json', {'recording_id': folder.name, 'campaign': run,
           'job_id': int(job), 'attempt': int(attempt), 'cell_id': cell, 'actor': actor,
           'case_id': case, 'status': 'recording', 'phases': {'execution': {'started': time.time()}}})
    return folder / 'evidence'


def finish_phase(directory, status):
    folder = Path(directory).parent
    path = folder / 'metadata.json'
    if not path.exists():
        raise ValueError('Missing canonical recording metadata: ' + str(path))
    value = json.loads(path.read_text())
    value['status'] = status
    value['phases'].setdefault('execution', {})['ended'] = time.time()
    atomic(path, value)


def record_phase(directory, name, started, status):
    path=Path(directory).parent/'metadata.json'
    value=json.loads(path.read_text())
    value.setdefault('phases',{})[name]={'started':started,'ended':time.time(),'status':status}
    atomic(path,value)


@contextmanager
def timed_phase(directory, name):
    started=time.time();status='failed'
    try:
        yield
        status='passed'
    finally:
        record_phase(directory,name,started,status)


def accept_recording(directory, record):
    """Called after the existing full case acceptance, never instead of it."""
    folder = Path(directory).parent
    path = folder / 'metadata.json'
    value = json.loads(path.read_text())
    started = time.time()
    for name, key in [('video.webm', 'video'), ('trace.json', 'trace')]:
        source = Path(record[key + '_source']).resolve()
        if folder.resolve() not in source.parents:
            raise ValueError('Accepted output must belong to its canonical recording')
        expected = record[key + '_sha256']
        if sha(source) != expected:
            raise ValueError('Accepted output changed: ' + str(source))
        if key == 'trace':
            from traffic_spec_adapter.roadways import validate_map
            from trace_json import scenes
            report_path=source.parent/'adapter_report.json'
            report=json.loads(report_path.read_text()) if report_path.is_file() else {}
            # Normal exports already check every map during full validation.
            # Imports without that hash-bound receipt use the same cached check.
            if report.get('roadway_check_trace_sha256') != expected:
                for scene,_ in scenes(source):
                    validate_map(scene.get('structures',[]))
        target = folder / name
        if target.exists():
            if sha(target) != expected:
                raise ValueError('Cannot replace accepted recording output')
        else:
            os.link(source, target)
    value.update(status='accepted', law_id=record.get('law_id'), frames=record['frames'],
                 video_sha256=record['video_sha256'], trace_sha256=record['trace_sha256'])
    value['acceptance'] = json.loads(json.dumps(record, default=str))
    value.setdefault('phases', {})['registration'] = {'started': started, 'ended': time.time()}
    from shared_manifest import canonical_path, link as link_manifest, link_sets
    collection = folder.parent.parent
    if canonical_path(collection).is_file():
        link_sets(collection)
        source_manifest=Path(record['trace_source']).parent/'manifest.json'
        capability=json.loads(source_manifest.read_text()) if source_manifest.is_file() else None
        link_manifest(collection, folder, capability)
        value['manifest_sha256'] = sha(folder/'manifest.json')
    atomic(path, value)
    return folder.name


def verify_recording(folder):
    folder = Path(folder)
    value = json.loads((folder / 'metadata.json').read_text())
    if value.get('status') != 'accepted':
        raise ValueError('Recording is not accepted: ' + folder.name)
    if value.get('manifest_sha256'):
        capability=folder/'manifest.json'
        if not capability.is_file() or sha(capability)!=value['manifest_sha256']:
            raise ValueError('Recording capability manifest differs: '+folder.name)

    for name, key in [('video.webm', 'video_sha256'), ('trace.json', 'trace_sha256')]:
        if not value.get(key) or sha(folder / name) != value[key]:
            raise ValueError('Recording changed: ' + str(folder / name))
    if value.get('reconstruction'):
        receipt=value['reconstruction'];report_path=folder.parent.parent/receipt['report']
        if sha(report_path)!=receipt['report_sha256']:raise ValueError('Reconstruction report changed')
        reconstruction=json.loads(report_path.read_text())['reconstruction']
        if reconstruction['output_trace_sha256']!=value['trace_sha256'] or not reconstruction['decoder_passed']:
            raise ValueError('Reconstruction receipt does not validate this trace')
        origin=Path(reconstruction['evidence_origin'])
        for name,expected in reconstruction.get('evidence_used',{}).items():
            if sha(origin/name)!=expected:raise ValueError('Reconstruction source changed: '+name)
    if value.get('trace_migration'):
        from trace_derivations import verify_trace_origin
        verify_trace_origin(folder,value,value['trace_migration']['original_trace_sha256'],folder.parent.parent)
    if value.get('intention_validation'):
        from trace_derivations import inside
        root=folder.parent.parent.resolve();reference=value['intention_validation']
        receipt_path=inside(root,reference['receipt'])
        if sha(receipt_path)!=reference['receipt_sha256']:raise ValueError('Intention validation receipt changed')
        receipt=json.loads(receipt_path.read_text())
        if receipt['recording_id']!=folder.name or receipt['trace_sha256']!=value['trace_sha256']:
            raise ValueError('Intention validation is bound to another trace')
        report=receipt['validation_report'];report_path=inside(root,report['path'])
        if sha(report_path)!=report['sha256']:raise ValueError('Intention validation report changed')
        proof=json.loads(report_path.read_text())
        if not proof.get('passed') or sha(proof['validator'])!=proof['validator_sha256']:
            raise ValueError('Intention validator proof changed')
        for batch in proof['batches']:
            if sha(inside(root,batch['path']))!=batch['sha256']:raise ValueError('Intention validation view changed')
    # Migration manifests bind every unique evidence file, including frozen receipts.
    inventory = folder / 'evidence-checksums.json'
    if inventory.exists():
        base=folder.resolve()
        def check(item):
            name,expected=item
            path=(base/name).resolve()
            if base not in path.parents:
                # Capabilities are deliberately shared; only the canonical,
                # relative manifest link may leave the recording directory.
                from shared_manifest import canonical_path,verify as verify_manifest
                collection=folder.parent.parent
                if name in ('manifest.json','evidence/traffic_spec/manifest.json'):
                    verify_manifest(collection,(base/name).parent,expected)
                    return
                raise ValueError('Evidence changed: '+str(path))
            if sha(path)!=expected:raise ValueError('Evidence changed: '+str(path))
        # Independent immutable files; bounded buffers, no model or simulator work.
        with ThreadPoolExecutor(max_workers=4) as pool:
            for _ in pool.map(check,json.loads(inventory.read_text()).items()):pass
    else:
        from batch_pipeline.completion import verify
        result = json.loads((folder / 'evidence/result.json').read_text())
        verify(folder / 'evidence', result['completion']['binding'])
    return value


def finalize_set(set_id, root=None):
    root = Path(root) if root is not None else OUTPUT_ROOT
    directory = root / 'sets' / safe_name(set_id)
    with locked(root / 'state' / ('set-' + set_id + '.lock')):
        selection = json.loads((directory / 'selection.json').read_text())
        members = selection.get('members', [])
        if not members or not selection.get('frozen'):
            raise ValueError('A nonempty frozen selection is required')
        scope = None
        if selection.get('scope_sha256'):
            scope = json.loads((directory / 'scope.json').read_text())
            if identity(scope) != selection['scope_sha256']:
                raise ValueError('Frozen set scope changed')
        from shared_manifest import canonical_path, link as link_manifest
        acquisition = canonical_path(root)
        if acquisition.is_file() and any(m.get('split') != 'heldout' for m in members):
            link_manifest(root, directory)
        selection_hash = identity(selection)
        receipt = directory / 'completion.json'
        if receipt.exists():
            old = json.loads(receipt.read_text())
            if old['selection_sha256'] != selection_hash:
                raise ValueError('Finalized selection changed; create a new set version')
            for name, expected in old['metadata_sha256'].items():
                if sha(directory / name) != expected:
                    raise ValueError('Finalized metadata changed')
            return old
        started = time.time()
        rows = []
        recordings = {}
        seen = set()
        for member in members:
            key = tuple(member.get(k) for k in ('campaign', 'cell_id', 'actor', 'case_id', 'law_id', 'comparison'))
            if key in seen:
                raise ValueError('Duplicate selected membership')
            seen.add(key)
            status = member.get('status')
            if status not in TERMINAL:
                raise ValueError('Selected member still pending/running: ' + str(key))
            if member.get('split') not in ('training', 'testing', 'heldout'):
                raise ValueError('Every member requires an explicit split')
            row = dict(member)
            if status == 'accepted':
                rid = safe_name(member['recording_id'])
                if rid not in recordings:
                    verified=verify_recording(root / 'recordings' / rid)
                    recordings[rid]={k:verified.get(k) for k in ('cell_id','actor','case_id','split','video_sha256','trace_sha256')}
                    recordings[rid]['law_id']=verified.get('law_id') or verified.get('published_record',{}).get('law_id')
                meta = recordings[rid]
                from law_split import validate_partition_migration, law_partition
                migrated=validate_partition_migration(member,meta,root)
                partition=law_partition(member.get('law_id'),root)
                if partition and partition!=('heldout' if member['split']=='heldout' else 'training'):
                    raise ValueError('Membership conflicts with active law partition')
                if meta.get('split') in ('training','testing','heldout') and meta['split']!=member['split'] and not migrated:
                    raise ValueError('Recording split cannot be relabeled')
                declared_law=meta.get('law_id') or meta.get('published_record',{}).get('law_id')
                if declared_law and declared_law!=member.get('law_id') and not member.get('reuse_receipt'):
                    raise ValueError('Another law requires an explicit reuse receipt')
                if not member.get('reuse_receipt'):
                    for field in ('cell_id', 'actor', 'case_id'):
                        if meta.get(field) != member.get(field):
                            raise ValueError('Recording membership mismatch: ' + field)
                else:
                    proof=member['reuse_receipt']
                    if not isinstance(proof,dict) or not isinstance(proof.get('provenance'),dict) or identity(proof['provenance'])!=proof.get('sha256'):
                        raise ValueError('Reuse requires a hash-bound provenance receipt')
                row.update(video='../../recordings/' + rid + '/video.webm',
                           trace='../../recordings/' + rid + '/trace.json')
            elif not member.get('reason'):
                raise ValueError('Nonaccepted dispositions require a reason')
            rows.append(row)
        manifest = {'format': 'recording-set-v1', 'set_id': set_id, 'selection_sha256': selection_hash,
                    'members': rows, 'recording_ids': sorted(recordings),
                    'accepted_members': sum(r['status'] == 'accepted' for r in rows),
                    'evidence_complete': all(r['status'] == 'accepted' for r in rows),
                    'coverage_complete': selection.get('reviewed_coverage_complete') is True
                       and all(r['status'] == 'accepted' for r in rows)}
        if scope is not None:
            manifest['scope'] = scope
            manifest['coverage_complete'] = manifest['coverage_complete'] and scope.get('reviewed_coverage_complete') is True
        staging = Path(tempfile.mkdtemp(prefix='.finalize-', dir=directory))
        try:
            atomic(staging / 'membership.json', manifest)
            with (staging / 'cases.csv').open('w', newline='') as stream:
                fields = ['campaign', 'law_id', 'cell_id', 'actor', 'case_id', 'split', 'status', 'recording_id', 'video', 'trace']
                writer = csv.DictWriter(stream, fields, extrasaction='ignore')
                writer.writeheader(); writer.writerows(rows)
            hashes = {p.name: sha(p) for p in staging.iterdir()}
            if acquisition.is_file() and (directory/'manifest.json').is_symlink():hashes['manifest.json']=sha(acquisition)
            result = {'set_id': set_id, 'selection_sha256': selection_hash, 'metadata_sha256': hashes,
                      'recordings': len(recordings), 'accepted_members': manifest['accepted_members'],
                      'evidence_complete': manifest['evidence_complete'], 'coverage_complete': manifest['coverage_complete'],
                      'started': started, 'ended': time.time()}
            for p in staging.iterdir():
                os.replace(p, directory / p.name)
            atomic(receipt, result)  # Commit marker; an interrupted finalization has no receipt.
            return result
        finally:
            shutil.rmtree(staging)


def package_set(set_id, output, archive=False, root=None):
    root = Path(root) if root is not None else OUTPUT_ROOT
    directory = root / 'sets' / safe_name(set_id)
    if not (directory / 'completion.json').exists():
        raise ValueError('Finalize the set before packaging')
    # Validate the committed selection before materializing it.
    finalize_set(set_id, root)
    manifest = json.loads((directory / 'membership.json').read_text())
    output = require_artifact_path(output) if root == OUTPUT_ROOT else Path(output)
    if output.exists() or (archive and output.with_suffix('.zip').exists()):
        raise ValueError('Package destination already exists')
    if root / 'recordings' == output or root / 'recordings' in output.parents or directory == output or directory in output.parents:
        raise ValueError('Package must be separate from source evidence and set metadata')
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.package-', dir=output.parent))
    try:
        for rid in manifest['recording_ids']:
            verify_recording(root / 'recordings' / rid)
            shutil.copytree(root / 'recordings' / rid, stage / 'recordings' / rid)
        packaged = json.loads(json.dumps(manifest))
        for row in packaged['members']:
            if row['status'] == 'accepted':
                row['video'] = 'recordings/' + row['recording_id'] + '/video.webm'
                row['trace'] = 'recordings/' + row['recording_id'] + '/trace.json'
        for name in ('selection.json', 'completion.json'):
            shutil.copyfile(directory / name, stage / name)
        atomic(stage / 'membership.json', packaged)
        from shared_manifest import canonical_path
        capability = canonical_path(root)
        if capability.is_file():
            shutil.copy2(capability, stage/'manifest.json')
        for rid in manifest['recording_ids']:
            source=root/'recordings'/rid/'manifest.json'
            if not source.is_file():continue
            checksum=sha(source)
            profile=stage/'inputs/shared/manifests'/(checksum+'.json')
            profile.parent.mkdir(parents=True,exist_ok=True)
            if not profile.exists():shutil.copy2(source,profile)
            for directory in (stage/'recordings'/rid,stage/'recordings'/rid/'evidence/traffic_spec'):
                destination=directory/'manifest.json'
                if destination.exists() or destination.is_symlink():destination.unlink()
                if directory.is_dir():destination.symlink_to(os.path.relpath(profile,directory))
        with (stage / 'cases.csv').open('w', newline='') as stream:
            fields = ['campaign','law_id','cell_id','actor','case_id','split','status','recording_id','video','trace']
            writer = csv.DictWriter(stream, fields, extrasaction='ignore');writer.writeheader();writer.writerows(packaged['members'])
        with (stage / 'SHA256SUMS').open('w') as stream:
            for p in sorted(stage.rglob('*')):
                if p.is_file() and p.name != 'SHA256SUMS':
                    stream.write(sha(p) + '  ' + p.relative_to(stage).as_posix() + '\n')
        stage.rename(output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    if archive:
        target = output.with_suffix('.zip')
        temporary = target.with_name('.' + target.name + '.pending')
        try:
            with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as z:
                for p in sorted(output.rglob('*')):
                    if p.is_file():
                        z.write(p, p.relative_to(output))
            with zipfile.ZipFile(temporary) as z:
                if z.testzip() is not None:
                    raise ValueError('Archive CRC verification failed')
            temporary.rename(target)
        finally:
            temporary.unlink(missing_ok=True)
    return {'output': str(output), 'archive': str(output.with_suffix('.zip')) if archive else None}


def selected_recordings(root, sets):
    """Deduplicate accepted memberships and protect every held-out recording."""
    from lean_work import folder, case_folder
    allowed={'demo-train','full-train','demo-test','full-test'}
    if not sets or set(sets)-allowed:raise ValueError('Reconstruction accepts non-held-out train/test sets only')
    result={}
    for name in sets:
        for member in json.loads((root/'sets'/name/'selection.json').read_text())['members']:
            if member.get('status')!='accepted':continue
            rid=member['recording_id']
            target=result.setdefault(rid,dict(member,sets=[]))
            if any(target.get(k)!=member.get(k) for k in ('law_id','case_id','cell_id')):
                raise ValueError('Conflicting recording membership: '+rid)
            target['sets'].append(name)
    held=root/'sets/held-out/selection.json'
    if held.exists() and set(result)&{m.get('recording_id') for m in json.loads(held.read_text())['members']}:
        raise ValueError('Selected recordings overlap held-out membership')
    for member in result.values():
        name='full-train' if any('train' in s for s in member['sets']) else 'full-test'
        review=root/'work'/name/folder(member)/case_folder(member)
        member['review']=str(review.resolve())
    return list(result.values())


def _reconstruct_recording(args):
    """Independent CPU task; successful hash-bound results are resumable."""
    import subprocess
    from traffic_spec_adapter.adapter import reconstruct
    root,archive,library,validator,source_key,member,required,raw_graphs,*overrides=args
    rid=member['recording_id'];case=Path(member['review']);trace=case/'trace.json'
    stage=archive/'stage'/rid;stage.mkdir(parents=True,exist_ok=True)
    report_path=stage/'report.json';input_hash=sha(trace)
    evidence=root/'recordings'/rid/'evidence'
    source_index=archive/'evidence-index.json'
    reference=json.loads(source_index.read_text()).get(rid) if source_index.exists() else None
    canonical_report=root/'recordings'/rid/'adapter_report.json'
    stored=json.loads(canonical_report.read_text()).get('reconstruction') if canonical_report.exists() else None
    context=overrides[0] if overrides and overrides[0] is not None else (stored or {}).get('context_recovery_receipt')
    static_inventory=overrides[1] if len(overrides)>1 and overrides[1] is not None else (stored or {}).get('static_inventory_receipt')
    if stored and stored.get('context_recovery_receipt') and context!=stored['context_recovery_receipt']:
        previous_context=dict(stored['context_recovery_receipt']);candidate=dict(context or {})
        previous_context.pop('scope_limits',None);candidate.pop('scope_limits',None)
        if candidate!=previous_context:
            raise ValueError('Published plan bindings are immutable; rebuild a changed receipt from the archived original trace')
    if reference is None and stored and stored.get('evidence_origin') and not (evidence/'road.xodr').exists():
        delivery=evidence/'delivery/evidence.json'
        if delivery.exists():
            original_receipt=json.loads(delivery.read_text()).get('provenance',{})
            reference={'original':stored['evidence_origin'],'result_sha256':original_receipt.get('result_sha256'),
                       'delivery_receipt_sha256':sha(delivery)}
    if reference:
        from traffic_spec_adapter.inventory_observations import Evidence
        delivery=Evidence(evidence.parent).path('delivery/evidence.json')
        if delivery is None or sha(delivery)!=reference['delivery_receipt_sha256']:
            raise ValueError('Historical source reference has no frozen delivery receipt')
        receipt=json.loads(delivery.read_text())
        candidate=Path(reference['original'])
        if receipt.get('provenance',{}).get('result_sha256')!=reference['result_sha256'] or sha(candidate/'result.json')!=reference['result_sha256']:
            raise ValueError('Historical source result differs from original delivery')
        result=json.loads((candidate/'result.json').read_text())
        if result.get('case_id')!=member['case_id']:raise ValueError('Historical source belongs to another case')
        evidence=candidate
    if static_inventory is None and (evidence/'static_map_inventory.json').exists():
        from traffic_spec_adapter.inventory_observations import Evidence,retained_static_inventory
        static_inventory=retained_static_inventory(Evidence(evidence.parent))
    context_key=([identity(context)] if context else [])+([identity(static_inventory)] if static_inventory else [])
    binding=evidence.parent/'evidence-checksums.json'
    source_inventory=json.loads(binding.read_text()) if binding.exists() else {'evidence/'+k:v for k,v in json.loads((evidence/'result.json').read_text()).get('completion',{}).get('artifact_hashes',{}).items()}
    source_hash=identity({k:v for k,v in source_inventory.items() if not k.startswith('evidence/traffic_spec/')}) if source_inventory else sha(evidence/'result.json')
    key=identity([input_hash,source_hash,source_key,sorted(required),raw_graphs]+context_key)
    validation_candidate=json.loads(report_path.read_text()) if report_path.exists() else stored
    previous=None
    if not report_path.exists():previous=stored
    if report_path.exists():
        previous=json.loads(report_path.read_text())
        if previous.get('context_recovery_receipt')!=context or previous.get('static_inventory_receipt')!=static_inventory:previous=None
        if previous and previous.get('cache_key')==key and previous.get('decoder_passed') and (
                not previous['changed'] or sha(stage/'trace.json')==previous['output_trace_sha256']):
            return dict(previous,metadata_sha256=sha(case/'metadata.json'),cached=True)
    if previous and previous.get('decoder_passed') and previous.get('source_key')==source_key and previous.get('output_trace_sha256')==input_hash and previous.get('evidence_inventory_sha256')==source_hash and previous.get('cache_key') in {identity([previous['input_trace_sha256'],source_hash,source_key,sorted(required),mode]+context_key) for mode in ([True] if raw_graphs else [False,True])}:
        # Publication changes the input path's bytes to the validated output.
        # Reuse that proof instead of treating the published trace as new work.
        return dict(previous,input_trace_sha256=input_hash,metadata_sha256=sha(case/'metadata.json'),
                    cache_key=key,changed=False,changes={},cached=True,reused_published_validation=True)
    started=time.monotonic()
    prior=None;input_path=trace;output_path=stage/'trace.json'
    if previous and previous.get('decoder_passed') and previous.get('changed') and (
            previous.get('input_trace_sha256')==input_hash and previous.get('evidence_inventory_sha256')==source_hash
            and sha(stage/'trace.json')==previous.get('output_trace_sha256')
            and not previous.get('changes',{}).get('segmented_lane_regions')):
        # A prior validated repair is another retained trace, not a reason to
        # repeat its writes. A partitioned lane no longer has the original full
        # native footprint, so rebuild those records from their original input
        # rather than joining map identities to individual fragments by shape.
        prior=previous;input_path=stage/'trace.json';output_path=stage/'trace.next.json'
    report=reconstruct(input_path,evidence,library,output_path,cache=archive/'map-cache',
                       required=required,read_graphs=raw_graphs,context_recovery=context,inventory_recovery=static_inventory)
    if prior:
        from collections import Counter
        if report['changed']:output_path.replace(stage/'trace.json')
        report['incremental_changes']=dict(report['changes'])
        changes=Counter(prior['changes']);changes.update(report['changes']);report['changes']=dict(changes)
        report['evidence_used']=dict(prior.get('evidence_used',{}),**report['evidence_used'])
        report['prior_staged_output_sha256']=prior['output_trace_sha256']
        report['prior_source_key']=prior['source_key'];report['changed']=True
    report.update(evidence_origin=str(evidence),recording_id=rid,law_id=member['law_id'],cache_key=key,
                  input_trace_sha256=input_hash,evidence_inventory_sha256=source_hash,
                  metadata_sha256=sha(case/'metadata.json'),source_key=source_key)
    result_path=stage/'trace.json' if report['changed'] else trace
    report['output_trace_sha256']=sha(result_path) if report['changed'] else input_hash
    if report['output_trace_sha256']==input_hash:report['changed']=False
    signature=overrides[2] if len(overrides)>2 else identity([sha(validator),sha(archive/'manifest.json')])
    reuse=bool(validation_candidate and validation_candidate.get('decoder_passed') and
               validation_candidate.get('output_trace_sha256')==report['output_trace_sha256'] and
               validation_candidate.get('decoder_signature')==signature)
    before_decode=time.monotonic()
    if reuse:
        report['decoder_passed']=True;report['decoder_error']=''
    else:
        process=subprocess.run([str(validator),str(result_path),str(archive/'manifest.json')],
                               capture_output=True,text=True,timeout=600)
        report['decoder_passed']=process.returncode==0
        report['decoder_error']=process.stderr[-3000:]
    report['decoder_signature']=signature
    report['reused_unchanged_core_validation']=reuse
    report['timings']['decode_seconds']=0 if reuse else time.monotonic()-before_decode
    report['elapsed_seconds']=time.monotonic()-started
    atomic(report_path,report)
    return report


def reconstruct_collection(root, sets, archive, library, validator, *, workers=8,
                           recordings=(), apply=False, raw_graphs=False, context_index=None, inventory_index=None):
    """Stage, decode, then publish retained-evidence repairs; never run CARLA."""
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
    root,archive,library,validator=map(lambda p:Path(p).resolve(),(root,archive,library,validator))
    if root==archive or root in archive.parents:raise ValueError('Historical staging belongs outside active outputs')
    if not validator.is_file():raise ValueError('Core decoder executable is required')
    if workers<1:raise ValueError('Worker count must be positive')
    archive.mkdir(parents=True,exist_ok=True)
    from traffic_spec_adapter.adapter import manifest
    from shared_manifest import encoded
    new_manifest=encoded(manifest(library))
    (archive/'manifest.json').write_bytes(new_manifest)
    old_manifest_hash=sha(root/'inputs/shared/manifest.json')
    manifest_changed=new_manifest!=(root/'inputs/shared/manifest.json').read_bytes()
    members=selected_recordings(root,sets)
    contexts=json.loads(Path(context_index).read_text()) if context_index else {}
    inventories=json.loads(Path(inventory_index).read_text()) if inventory_index else {}
    if not isinstance(contexts,dict):raise ValueError('Context index must map recording IDs to plan-binding receipts')
    if set(contexts)-{m['recording_id'] for m in members}:raise ValueError('Context index contains non-selected or held-out recordings')
    if not isinstance(inventories,dict):raise ValueError('Inventory index must map recording IDs to source-bound receipts')
    if set(inventories)-{m['recording_id'] for m in members}:raise ValueError('Inventory index contains non-selected or held-out recordings')
    if recordings:
        unknown=set(recordings)-{m['recording_id'] for m in members}
        if unknown:raise ValueError('Recording not in selected accepted sets: '+str(sorted(unknown)))
        members=[m for m in members if m['recording_id'] in recordings]
    source=Path(__file__).parent
    source_key=identity([
        {str(p.relative_to(source)):sha(p) for p in list((source/'traffic_spec_adapter').glob('*.py'))+
            [source/n for n in ('recording_store.py','trace_json.py','context_catalogue.py','authored_context.py','intentions.py')]},
        sha(validator),sha(archive/'manifest.json')])
    # Existing audit dependencies prioritize coverage diagnostics only. Missing
    # executable rules do not prevent measured data repair.
    ledger=root/'inputs/shared/repair-ledger.json'
    requirements={r['recording_id']:r.get('required_atoms',[]) for r in json.loads(ledger.read_text())} if ledger.exists() else {}
    decoder_signature=identity([sha(validator),sha(archive/'manifest.json')])
    inventory=[]
    for m in members:
        frozen=root/'recordings'/m['recording_id']/'evidence/capture/manifest.json'
        capture_required=json.loads(frozen.read_text()).get('required_observations',[]) if frozen.exists() else []
        inventory.append((root,archive,library,validator,source_key,m,
                          set(requirements.get(m['recording_id'],[]))|set(capture_required),raw_graphs,
                          contexts.get(m['recording_id']),inventories.get(m['recording_id']),decoder_signature))
    started=time.monotonic();reports=[]
    with locked(root/'state/reconstruction.lock'):
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(_reconstruct_recording,arg) for arg in inventory]
            for future in as_completed(futures):
                report=future.result();reports.append(report)
                print(json.dumps({k:report.get(k) for k in ('recording_id','changed','decoder_passed','elapsed_seconds','cached')}),flush=True)
        atomic(archive/'reports.json',reports)
        if not all(r['decoder_passed'] for r in reports):raise ValueError('Core decoding failed; staged outputs have not been published')
        if apply:
            if manifest_changed and {m['recording_id'] for m in members}!={m['recording_id'] for m in selected_recordings(root,['full-train','full-test'])}:
                raise ValueError('A capability change requires migration of every accepted non-held-out recording')
            if len({m['review']for m in members})!=len(members):raise ValueError('Different recordings share a review output directory')
            by_id={r['recording_id']:r for r in reports}
            def check_current(member):
                r=by_id[member['recording_id']];case=Path(member['review']);canonical=root/'recordings'/member['recording_id']
                if sha(case/'trace.json')!=r['input_trace_sha256'] or sha(canonical/'trace.json')!=r['input_trace_sha256'] or sha(case/'metadata.json')!=r['metadata_sha256']:
                    raise ValueError('Collection changed after staging: '+member['recording_id'])
            with ThreadPoolExecutor(max_workers=min(workers,16))as pool:list(pool.map(check_current,members))
            if manifest_changed:
                current=root/'inputs/shared/manifest.json'
                if sha(current)!=old_manifest_hash:raise ValueError('Manifest changed during staging')
                shutil.copy2(current,archive/'previous-manifest.json')
                temporary=current.with_suffix('.reconstruct-tmp');temporary.write_bytes(new_manifest);temporary.replace(current)
            def publish(member):
                publish_reconstructed(root,archive,member,by_id[member['recording_id']],manifest_changed=manifest_changed)
                print(json.dumps({'published_recording':member['recording_id']}),flush=True)
            with ThreadPoolExecutor(max_workers=min(workers,16))as pool:list(pool.map(publish,members))
    from collections import Counter
    changes=Counter()
    for r in reports:changes.update(r['changes'])
    summary={'recordings':len(reports),'changed':sum(r['changed'] for r in reports),
        'decoder_passed':sum(r['decoder_passed'] for r in reports),'changes':dict(changes),
        'elapsed_seconds':time.monotonic()-started,'workers':workers,'published':apply,
        'source_key':source_key,'archive':str(archive),'gpu_simulations':0,'carla_executions':0,
        'cached_recordings':sum(bool(r.get('cached')) for r in reports),
        'manifest_sha256':sha(archive/'manifest.json'),'manifest_changed':manifest_changed}
    atomic(archive/'summary.json',summary)
    if apply:atomic(root/'inputs/shared/reconstruction.json',summary)
    return summary


def publish_reconstructed(root, archive, member, report, *, manifest_changed=False):
    """Archive superseded derivatives; original evidence and membership stay put."""
    from shared_manifest import verify as verify_manifest
    rid=member['recording_id'];canonical=root/'recordings'/rid;review=Path(member['review'])
    manifest_hash=sha(root/'inputs/shared/manifest.json')
    def preserve(path):
        if not path.exists():return
        target=archive/'superseded'/path.relative_to(root)
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():shutil.copy2(path,target)
        if sha(target)!=sha(path):
            raise ValueError('Superseded artifact backup differs from the current input: '+str(path))
    def install(path,source):
        preserve(path);temp=path.with_name(path.name+'.reconstruct-tmp')
        shutil.copyfile(source,temp);temp.replace(path)
    if sha(review/'trace.json')!=report['input_trace_sha256']:
        raise ValueError('Review changed after staging: '+rid)
    if sha(review/'metadata.json')!=report['metadata_sha256']:
        raise ValueError('Review metadata changed after staging: '+rid)
    if sha(canonical/'trace.json')!=report['input_trace_sha256']:
        raise ValueError('Canonical/review trace mismatch: '+rid)
    if not report['changed'] and not manifest_changed:
        previous=json.loads((canonical/'adapter_report.json').read_text()).get('reconstruction',{}) if (canonical/'adapter_report.json').exists()else{}
        if previous.get('source_key')==report['source_key']and previous.get('static_inventory_receipt')==report.get('static_inventory_receipt'):return
    stage=archive/'stage'/rid
    if report['changed'] and sha(stage/'trace.json')!=report['output_trace_sha256']:raise ValueError('Staged output changed: '+rid)
    for directory in dict.fromkeys([canonical,review,canonical/'evidence/traffic_spec']):
        if not directory.exists():continue
        verify_manifest(root,directory,manifest_hash)
        if report['changed']:install(directory/'trace.json',stage/'trace.json')
        report_path=canonical/'adapter_report.json' if directory==review else directory/'adapter_report.json'
        if directory==review:
            auxiliary=directory/'adapter_report.json'
            if auxiliary.exists():preserve(auxiliary);auxiliary.unlink()
        else:
            preserve(report_path)
            value=json.loads(report_path.read_text()) if report_path.exists() else {}
            value['reconstruction']=report
            value['decoder_validation']='passed'
            value['required_measurements_complete']=False
            value['trace_sha256']=report['output_trace_sha256'];value['manifest_sha256']=manifest_hash
            if 'output_trace_sha256' in value:value['output_trace_sha256']=report['output_trace_sha256']
            value.pop('atom_coverage',None)  # Its previous trace and manifest are archived.
            atomic(report_path,value)
        metadata=directory/'metadata.json'
        if metadata.exists():
            preserve(metadata);value=json.loads(metadata.read_text());value['trace_sha256']=report['output_trace_sha256']
            value['manifest_sha256']=manifest_hash
            value['reconstruction']={'decoder_passed':True,'source_key':report['source_key'],
                'report':str(report_path.relative_to(root)),'report_sha256':sha(report_path),
                'original_trace_sha256':report['input_trace_sha256']}
            prior={k:value.pop(k) for k in ('offline_repair','b_repair') if k in value}
            if report['changed'] or manifest_changed:prior.update({k:value.pop(k) for k in ('trace_migration','intention_validation') if k in value})
            if prior:value['reconstruction']['superseded_validation']=prior
            for key in ('published_record','source_record'):
                nested=value.get(key)
                if isinstance(nested,dict):
                    if 'trace_sha256' in nested:nested['trace_sha256']=report['output_trace_sha256']
                    if 'manifest_sha256' in nested:nested['manifest_sha256']=manifest_hash
                    if isinstance(nested.get('sha256'),dict):
                        for name,digest in (('trace.json',report['output_trace_sha256']),('manifest.json',manifest_hash)):
                            if name in nested['sha256']:nested['sha256'][name]=digest
            # Previously evaluated verdicts describe the old trace, not this one.
            if isinstance(value.get('offline_repair'),dict):value['offline_repair']['verdicts_verified']=False
            atomic(metadata,value)
    checks=canonical/'evidence-checksums.json'
    completion_path=canonical/'evidence/result.json'
    if checks.exists() or completion_path.exists():
        preserve(checks)
        if checks.exists():values=json.loads(checks.read_text())
        else:values={'evidence/'+k:v for k,v in json.loads(completion_path.read_text()).get('completion',{}).get('artifact_hashes',{}).items()}
        for name in ('trace.json','adapter_report.json','manifest.json'):
            path=canonical/'evidence/traffic_spec'/name
            if path.exists():values['evidence/traffic_spec/'+name]=sha(path)
        atomic(checks,values)
