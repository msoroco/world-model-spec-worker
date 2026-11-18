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


def verified_label(folder, metadata, *, trace_sha256=None, authority_path=None, adapter_report_path=None):
    """Verify one authority and its canonical projection before publication."""
    from production_verdicts import validate_authoritative,validate_presentation,presentation
    folder=Path(folder)
    path=Path(authority_path) if authority_path is not None else folder/'evidence/expected_label.json'
    if not path.is_file():raise ValueError('Source-bound outcome record missing: '+folder.name)
    record=validate_authoritative(json.loads(path.read_text()))
    import production_verdicts
    if record['classification_method']['source_sha256']!=sha(Path(production_verdicts.__file__)):
        raise ValueError('Outcome classification uses superseded implementation; regenerate from frozen sources')
    if record['evidence_status']!='accepted':raise ValueError('Outcome evidence still requires repair')
    if metadata.get('recapture'):
        recorded_identity=record.get('recording_identity',{})
        if recorded_identity.get('recording_id')!=folder.name or recorded_identity.get('parent_recording_id')!=metadata.get('parent_recording_id'):
            raise ValueError('Recapture outcome identity/parent lineage differs')
    reference=record.get('reference_check')or{}
    if record.get('evaluation_method')=='recorded_rule_reference' and record['expected_label'] in ('compliant','violation','not applicable'):
        implementations=reference.get('source_hashes',{})
        if set(implementations)!={'expected_labels.py','demo_rule_evidence.py'}:
            raise ValueError('Recorded-rule evaluator source bindings missing')
        for name,checksum in implementations.items():
            if sha(Path(__file__).with_name(name))!=checksum:
                raise ValueError('Recorded-rule evaluator implementation changed: '+name)
    expected=trace_sha256 or metadata.get('trace_sha256')
    if record['source_hashes']['trace_sha256']!=expected:
        raise ValueError('Authoritative outcome is bound to a stale trace')
    if record['case_id']!=metadata.get('case_id') or record['target_law_id']!=(metadata.get('law_id') or record['target_law_id']):
        raise ValueError('Authoritative outcome identity disagrees with recording')
    definition_hash=record['source_hashes']['definition_sha256']
    candidates=[folder/'evidence'/name for name in
                ('accepted_case_definition.json','expected_label_case_definition.json','case.json')]
    if not any(path.is_file() and sha(path)==definition_hash for path in candidates):
        raise ValueError('Authoritative outcome definition is missing or changed')
    if record['source_hashes'].get('original_capture_sha256'):
        source=folder/'evidence/trace.jsonl'
        if not source.is_file() or sha(source)!=record['source_hashes']['original_capture_sha256']:
            raise ValueError('Authoritative outcome original capture changed')
    if record['source_hashes'].get('adapter_report_sha256'):
        profile=Path(adapter_report_path) if adapter_report_path is not None else folder/'evidence/traffic_spec/adapter_report.json'
        if not profile.is_file() or sha(profile)!=record['source_hashes']['adapter_report_sha256']:
            raise ValueError('Authoritative outcome capture-profile receipt changed')
    for source in (metadata, metadata.get('acceptance',{}),metadata.get('published_record',{})):
        if source.get('label_record') is not None:validate_presentation(record,source['label_record'])
        for key in ('expected_label','judgment_sweep'):
            if key in source and source[key]!=record[key]:raise ValueError('Saved label projection disagrees: '+key)
    return record


def case_csv_row(row):
    """Encode the pinned classification as JSON, avoiding Python repr in CSV."""
    result=dict(row)
    if result.get('label_record') is not None:
        result['label_record']=json.dumps(result['label_record'],sort_keys=True,separators=(',',':'))
    return result


def accept_recording(directory, record):
    """Called after the existing full case acceptance, never instead of it."""
    folder = Path(directory).parent
    path = folder / 'metadata.json'
    value = json.loads(path.read_text())
    started = time.time()
    if value.get('recapture'):
        lineage=value['recapture'];source_manifest=folder/'recapture-source-manifest.json'
        if sha(source_manifest)!=lineage.get('source_manifest_sha256'):
            raise ValueError('Recapture source manifest changed before acceptance')
        physical=lineage.get('physical_acquisition',{})
        receipt=json.loads(source_manifest.read_text())
        if (physical!=receipt.get('physical_acquisition') or identity(physical)!=folder.name
                or physical.get('parent_recording_id')!=value.get('parent_recording_id')):
            raise ValueError('Recapture physical identity or parent lineage changed')
        original=json.loads((Path(directory)/'result.json').read_text())
        if sha(Path(directory)/'result.json')!=physical.get('original_result_sha256'):
            raise ValueError('Recapture original result changed before acceptance')
        from batch_pipeline.completion import verify as verify_completion
        verify_completion(directory,original['completion']['binding'])
        final=receipt['final_artifacts_sha256']
        if record['trace_sha256']!=final['trace.json'] or record['video_sha256']!=final['video.webm']:
            raise ValueError('Recapture acceptance outputs differ from staged validation')
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
    from production_verdicts import presentation,validate_presentation
    authority=verified_label(folder,dict(value,law_id=record.get('law_id')),trace_sha256=record['trace_sha256'])
    validate_presentation(authority,record.get('label_record',{}))
    value.update(label_record=presentation(authority),expected_label=authority['expected_label'],
                 judgment_sweep=authority['judgment_sweep'])
    if value.get('recapture'):value['recapture']['pending_explicit_acceptance']=False
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


