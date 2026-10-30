"""Versioned law-corpus partitions and auditable recording membership changes."""
import json
from pathlib import Path
from pipeline_paths import OUTPUT_ROOT
from recording_store import identity, sha


def active_manifest(root=None):
    root=Path(root) if root is not None else OUTPUT_ROOT
    transaction=root/'state/law-split-transaction.json'
    if transaction.exists() and json.loads(transaction.read_text()).get('status')=='applying':
        raise ValueError('Law-split activation is in progress; retry after cutover')
    pointer=root/'sets/index.json'
    if not pointer.exists(): return None
    index=json.loads(pointer.read_text())
    ref=index.get('law_split_manifest')
    if not ref:return None
    path=(root/ref).resolve()
    if root.resolve() not in path.parents or sha(path)!=index.get('law_split_manifest_sha256'):
        raise ValueError('Active law-split manifest changed')
    return json.loads(path.read_text())


def law_partition(law_id,root=None):
    manifest=active_manifest(root)
    if not manifest:return None
    if law_id in manifest['training_law_ids']:return 'training'
    if law_id in manifest['heldout_law_ids']:return 'heldout'
    raise ValueError('Law is outside the active corpus: '+law_id)


def assignment_allowed(law_id,cell,actor,split,root=None):
    root=Path(root) if root is not None else OUTPUT_ROOT
    manifest=active_manifest(root)
    if not manifest:return True
    expected='heldout' if split=='heldout' else 'training'
    if law_partition(law_id,root)!=expected:return False
    scope=json.loads((root/'sets'/{'training':'full-train','testing':'full-test','heldout':'held-out'}[split]/'scope.json').read_text())
    return any(a['law_id']==law_id and a['cell_id']==cell and a['actor']==actor for a in scope['assignments'])


def validate_partition_migration(member,metadata,root=None):
    root=Path(root) if root is not None else OUTPUT_ROOT
    reference=member.get('partition_migration_receipt')
    if not reference:return False
    manifest=active_manifest(root)
    if not manifest or reference.get('sha256') not in manifest['membership_migrations']:
        raise ValueError('Unregistered partition migration')
    path=(root/reference['path']).resolve()
    if root.resolve() not in path.parents or sha(path)!=reference['sha256']:
        raise ValueError('Partition-migration receipt changed')
    receipt=json.loads(path.read_text())
    if receipt['version']!=manifest['version']:raise ValueError('Wrong partition policy')
    source=receipt['source_member'];target=receipt['target_identity']
    for key in ('recording_id','law_id','cell_id','actor','case_id','campaign'):
        if member.get(key)!=target.get(key) or source.get(key)!=target.get(key):
            raise ValueError('Partition migration cannot change '+key)
    if member['split']!=receipt['target_split']:raise ValueError('Wrong migrated split')
    expected='heldout' if member['split']=='heldout' else 'training'
    if law_partition(member['law_id'],root)!=expected:raise ValueError('Migration conflicts with active corpus')
    if metadata.get('split') in ('training','testing','heldout') and metadata['split']!=source['split']:
        raise ValueError('Capture-time split differs from receipt source')
    if metadata.get('video_sha256')!=receipt['video_sha256']:
        raise ValueError('Partition migration video payload changed')
    if metadata.get('trace_sha256')!=receipt['trace_sha256']:
        from trace_derivations import verify_trace_origin
        verify_trace_origin(root/'recordings'/member['recording_id'],metadata,receipt['trace_sha256'],root)
    snapshot=(root/receipt['source_selection']).resolve()
    if root.resolve() not in snapshot.parents or sha(snapshot)!=receipt['source_selection_sha256']:
        raise ValueError('Original membership snapshot changed')
    before=json.loads(snapshot.read_text())
    if source not in before['members']:raise ValueError('Original membership not found')
    return True
