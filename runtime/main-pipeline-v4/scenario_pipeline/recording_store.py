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
    atomic(path, value)
    return folder.name


def verify_recording(folder):
    folder = Path(folder)
    value = json.loads((folder / 'metadata.json').read_text())
    if value.get('status') != 'accepted':
        raise ValueError('Recording is not accepted: ' + folder.name)
    for name, key in [('video.webm', 'video_sha256'), ('trace.json', 'trace_sha256')]:
        if not value.get(key) or sha(folder / name) != value[key]:
            raise ValueError('Recording changed: ' + str(folder / name))
    # Migration manifests bind every unique evidence file, including frozen receipts.
    inventory = folder / 'evidence-checksums.json'
    if inventory.exists():
        base=folder.resolve()
        def check(item):
            name,expected=item
            path=(base/name).resolve()
            if base not in path.parents or sha(path)!=expected:
                raise ValueError('Evidence changed: '+str(path))
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
            atomic(staging / 'manifest.json', manifest)
            with (staging / 'cases.csv').open('w', newline='') as stream:
                fields = ['campaign', 'law_id', 'cell_id', 'actor', 'case_id', 'split', 'status', 'recording_id', 'video', 'trace']
                writer = csv.DictWriter(stream, fields, extrasaction='ignore')
                writer.writeheader(); writer.writerows(rows)
            hashes = {p.name: sha(p) for p in staging.iterdir()}
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
    manifest = json.loads((directory / 'manifest.json').read_text())
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
        atomic(stage / 'manifest.json', packaged)
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