def verify_recording(folder, *, require_label=False):
    folder = Path(folder)
    value = json.loads((folder / 'metadata.json').read_text())
    if value.get('status') != 'accepted':
        raise ValueError('Recording is not accepted: ' + folder.name)
    if require_label:
        verified_label(folder,value)
        if value.get('label_record') is None:raise ValueError('Canonical label projection missing')
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
        if set_id.endswith('-test') or any(m.get('split') == 'testing' for m in members):
            from judgment_coverage import audit_set
            judgment = audit_set(root, set_id)
            atomic(directory / 'judgment_coverage.json', judgment)
            if not judgment['passed']:
                raise ValueError('Judgment coverage incomplete; see ' + str(directory / 'judgment_coverage.json'))
        from shared_manifest import canonical_path, link as link_manifest
        acquisition = canonical_path(root)
        if acquisition.is_file() and any(m.get('split') != 'heldout' for m in members):
            link_manifest(root, directory)
        selection_hash = identity(selection)
        receipt = directory / 'completion.json'
        if receipt.exists():
            old = json.loads(receipt.read_text())
            if old.get('label_record_format')!='production-verdict-v2':
                raise ValueError('Finalized set requires source-bound v2 label regeneration')
            if old['selection_sha256'] != selection_hash:
                raise ValueError('Finalized selection changed; create a new set version')
            labels=old.get('label_records_sha256',{})
            expected_ids={m['recording_id']for m in members if m.get('status')=='accepted'}
            if set(labels)!=expected_ids:raise ValueError('Finalized outcome membership changed')
            for rid,checksum in labels.items():
                if sha(root/'recordings'/rid/'evidence/expected_label.json')!=checksum:
                    raise ValueError('Finalized outcome authority changed')
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
                    verified=verify_recording(root / 'recordings' / rid,require_label=True)
                    recordings[rid]={k:verified.get(k) for k in ('cell_id','actor','case_id','split','video_sha256','trace_sha256')}
                    recordings[rid]['label_record']=verified['label_record']
                    recordings[rid]['law_id']=verified.get('law_id') or verified.get('published_record',{}).get('law_id')
                meta = recordings[rid]
                projection=meta['label_record']
                row.update(label_record=projection,expected_label=projection['expected_label'],
                           judgment_sweep=projection['sweep_membership']['is_member'])
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
                fields = ['campaign', 'law_id', 'cell_id', 'actor', 'case_id', 'split', 'status', 'recording_id', 'video', 'trace', 'expected_label','judgment_sweep','label_record']
                writer = csv.DictWriter(stream, fields, extrasaction='ignore')
                writer.writeheader(); writer.writerows(case_csv_row(row)for row in rows)
            hashes = {p.name: sha(p) for p in staging.iterdir()}
            if acquisition.is_file() and (directory/'manifest.json').is_symlink():hashes['manifest.json']=sha(acquisition)
            result = {'set_id': set_id, 'label_record_format':'production-verdict-v2','selection_sha256': selection_hash, 'metadata_sha256': hashes,
                      'label_records_sha256':{rid:sha(root/'recordings'/rid/'evidence/expected_label.json')for rid in recordings},
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
            fields = ['campaign','law_id','cell_id','actor','case_id','split','status','recording_id','video','trace','expected_label','judgment_sweep','label_record']
            writer = csv.DictWriter(stream, fields, extrasaction='ignore');writer.writeheader();writer.writerows(case_csv_row(row)for row in packaged['members'])
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
    """Resolve current outputs once, retaining membership and every review alias."""
    from lean_work import folder, case_folder, SETS
    root = Path(root).resolve()
    if not sets or set(sets)-set(SETS):raise ValueError('Unknown reconstruction set')
    result = {}; ownership = {}; work = {}
    def add(member, name, review=None):
        rid = member['recording_id']
        if member.get('status', 'accepted') != 'accepted':return
        partition = 'held-out' if name == 'held-out' else 'train' if name.endswith('train') else 'test'
        owners = ownership.setdefault(rid, set()); owners.add(partition)
        if len(owners) > 1:
            raise ValueError('Recording crosses train/test/held-out membership: '+rid)
        if name not in sets:return
        target = result.setdefault(rid, dict(member, sets=[], reviews=[]))
        if any(target.get(k) != member.get(k) for k in ('law_id', 'case_id', 'cell_id')):
            raise ValueError('Conflicting recording membership: '+rid)
        if name not in target['sets']:target['sets'].append(name)
        if review is not None and str(review) not in target['reviews']:
            target['reviews'].append(str(review))
    for name in SETS:
        selection = root/'sets'/name/'selection.json'
        if selection.is_file():
            for member in json.loads(selection.read_text())['members']:add(member, name)
        base = root/'work'/name
        if not base.is_dir():continue
        for law in sorted(base.iterdir()):
            if not law.is_dir():continue
            for case in sorted(law.iterdir()):
                if not case.is_dir():continue
                metadata = case/'metadata.json'
                if not metadata.is_file():raise ValueError('Current review metadata missing: '+str(case))
                member = json.loads(metadata.read_text())
                if not member.get('recording_id'):raise ValueError('Current review recording identity missing: '+str(case))
                cell, separator, law_id = law.name.partition('--')
                if not separator or member.get('law_id') != law_id:
                    raise ValueError('Current review law identity differs: '+str(case))
                member = dict(member, cell_id=cell)
                resolved = case.resolve()
                if root/'work' not in resolved.parents:
                    raise ValueError('Current review link escapes work tree: '+str(case))
                work.setdefault(member['recording_id'], set()).add(str(resolved))
                add(member, name, resolved)
    for rid, member in result.items():
        member['reviews'] = sorted(work.get(rid, set())) or member['reviews']
        if not member['reviews']:
            name = member['sets'][0]
            parent = {'demo-train':'full-train', 'demo-test':'full-test'}.get(name, name)
            member['reviews'] = [str((root/'work'/parent/folder(member)/case_folder(member)).resolve())]
        member['review'] = member['reviews'][0]
    return sorted(result.values(), key=lambda member: ('demo-train' not in member['sets'], member['recording_id']))


def _historical_case_matches(result, expected_case, evidence, original_evidence=None):
    """Verify a case identifier, including the original native-recorder-v1 path.

    Missing legacy result fields are not conflicting identifiers. The fallback
    requires original hash-bound config/producer/capture/recorder inputs and the
    actual captured subject's native role, independently of the imported Python
    capture writer. It does not infer identity from a directory or rename data.
    """
    if 'case_id' in result:
        return result['case_id'] == expected_case
    import ast
    import re
    from traffic_spec_adapter.inventory_observations import Evidence
    view = Evidence(Path(evidence).parent)
    names = ('capture/manifest.json', 'config.json', 'runner.py',
             'capture/recorder_info.txt', 'capture/evidence.jsonl', 'carla_recorder.log')
    original = Evidence(Path(original_evidence).parent) if original_evidence is not None else view
    paths = {}
    for name in names:
        key = 'evidence/' + name
        # Derived sparse views may omit a large original recorder file, but
        # they may not change any case-identity source binding.
        if not view.expected.get(key) or view.expected.get(key) != original.expected.get(key):return False
        paths[name] = view.path(name) or original.path(name)
    if any(path is None for path in paths.values()):return False
    capture = json.loads(paths['capture/manifest.json'].read_text())
    config = json.loads(paths['config.json'].read_text())
    if not isinstance(capture, dict) or not isinstance(config, dict) or not isinstance(config.get('case'), dict):return False
    if not isinstance(capture.get('map'), str) or not capture['map']:return False
    if (capture.get('acquisition') != 'original_live_run'
            or capture.get('case_id') != expected_case
            or config.get('case', {}).get('case_id') != expected_case
            or capture.get('sources', {}).get('carla_recorder.log') != sha(paths['carla_recorder.log'])):
        return False
    # This supported producer binds CASE to this immutable config and passes
    # the same value both to the native actor role and the capture constructor.
    try:tree = ast.parse(paths['runner.py'].read_text())
    except SyntaxError:return False
    def equivalent(node, expression):
        return ast.dump(node) == ast.dump(ast.parse(expression, mode='eval').body)
    bindings = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):bindings.setdefault(target.id, []).append(node.value)
    for name, expression in (('BASE', 'Path(__file__).resolve().parent'),
            ('CONFIG', "json.loads((BASE / 'config.json').read_text())"), ('CASE', "CONFIG['case']")):
        values = bindings.get(name, [])
        if len(values) != 1 or not equivalent(values[0], expression):return False
    allowed = {id(node) for node in tree.body if isinstance(node, ast.Assign)
        and all(isinstance(target, ast.Name) for target in node.targets)
        and any(target.id in ('BASE', 'CONFIG', 'CASE') for target in node.targets)}
    for node in ast.walk(tree):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)) else []
        if id(node) not in allowed and any(isinstance(item, ast.Name) and item.id in ('BASE', 'CONFIG', 'CASE') for target in targets for item in ast.walk(target)):
            return False
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    constructors = [node for node in calls if isinstance(node.func, ast.Name)
        and node.func.id == 'PipelineCapture' and len(node.args) == 4
        and equivalent(node.args[3], "CASE['case_id']")]
    roles = [node for node in calls if isinstance(node.func, ast.Attribute)
        and node.func.attr == 'set_attribute' and len(node.args) == 2
        and equivalent(node.args[0], "'role_name'") and equivalent(node.args[1], "CASE['case_id']")]
    if len(constructors) != 1 or len(roles) != 1 or roles[0].lineno >= constructors[0].lineno:return False
    # Only the declared native recorder text format is interpreted. Actor IDs
    # come from the recorded subject, never proximity or an arbitrary role tag.
    lines = paths['capture/recorder_info.txt'].read_text().splitlines()
    if not lines or lines[0] != 'Version: 1':return False
    map_names = [line[5:].strip() for line in lines if line.startswith('Map: ')]
    if map_names != [Path(capture.get('map', '')).name]:return False
    actor_ids = set()
    with paths['capture/evidence.jsonl'].open() as stream:
        for line in stream:
            if not line.strip():continue
            aid = json.loads(line).get('actor_id')
            if type(aid) is not int or aid <= 0:return False
            actor_ids.add(aid)
    if len(actor_ids) != 1:return False
    subject = next(iter(actor_ids));current = None;native_roles = set()
    for line in lines:
        match = re.match(r' Create (\d+): (\S+) ', line)
        if match:current = (int(match[1]), match[2])
        elif line.startswith('  role_name = ') and current and current[0] == subject:
            if not current[1].startswith(('vehicle.', 'walker.')):return False
            native_roles.add(line[len('  role_name = '):])
    return native_roles == {expected_case}


def _reconstruct_recording(args):
    """Independent CPU task; successful hash-bound results are resumable."""
    import subprocess
    from traffic_spec_adapter.adapter import reconstruct
    root,archive,library,validator,source_key,member,required,raw_graphs,*overrides=args
    rid=member['recording_id'];case=Path(member['review']);trace=case/'trace.json'
    stage=archive/'stage'/rid;stage.mkdir(parents=True,exist_ok=True)
    report_path=stage/'report.json';input_hash=sha(trace)
    review_inputs={str(Path(review)): {'trace_sha256':sha(Path(review)/'trace.json'),
                   'metadata_sha256':sha(Path(review)/'metadata.json')}
                   for review in member.get('reviews',[member['review']])}
    if any(value['trace_sha256']!=input_hash for value in review_inputs.values()):
        raise ValueError('Independent review copies differ before reconstruction: '+rid)
    evidence=root/'recordings'/rid/'evidence'
    source_index=archive/'evidence-index.json'
    reference=json.loads(source_index.read_text()).get(rid) if source_index.exists() else None
    canonical_inputs={name:sha(evidence.parent/name) if (evidence.parent/name).is_file() else None
        for name in ('metadata.json','adapter_report.json','manifest.json','evidence/expected_label.json','evidence-checksums.json')}
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
        if not _historical_case_matches(result, member['case_id'], candidate, evidence):raise ValueError('Historical source case identity is conflicting or unverified')
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
            return dict(previous,metadata_sha256=sha(case/'metadata.json'),review_inputs=review_inputs,canonical_inputs=canonical_inputs,cached=True)
    if previous and previous.get('decoder_passed') and previous.get('source_key')==source_key and previous.get('output_trace_sha256')==input_hash and previous.get('evidence_inventory_sha256')==source_hash and previous.get('cache_key') in {identity([previous['input_trace_sha256'],source_hash,source_key,sorted(required),mode]+context_key) for mode in ([True] if raw_graphs else [False,True])}:
        # Publication changes the input path's bytes to the validated output.
        # Reuse that proof instead of treating the published trace as new work.
        return dict(previous,input_trace_sha256=input_hash,metadata_sha256=sha(case/'metadata.json'),
                    cache_key=key,changed=False,changes={},review_inputs=review_inputs,canonical_inputs=canonical_inputs,cached=True,reused_published_validation=True)
    started=time.monotonic()
    input_path=trace;output_path=stage/'trace.json'
    report=reconstruct(input_path,evidence,library,output_path,cache=archive/'map-cache',
                       required=required,read_graphs=raw_graphs,context_recovery=context,inventory_recovery=static_inventory)
    report.update(evidence_origin=str(evidence),recording_id=rid,law_id=member['law_id'],cache_key=key,
                  input_trace_sha256=input_hash,evidence_inventory_sha256=source_hash,
                  metadata_sha256=sha(case/'metadata.json'),review_inputs=review_inputs,canonical_inputs=canonical_inputs,source_key=source_key)
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
        report['decoder_returncode']=process.returncode
        report['decoder_stdout']=process.stdout[-3000:]
        for name,value in [('decoder.stdout.log',process.stdout),('decoder.stderr.log',process.stderr)]:
            path=result_path.parent/name
            path.write_text(value)
    report['decoder_signature']=signature
    report['reused_unchanged_core_validation']=reuse
    report['timings']['decode_seconds']=0 if reuse else time.monotonic()-before_decode
    report['elapsed_seconds']=time.monotonic()-started
    atomic(report_path,report)
    return report


def recover_reconstruction_publication(root, archive):
    """Restore a hash-verified prepublication snapshot after interruption."""
    root, archive = Path(root), Path(archive)
    journal = archive/'publication.json'
    if not journal.is_file():return
    value = json.loads(journal.read_text())
    if value['state'] not in ('installing', 'restoring'):return
    # Verify the entire snapshot before restoring even the first active file.
    # A corrupt later backup must not leave a partially restored generation.
    planned={str(root/item['path']):item for item in value['files']}
    for item in value['files']:
        path = root/item['path']
        if root.resolve() not in path.parent.resolve().parents and path.parent.resolve()!=root.resolve():
            raise ValueError('Publication restore path escapes output root')
        if item['kind'] not in ('file','symlink','absent'):
            raise ValueError('Unknown publication snapshot entry')
        if item['kind'] != 'absent':
            backup=archive/'publication-backup'/item['path']
            if sha(backup)!=item['sha256']:
                raise ValueError('Publication backup changed: '+str(backup))
        if item['kind']=='symlink':
            target=path.parent/item['target']
            restored=planned.get(os.path.abspath(target))
            if restored is not None and restored['kind']!='absent' and restored['sha256']==item['sha256']:continue
            if not target.is_file() or sha(target)!=item['sha256']:
                raise ValueError('Original publication link target changed during publication')
    value['state'] = 'restoring'; atomic(journal, value)
    for item in value['files']:
        path = root/item['path']
        path.parent.mkdir(parents=True,exist_ok=True)
        if item['kind'] == 'file':
            backup = archive/'publication-backup'/item['path']
            temp = path.with_name(path.name+'.restore-tmp')
            if temp.is_symlink():temp.unlink()
            shutil.copy2(backup,temp);temp.replace(path)
        elif item['kind'] == 'symlink':
            temp = path.with_name(path.name+'.restore-tmp')
            if temp.exists() or temp.is_symlink():temp.unlink()
            temp.symlink_to(item['target']);temp.replace(path)
        elif path.exists() or path.is_symlink():path.unlink()
    value['state'] = 'restored';atomic(journal,value)


@contextmanager
def reconstruction_publication(root, archive, members, *, extra_paths=()):
    """Archive the complete install scope before changing any active derivative."""
    root, archive = Path(root), Path(archive)
    recover_reconstruction_publication(root, archive)
    paths = {root/'inputs/shared/reconstruction.json'}
    paths.update(Path(path) if Path(path).is_absolute() else root/path for path in extra_paths)
    staged_manifest=archive/'manifest.json'
    if staged_manifest.is_file():
        paths.add(root/'inputs/shared/manifests'/(sha(staged_manifest)+'.json'))
    for member in members:
        canonical = root/'recordings'/member['recording_id']
        directories = [canonical, canonical/'evidence/traffic_spec'] + [Path(p) for p in member.get('reviews',[member['review']])]
        for directory in directories:
            if directory.is_dir():
                paths.update(directory/name for name in ('video.webm','trace.json','metadata.json','adapter_report.json','manifest.json'))
        paths.add(canonical/'evidence-checksums.json')
        paths.add(canonical/'evidence/expected_label.json')
    files = []
    for path in sorted(paths):
        if root.resolve() not in path.parent.resolve().parents and path.parent.resolve()!=root.resolve():
            raise ValueError('Publication path escapes output root: '+str(path))
        relative = str(path.relative_to(root));item = {'path':relative,'kind':'absent'}
        if path.is_symlink():
            item.update(kind='symlink',target=os.readlink(path),sha256=sha(path))
        elif path.is_file():item.update(kind='file',sha256=sha(path))
        if item['kind'] != 'absent':
            backup = archive/'publication-backup'/relative
            backup.parent.mkdir(parents=True,exist_ok=True)
            if not backup.exists():shutil.copy2(path,backup)
            if sha(backup) != item['sha256']:raise ValueError('Publication preservation mismatch: '+str(path))
        files.append(item)
    journal = archive/'publication.json'
    atomic(journal,{'state':'installing','files':files})
    try:yield
    except BaseException:
        recover_reconstruction_publication(root,archive)
        raise
    else:atomic(journal,{'state':'installed','files':files})


def reconstruct_collection(root, sets, archive, library, validator, *, workers=8,
                           recordings=(), apply=False, raw_graphs=False, context_index=None, inventory_index=None,
                           publication_inputs=None, refresh_reports=None, report_paths=()):
    """Stage, decode, then publish retained-evidence repairs; never run CARLA.

    Final apply requires per-record ``publication_inputs`` paths named
    ``expected_label`` and ``adapter_report``. The latter is the complete final
    exporter report, including its reconstruction and native source projection;
    this function never rebases a projection or classifies an outcome itself.
    ``refresh_reports(root)`` generates/verifies the current indexed aggregate
    reports. Every path it can create, replace or remove belongs in
    ``report_paths`` (relative to root, or absolute). The callback owns report
    source signatures and rejection of stale/unindexed report files. Navigation,
    labels, traces, profiles and those declared report paths roll back together.
    """
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
    from concurrent.futures.process import BrokenProcessPool
    root,archive,library,validator=map(lambda p:Path(p).resolve(),(root,archive,library,validator))
    if root==archive or root in archive.parents:raise ValueError('Historical staging belongs outside active outputs')
    if not validator.is_file():raise ValueError('Core decoder executable is required')
    if workers<1:raise ValueError('Worker count must be positive')
    archive.mkdir(parents=True,exist_ok=True)
    from traffic_spec_adapter.adapter import manifest
    from shared_manifest import encoded
    new_manifest=encoded(manifest(library))
    (archive/'manifest.json').write_bytes(new_manifest)
    manifest_changed=new_manifest!=(root/'inputs/shared/manifest.json').read_bytes()
    members=selected_recordings(root,sets)
    contexts=json.loads(Path(context_index).read_text()) if context_index else {}
    inventories=json.loads(Path(inventory_index).read_text()) if inventory_index else {}
    if not isinstance(contexts,dict):raise ValueError('Context index must map recording IDs to plan-binding receipts')
    if set(contexts)-{m['recording_id'] for m in members}:raise ValueError('Context index contains non-selected recordings')
    if not isinstance(inventories,dict):raise ValueError('Inventory index must map recording IDs to source-bound receipts')
    if set(inventories)-{m['recording_id'] for m in members}:raise ValueError('Inventory index contains non-selected recordings')
    if recordings:
        unknown=set(recordings)-{m['recording_id'] for m in members}
        if unknown:raise ValueError('Recording not in selected accepted sets: '+str(sorted(unknown)))
        members=[m for m in members if m['recording_id'] in recordings]
    source=Path(__file__).parent
    source_paths=list((source/'traffic_spec_adapter').glob('*.py'))+[source/n for n in
        ('recording_store.py','trace_json.py','context_catalogue.py','authored_context.py','intentions.py')]
    source_hashes={str(p.relative_to(source)):sha(p) for p in source_paths}
    source_key=identity([source_hashes,sha(validator),sha(archive/'manifest.json')])
    from lean_work import SETS
    membership_paths=[root/'sets'/name/file for name in SETS for file in ('selection.json','scope.json')]
    membership_paths += [root/'work/index.json']+list((root/'state/review_models').glob('*/*.json'))
    membership_inputs={path:sha(path) if path.is_file() else None for path in membership_paths}
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
        recover_reconstruction_publication(root,archive)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures={pool.submit(_reconstruct_recording,arg):arg[5]['recording_id'] for arg in inventory}
            for future in as_completed(futures):
                try:report=future.result()
                except Exception as exc:
                    report={'recording_id':futures[future],'status':'interrupted' if isinstance(exc,BrokenProcessPool) else 'blocked',
                        'error_type':type(exc).__name__,'error':str(exc),
                        'changed':False,'decoder_passed':False,'changes':{},
                        'required_measurements_complete':False,'gpu_simulations':0,'carla_executions':0}
                reports.append(report)
                # Preserve every orchestration result before waiting on another case.
                atomic(archive/'collection-results'/(report['recording_id']+'.json'),report)
                print(json.dumps({k:report.get(k) for k in ('recording_id','changed','decoder_passed','elapsed_seconds','cached')}),flush=True)
        reports.sort(key=lambda report:report['recording_id'])
        atomic(archive/'reports.json',reports)
        from collections import Counter
        changes=Counter()
        for r in reports:changes.update(r['changes'])
        summary={'recordings':len(reports),'changed':sum(r['changed'] for r in reports),
            'decoder_passed':sum(r['decoder_passed'] for r in reports),
            'blocked_recordings':[r['recording_id']for r in reports if not r['decoder_passed']],
            'interrupted_recordings':[r['recording_id']for r in reports if r.get('status')=='interrupted'],'changes':dict(changes),
            'elapsed_seconds':time.monotonic()-started,'workers':workers,'published':False,
            'source_key':source_key,'archive':str(archive),'gpu_simulations':0,'carla_executions':0,
            'cached_recordings':sum(bool(r.get('cached')) for r in reports),
            'manifest_sha256':sha(archive/'manifest.json'),'manifest_changed':manifest_changed}
        atomic(archive/'summary.json',summary)
        if summary['blocked_recordings']:
            raise ValueError('Offline projection or Core decoding blocked; not every selected record completed; see '+str(archive/'reports.json'))
        if apply:
            if {str(p.relative_to(source)):sha(p) for p in source_paths}!=source_hashes or identity([source_hashes,sha(validator),sha(archive/'manifest.json')])!=source_key:
                raise ValueError('Projection implementation, validator or staged manifest changed after staging')
            if any((sha(path) if path.is_file() else None)!=checksum for path,checksum in membership_inputs.items()):
                raise ValueError('Collection membership or review model changed after staging')
            incomplete=[r['recording_id'] for r in reports if not r.get('required_measurements_complete')]
            if incomplete:raise ValueError('Required common observations incomplete; staged outputs not published: '+', '.join(incomplete))
            if len({m['review']for m in members})!=len(members):raise ValueError('Different recordings share a review output directory')
            by_id={r['recording_id']:r for r in reports}
            if not callable(refresh_reports) or not report_paths:
                raise ValueError('Final publication requires a report generator and explicit report/index paths')
            if not isinstance(publication_inputs,dict) or set(publication_inputs)!={m['recording_id'] for m in members}:
                raise ValueError('Final publication requires staged authorities and profiles for every selected recording')
            # Freeze the actual supplied bytes before checking any final projection.
            frozen_publication={rid:{name:{'path':str(Path(item[name]).resolve()),'sha256':sha(item[name])}
                for name in ('expected_label','adapter_report')} for rid,item in publication_inputs.items()}
            for member in members:
                _verified_publication_inputs(root,member,by_id[member['recording_id']],frozen_publication[member['recording_id']])
            from lean_work import refresh, SETS
            navigation=[root/'work/README.md',root/'work/index.json']
            navigation.extend((root/'work').glob('*/README.md'))
            navigation.extend((root/'work').glob('*/*/README.md'))
            navigation.extend(root/'work'/name/'README.md' for name in SETS)
            index=json.loads((root/'work/index.json').read_text())
            navigation.extend(root/'work'/entry['set_id']/entry['folder']/'README.md' for entry in index['entries'])
            generation_paths=list(report_paths)+navigation
            def check_current(member):
                r=by_id[member['recording_id']];case=Path(member['review']);canonical=root/'recordings'/member['recording_id']
                if sha(case/'trace.json')!=r['input_trace_sha256'] or sha(canonical/'trace.json')!=r['input_trace_sha256'] or sha(case/'metadata.json')!=r['metadata_sha256']:
                    raise ValueError('Collection changed after staging: '+member['recording_id'])
            with ThreadPoolExecutor(max_workers=min(workers,16))as pool:list(pool.map(check_current,members))
            def publish(member):
                publish_reconstructed(root,archive,member,by_id[member['recording_id']],manifest_changed=manifest_changed,
                                      publication=frozen_publication[member['recording_id']])
                print(json.dumps({'published_recording':member['recording_id']}),flush=True)
            with reconstruction_publication(root,archive,members,extra_paths=generation_paths):
                with ThreadPoolExecutor(max_workers=min(workers,16))as pool:list(pool.map(publish,members))
                refresh(root)
                refresh_reports(root)
                summary['report_outputs_sha256']={str(path.relative_to(root)):sha(path) for path in
                    (Path(p) if Path(p).is_absolute() else root/p for p in report_paths) if path.is_file()}
                if not summary['report_outputs_sha256']:
                    raise ValueError('Report generation produced no declared current outputs')
                summary['label_records_sha256']={member['recording_id']:sha(root/'recordings'/member['recording_id']/'evidence/expected_label.json') for member in members}
                summary['published']=True
                summary['elapsed_seconds']=time.monotonic()-started
                atomic(root/'inputs/shared/reconstruction.json',summary)
    atomic(archive/'summary.json',summary)
    return summary


def validate_review_archive(root, archive, repo=None):
    """Require backups outside active outputs and maintained repositories."""
    if archive is None:raise ValueError('An external review archive is required')
    root=Path(root).resolve();archive=Path(archive).resolve()
    protected=[root,Path(__file__).resolve().parents[1]]
    if repo is not None:protected.append(Path(repo).resolve())
    if any(archive==p or p in archive.parents or archive in p.parents for p in protected):
        raise ValueError('Review archive must be outside active outputs and repositories')
    return archive


def publish_review_links(root, member, archive):
    """Publish accepted outputs through complete, canonical-linked work folders."""
    root=Path(root).resolve();archive=validate_review_archive(root,archive)
    rid=safe_name(member['recording_id']);canonical=root/'recordings'/rid
    archive=archive/'review-links'/rid
    recover_reconstruction_publication(root,archive)
    value=verify_recording(canonical,require_label=True)
    authority=verified_label(canonical,value)
    if (value.get('recording_id')!=rid or value.get('case_id')!=member['case_id']
            or authority['target_law_id']!=member['law_id']
            or value.get('law_id',member['law_id'])!=member['law_id']
            or value.get('cell_id')!=member['cell_id']):
        raise ValueError('Canonical review identity differs: '+rid)
    names=('video.webm','trace.json','manifest.json','metadata.json')
    if not (canonical/'manifest.json').is_file():raise ValueError('Canonical manifest missing: '+rid)
    directories=[]
    for raw in member.get('reviews',[member.get('review')]):
        if raw is None:raise ValueError('Review path missing: '+rid)
        path=Path(raw);case=(path if path.is_absolute()else root/path).resolve()
        if root/'work' not in case.parents:raise ValueError('Review path escapes work tree')
        if case in directories:continue
        if case.exists():
            if not case.is_dir()or set(p.name for p in case.iterdir())-set(names):
                raise ValueError('Unexpected review folder contents: '+str(case))
            if (case/'metadata.json').is_file():
                old=json.loads((case/'metadata.json').read_text())
                if any(old.get(k)!=member[k]for k in ('recording_id','case_id','law_id')):
                    raise ValueError('Existing review identity differs: '+str(case))
        directories.append(case)
    if not directories:raise ValueError('No review folders to publish')
    expected=dict(value,law_id=member['law_id'],delivery_layout='canonical-recording-links-v1',
                  manifest_sha256=sha(canonical/'manifest.json'))
    def check(case):
        for name in names:
            path=case/name;relative=os.path.relpath(canonical/name,case)
            if not path.is_symlink()or os.readlink(path)!=relative or path.resolve()!=(canonical/name).resolve():
                raise ValueError('Review is not linked to its canonical output: '+str(path))
        current=json.loads((case/'metadata.json').read_text())
        if current!=expected:raise ValueError('Review metadata differs from canonical acceptance')
        for name,key in (('video.webm','video_sha256'),('trace.json','trace_sha256'),('manifest.json','manifest_sha256')):
            if sha(case/name)!=current[key]:raise ValueError('Review output hash differs: '+str(case/name))
    if value==expected:
        try:
            for case in directories:check(case)
        except ValueError:pass
        else:return {'recording_id':rid,'reviews':[str(p)for p in directories],'changed':False}
    archive.mkdir(parents=True,exist_ok=True)
    extra=[canonical/'metadata.json']+[case/name for case in directories for name in names]
    swaps=[]
    with locked(root/'state'/('review-links-'+rid+'.lock')):
        with reconstruction_publication(root,archive,[],extra_paths=extra):
            ready=[]
            for index,case in enumerate(directories):
                stage=archive/('ready-'+str(index));prior=archive/('prior-'+str(index))
                if stage.exists()or prior.exists():raise ValueError('Use a fresh external review archive')
                stage.mkdir()
                if stage.stat().st_dev!=case.parent.stat().st_dev:
                    raise ValueError('Review commit staging must share the output filesystem')
                for name in names:(stage/name).symlink_to(os.path.relpath(canonical/name,case))
                ready.append((case,stage,prior))
            try:
                atomic(canonical/'metadata.json',expected)
                for case,stage,prior in ready:
                    existed=case.exists()
                    if existed:case.rename(prior)
                    swaps.append((case,stage,prior,existed));stage.rename(case)
                for case in directories:check(case)
            except BaseException:
                for case,stage,prior,existed in reversed(swaps):
                    if case.exists():case.rename(stage)
                    if existed:prior.rename(case)
                raise
    return {'recording_id':rid,'reviews':[str(p)for p in directories],'changed':True,
            'metadata_sha256':sha(canonical/'metadata.json'),'backup_journal':str(archive/'publication.json')}


def publish_reconstructed(root, archive, member, report, *, manifest_changed=False, publication=None):
    """Archive superseded derivatives; original evidence and membership stay put."""
    from shared_manifest import verify as verify_manifest, link as link_manifest
    root,archive=Path(root),Path(archive)
    rid=member['recording_id'];canonical=root/'recordings'/rid;review=Path(member['review'])
    if publication is None and json.loads((canonical/'metadata.json').read_text()).get('delivery_layout')=='canonical-recording-links-v1':
        raise ValueError('Accepted linked outputs require complete final publication inputs')
    authority=_verified_publication_inputs(root,member,report,publication) if publication is not None else None
    staged_manifest=archive/'manifest.json'
    capability=json.loads(staged_manifest.read_text()) if staged_manifest.is_file() else None
    manifest_hash=sha(staged_manifest if staged_manifest.is_file() else root/'inputs/shared/manifest.json')
    if publication is not None:
        profile=json.loads(Path(publication['adapter_report']['path']).read_text())
        if profile.get('manifest_sha256')!=manifest_hash:
            raise ValueError('Staged profile is bound to a stale manifest: '+rid)
    def preserve(path):
        if not path.exists():return
        target=archive/'superseded'/path.relative_to(root)
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():shutil.copy2(path,target)
        if sha(target)!=sha(path):
            raise ValueError('Superseded artifact backup differs from the current input: '+str(path))
    def install(path,source,checksum):
        preserve(path);temp=path.with_name(path.name+'.reconstruct-tmp')
        try:
            shutil.copyfile(source,temp)
            if sha(temp)!=checksum:raise ValueError('Staged publication bytes changed during installation: '+str(source))
            temp.replace(path)
        finally:temp.unlink(missing_ok=True)
    reviews=[Path(p) for p in member.get('reviews',[member['review']])]
    for case in reviews:
        expected=report.get('review_inputs',{}).get(str(case),{})
        metadata_hash=expected.get('metadata_sha256',report['metadata_sha256'] if case==review else None)
        if sha(case/'trace.json')!=report['input_trace_sha256'] or sha(case/'metadata.json')!=metadata_hash:
            raise ValueError('Review copy changed after staging: '+str(case))
    if sha(review/'trace.json')!=report['input_trace_sha256']:
        raise ValueError('Review changed after staging: '+rid)
    if sha(review/'metadata.json')!=report['metadata_sha256']:
        raise ValueError('Review metadata changed after staging: '+rid)
    if sha(canonical/'trace.json')!=report['input_trace_sha256']:
        raise ValueError('Canonical/review trace mismatch: '+rid)
    if publication is None and not report['changed'] and not manifest_changed:
        previous=json.loads((canonical/'adapter_report.json').read_text()).get('reconstruction',{}) if (canonical/'adapter_report.json').exists()else{}
        if previous.get('source_key')==report['source_key']and previous.get('static_inventory_receipt')==report.get('static_inventory_receipt'):return
    stage=archive/'stage'/rid
    if report['changed'] and sha(stage/'trace.json')!=report['output_trace_sha256']:raise ValueError('Staged output changed: '+rid)
    output_directories=[canonical,canonical/'evidence/traffic_spec']if authority is not None else [canonical]+reviews+[canonical/'evidence/traffic_spec']
    for directory in dict.fromkeys(output_directories):
        if not directory.exists():continue
        current_manifest=directory/'manifest.json'
        if sha(current_manifest)!=manifest_hash:
            preserve(current_manifest)
            current_manifest.unlink()
            link_manifest(root,directory,capability)
        verify_manifest(root,directory,manifest_hash)
        if report['changed']:install(directory/'trace.json',stage/'trace.json',report['output_trace_sha256'])
        report_path=canonical/'adapter_report.json' if directory in reviews else directory/'adapter_report.json'
        if directory in reviews:
            auxiliary=directory/'adapter_report.json'
            if auxiliary.exists():preserve(auxiliary);auxiliary.unlink()
        elif publication is not None:
            install(report_path,publication['adapter_report']['path'],publication['adapter_report']['sha256'])
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
            if authority is not None:
                from production_verdicts import presentation
                projection=presentation(authority)
                for source in (value,value.get('acceptance',{}),value.get('published_record',{}),value.get('source_record',{})):
                    if isinstance(source,dict):
                        source.update(label_record=projection,expected_label=authority['expected_label'],judgment_sweep=authority['judgment_sweep'])
            value['reconstruction']={'decoder_passed':True,'source_key':report['source_key'],
                'report':str(report_path.relative_to(root)),'report_sha256':sha(report_path),
                'original_trace_sha256':report['input_trace_sha256']}
            prior={k:value.pop(k) for k in ('offline_repair','b_repair') if k in value}
            if report['changed'] or manifest_changed:prior.update({k:value.pop(k) for k in ('trace_migration','intention_validation') if k in value})
            if prior:value['reconstruction']['superseded_validation']=prior
            for key in ('acceptance','published_record','source_record'):
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
    if authority is not None:
        install(canonical/'evidence/expected_label.json',publication['expected_label']['path'],publication['expected_label']['sha256'])
        verified_label(canonical,json.loads((canonical/'metadata.json').read_text()))
    checks=canonical/'evidence-checksums.json'
    completion_path=canonical/'evidence/result.json'
    if authority is not None or checks.exists() or completion_path.exists():
        preserve(checks)
        if checks.exists():values=json.loads(checks.read_text())
        else:values={'evidence/'+k:v for k,v in (json.loads(completion_path.read_text()).get('completion',{}).get('artifact_hashes',{}) if completion_path.exists() else {}).items()}
        for name in ('trace.json','adapter_report.json','manifest.json'):
            path=canonical/'evidence/traffic_spec'/name
            if path.exists():values['evidence/traffic_spec/'+name]=sha(path)
        if authority is not None:values['evidence/expected_label.json']=sha(canonical/'evidence/expected_label.json')
        atomic(checks,values)
    if authority is not None and profile.get('device_projection') is not None:
        from traffic_spec_adapter.inventory_observations import Evidence
        from traffic_spec_adapter.adapter import retained_signal_bindings
        evidence=Evidence(canonical)
        for name in ('capture/manifest.json','capture/native/frames.jsonl','capture/evidence.jsonl'):
            if evidence.path(name) is None:
                raise ValueError('Final device projection source is unavailable: '+name)
        retained_signal_bindings(evidence,canonical/'trace.json')
        if evidence.problems:
            raise ValueError('Final device projection lacks verified source joins: '+'; '.join(evidence.problems))

    if authority is not None:
        publish_review_links(root,member,archive)


def _verified_publication_inputs(root, member, report, publication):
    """Check frozen evaluator/profile bytes without manufacturing an outcome."""
    from traffic_spec_adapter.atom_contract import common_profile_complete
    rid=member['recording_id'];canonical=Path(root)/'recordings'/rid
    if not report.get('decoder_passed') or not common_profile_complete(report):
        raise ValueError('Final publication requires complete common observations and Core validation: '+rid)
    if not report.get('canonical_inputs'):
        raise ValueError('Staged publication lacks canonical input bindings: '+rid)
    for name,checksum in report['canonical_inputs'].items():
        path=canonical/name
        if (sha(path) if path.is_file() else None)!=checksum:
            raise ValueError('Canonical publication input changed: '+name)
    for name in ('expected_label','adapter_report'):
        item=publication[name]
        if sha(item['path'])!=item['sha256']:
            raise ValueError('Staged publication input changed: '+name)
    profile_path=Path(publication['adapter_report']['path'])
    profile=json.loads(profile_path.read_text())
    if not common_profile_complete(profile):
        raise ValueError('Staged final profile is incomplete: '+rid)
    if profile.get('trace_sha256',profile.get('output_trace_sha256'))!=report['output_trace_sha256']:
        raise ValueError('Staged profile is bound to a stale trace: '+rid)
    previous_projection=None
    for path in (canonical/'evidence/traffic_spec/adapter_report.json',canonical/'adapter_report.json'):
        if path.is_file():
            previous_projection=json.loads(path.read_text()).get('device_projection') or previous_projection
    projection=profile.get('device_projection')
    if previous_projection is not None and projection is None:
        raise ValueError('Final profile drops the native device source projection: '+rid)
    if projection is not None and projection.get('trace_sha256')!=report['output_trace_sha256']:
        raise ValueError('Final device source projection is bound to a stale trace: '+rid)
    reconstruction=profile.get('reconstruction',{})
    if (not reconstruction.get('decoder_passed') or reconstruction.get('output_trace_sha256')!=report['output_trace_sha256']
            or reconstruction.get('source_key')!=report['source_key']):
        raise ValueError('Staged profile lacks the final reconstruction validation: '+rid)
    metadata=json.loads((canonical/'metadata.json').read_text())
    identity_metadata={key:metadata.get(key) for key in ('case_id','law_id')}
    authority=verified_label(canonical,identity_metadata,trace_sha256=report['output_trace_sha256'],
        authority_path=publication['expected_label']['path'],adapter_report_path=profile_path)
    if authority['source_hashes'].get('adapter_report_sha256')!=publication['adapter_report']['sha256']:
        raise ValueError('Final authority must bind the staged profile: '+rid)
    return authority


def stage_recapture(root, parent_id, source_attempt, staging_root, *, definition,
                    trace, profile, manifest, video, validation, derived_evidence=None):
    """Stage a sealed DB-free physical acquisition; acceptance is a separate call.

    ``validation`` supplies path/sha256 plus adapter_report_sha256,
    video_sha256 and frame_map_sha256, binding the independently completed
    source/media/Core validation to these exact outputs. The physical ID binds
    only immutable acquisition bytes and its actual parent, never export bytes,
    validation receipts, staging paths, or an invented job/campaign.

    Raw sealed files remain at evidence/. Additional/different files from a
    validated offline evidence view remain under validation-projection/ with
    their own inventory; its result never replaces the sealed original result.
    This does not install a canonical output or change any set membership.
    """
    from batch_pipeline.completion import verify as verify_completion
    from traffic_spec_adapter.atom_contract import common_profile_complete
    root,source,staging=map(lambda p:Path(p).resolve(),(root,source_attempt,staging_root))
    parent_id=safe_name(parent_id);parent=root/'recordings'/parent_id
    if staging==root or root in staging.parents or staging==source or source in staging.parents or staging in source.parents:
        raise ValueError('Recapture staging must be separate from active outputs and original acquisition')
    parent_metadata=json.loads((parent/'metadata.json').read_text())
    if parent_metadata.get('recording_id')!=parent_id:raise ValueError('Parent recording identity differs')
    definition,trace,profile,manifest,video=map(Path,(definition,trace,profile,manifest,video))
    definition_hash=sha(definition);case=json.loads(definition.read_text())
    inventory=json.loads((parent/'evidence-checksums.json').read_text())
    if inventory.get('evidence/accepted_case_definition.json')!=definition_hash:
        raise ValueError('Frozen recapture definition lacks parent source binding')
    law=parent_metadata.get('law_id') or parent_metadata.get('published_record',{}).get('law_id')
    if case.get('case_id')!=parent_metadata.get('case_id') or case.get('target_law_id')!=law:
        raise ValueError('Recapture definition changes parent semantic identity')
    result=json.loads((source/'result.json').read_text());completion=result.get('completion',{})
    binding=completion.get('binding',{})
    verify_completion(source,binding)
    if binding.get('parent_recording_id')!=parent_id or binding.get('case_id')!=case['case_id']:
        raise ValueError('Sealed recapture binding disagrees with parent/case')
    if not binding.get('operation') or not binding.get('batch'):
        raise ValueError('Sealed recapture requires its actual operation and batch')
    for field in ('cell_id','actor','case_id'):
        if result.get(field)!=parent_metadata.get(field):raise ValueError('Recapture source changes semantic '+field)
    config=json.loads((source/'config.json').read_text())
    if config.get('target_law_id')!=law or config.get('case_id')!=case['case_id']:
        raise ValueError('Sealed recapture configuration changes law/case identity')
    capture=json.loads((source/'capture/manifest.json').read_text())
    if capture.get('acquisition')!='original_live_run' or capture.get('diagnostic_fixture'):
        raise ValueError('Recapture staging requires a real original physical acquisition')
    if result.get('requested_variable_assignments')!=case.get('variable_assignments'):
        raise ValueError('Executed recapture assignments differ from frozen case')
    if result.get('episode_definition')!=case.get('episode_definition'):
        raise ValueError('Executed recapture episode differs from frozen case')
    profile_value=json.loads(profile.read_text());proof_path=Path(validation['path'])
    if sha(proof_path)!=validation['sha256']:raise ValueError('Recapture validation receipt changed')
    proof=json.loads(proof_path.read_text())
    frames=profile_value.get('frames')
    expected={'parent_recording_id':parent_id,'case_id':case['case_id'],
        'original_result_sha256':sha(source/'result.json'),'trace_sha256':sha(trace),
        'manifest_sha256':sha(manifest),'frames':frames}
    if any(proof.get(k)!=v for k,v in expected.items()):raise ValueError('Recapture validation source/output binding differs')
    if (not common_profile_complete(profile_value) or not profile_value.get('decoder_validation',{}).get('passed')
            or any(proof.get(key)is not True for key in ('execution_media_validated','common_profile_passed','decoder_passed','all_targets_matched','original_result_unchanged'))
            or proof.get('rebuild_required')is not False or type(frames)is not int or frames<1):
        raise ValueError('Recapture source/media/common profile/Core validation is incomplete')
    if sha(profile)!=validation['adapter_report_sha256'] or sha(video)!=validation['video_sha256'] or sha(source/'video_frames.jsonl')!=validation['frame_map_sha256']:
        raise ValueError('Recapture profile/media validation hashes differ')
    video_relative=video.resolve().relative_to(source)
    if str(video_relative)not in result.get('video_references',[]) or completion['artifact_hashes'].get(str(video_relative))!=sha(video):
        raise ValueError('Recapture primary media is not sealed original evidence')
    if proof.get('video_frames')!=[frames]*len(result['video_references']):raise ValueError('Recapture full media/frame coverage differs')
    projection=profile_value.get('device_projection',{})
    if projection.get('schema')!='device-source-projection-v1' or projection.get('diagnostic_fixture')is not False:
        raise ValueError('Recapture requires a physical original device projection')
    for key,path in [('trace_sha256',trace),('capture_manifest_sha256',source/'capture/manifest.json'),
                     ('frame_index_sha256',source/'capture/native/frames.jsonl'),('capture_evidence_sha256',source/'capture/evidence.jsonl')]:
        if projection.get(key)!=sha(path):raise ValueError('Recapture device projection source binding differs: '+key)
    for key,name in [('capture_evidence','capture/evidence.jsonl'),('frame_index','capture/native/frames.jsonl'),
                     ('original_telemetry','trace.jsonl'),('capture_manifest','capture/manifest.json')]:
        if profile_value.get('inputs',{}).get(key,{}).get('sha256')!=sha(source/name):
            raise ValueError('Final export does not bind original acquisition source: '+key)
    physical={'format':'sealed-recapture-acquisition-v1','parent_recording_id':parent_id,
        'definition_sha256':definition_hash,'original_result_sha256':sha(source/'result.json'),
        'original_capture_sha256':sha(source/'trace.jsonl'),
        'original_capture_manifest_sha256':sha(source/'capture/manifest.json'),
        'completion_binding_sha256':identity(binding)}
    rid=identity(physical)
    if rid==parent_id:raise ValueError('Recapture must have a distinct physical identity')
    raw=dict(completion['artifact_hashes']);raw['result.json']=physical['original_result_sha256']
    if 'expected_label.json'in raw:raise ValueError('Stage fresh physical sources before outcome authority registration')
    derived={};derived_base=Path(derived_evidence).resolve()if derived_evidence is not None else None
    if derived_base is not None:
        for path in sorted(derived_base.rglob('*')):
            if not path.is_file():continue
            resolved=path.resolve()
            if derived_base not in resolved.parents:raise ValueError('Derived source link escapes its evidence view')
            name=str(path.relative_to(derived_base));checksum=sha(path)
            if raw.get(name)!=checksum:derived[name]=checksum
    # Explicitly verify every final export input before retaining its provenance.
    for value in profile_value.get('inputs',{}).values():
        path=Path(value['path']).resolve()
        if source not in path.parents and (derived_base is None or derived_base not in path.parents):
            raise ValueError('Final export source escapes acquisition/validated evidence view')
        if sha(path)!=value['sha256']:raise ValueError('Final export source changed')
    source_manifest={'physical_acquisition':physical,'raw_artifact_sha256':raw,
        'derived_projection_artifact_sha256':derived,'parent_metadata_sha256':sha(parent/'metadata.json'),
        'definition_sha256':definition_hash,'validation_receipt_sha256':validation['sha256'],
        'final_artifacts_sha256':{'trace.json':sha(trace),'adapter_report.json':sha(profile),'manifest.json':sha(manifest),'video.webm':sha(video)},
        'primary_video_source':str(video_relative),'frame_map_sha256':validation['frame_map_sha256']}
    target=staging/'recordings'/rid
    if target.exists():
        if json.loads((target/'recapture-source-manifest.json').read_text())!=source_manifest:
            raise ValueError('Recapture staging identity collision or changed staged inputs')
        metadata=json.loads((target/'metadata.json').read_text())
        if metadata.get('recapture',{}).get('physical_acquisition')!=physical:
            raise ValueError('Recapture staging identity collision')
        for name,checksum in json.loads((target/'evidence-checksums.json').read_text()).items():
            if target.resolve() not in (target/name).resolve().parents:
                raise ValueError('Staged recapture evidence link escapes its recording')
            if sha(target/name)!=checksum:raise ValueError('Staged recapture bytes changed')
        return target/'evidence'
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=Path(tempfile.mkdtemp(prefix='.recapture-',dir=target.parent))
    def copy(source_path,relative,checksum):
        path=temporary/relative;path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source_path,path)
        if sha(path)!=checksum:raise ValueError('Recapture source changed during staging')
    try:
        for name,checksum in raw.items():
            relative=Path(name);path=(source/relative).resolve()
            if relative.is_absolute() or '..'in relative.parts or source not in path.parents:
                raise ValueError('Sealed recapture source path escapes acquisition')
            copy(path,'evidence/'+name,checksum)
        for name,checksum in derived.items():copy(derived_base/name,'evidence/validation-projection/'+name,checksum)
        for name,path in [('trace.json',trace),('adapter_report.json',profile),('manifest.json',manifest)]:
            if 'traffic_spec/'+name in raw:raise ValueError('Recapture export would replace a sealed original source')
            copy(path,'evidence/traffic_spec/'+name,source_manifest['final_artifacts_sha256'][name])
        copy(definition,'evidence/accepted_case_definition.json',definition_hash)
        copy(manifest,'manifest.json',sha(manifest))
        copy(proof_path,'evidence/recapture-validation.json',validation['sha256'])
        copy(parent/'metadata.json','parent-metadata.json',source_manifest['parent_metadata_sha256'])
        atomic(temporary/'recapture-source-manifest.json',source_manifest)
        checks={'evidence/'+name:checksum for name,checksum in raw.items()}
        checks.update({'evidence/validation-projection/'+name:checksum for name,checksum in derived.items()})
        checks.update({'evidence/traffic_spec/'+name:sha(path)for name,path in [('trace.json',trace),('adapter_report.json',profile),('manifest.json',manifest)]})
        checks.update({'evidence/accepted_case_definition.json':definition_hash,'evidence/recapture-validation.json':validation['sha256'],
            'parent-metadata.json':source_manifest['parent_metadata_sha256'],'recapture-source-manifest.json':sha(temporary/'recapture-source-manifest.json')})
        atomic(temporary/'evidence-checksums.json',checks)
        metadata={key:parent_metadata[key]for key in ('cell_id','actor','case_id','campaign')if key in parent_metadata}
        metadata.update(recording_id=rid,status='recording',law_id=law,parent_recording_id=parent_id,
            manifest_sha256=sha(manifest),recapture={'physical_acquisition':physical,'source_manifest_sha256':sha(temporary/'recapture-source-manifest.json'),
                'parent_metadata_sha256':source_manifest['parent_metadata_sha256'],'pending_explicit_acceptance':True},
            phases={'staging':{'status':'pending_acceptance'}})
        atomic(temporary/'metadata.json',metadata)
        temporary.rename(target)
    finally:
        if temporary.exists():shutil.rmtree(temporary)
    return target/'evidence'
