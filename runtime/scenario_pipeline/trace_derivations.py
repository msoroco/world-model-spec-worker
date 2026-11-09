"""Verify saved trace-format derivations without rewriting capture certificates.

Hashes bind every link; permitted transformations are checked against every source
frame. No arbitrary replacement can be accepted by merely writing a receipt.
"""
import copy
from functools import lru_cache
from itertools import zip_longest
import json
from pathlib import Path
from recording_store import sha
from trace_json import scenes

LEGACY = {'asm.preparing_left_turn':'int.preparing_left_turn',
          'asm.exit_intent_left':'int.exit_intent_left',
          'asm.exit_intent_right':'int.exit_intent_right',
          'asm.exit_intent_u_turn':'int.exit_intent_u_turn'}
ALIASES = {'asm.authored_divided_highway','asm.authored_one_way_carriageway_designation',
           'asm.structural_posted_maximum_20mph'}


def inside(root, path):
    p=Path(path)
    p=(p if p.is_absolute() else root/p).resolve()
    if root not in p.parents:raise ValueError('Trace derivation path escapes recording store')
    return p


def _check(condition, message):
    if not condition:raise ValueError('Invalid trace derivation: '+message)


@lru_cache(maxsize=128)
def _prove(old_path,new_path,old_hash,new_hash,receipt_text):
    # Caller rehashes both files and all dependencies before using this cache.
    receipt=json.loads(receipt_text);kind=receipt.get('format');n=0
    for olditem,newitem in zip_longest(scenes(old_path),scenes(new_path)):
        _check(olditem is not None and newitem is not None,'frame count changed')
        old,_=olditem;new,_=newitem;expected=dict(old);n+=1
        if kind=='trace-only-scene-intent-migration-v1':
            spec=receipt['mapping'];keys=spec.get('intent_keys',[]);aliases=spec.get('remove_aliases',{})
            _check(set(keys)<=set(LEGACY) and set(aliases)<=ALIASES,'unapproved mapping')
            pairs=dict(old.get('assumptions',[]));remove=set(keys)|set(aliases)
            _check(remove<=set(pairs),'missing source declarations')
            for key,binding in aliases.items():
                _check(pairs[key] is True,'negative structural alias is not supported')
                if key=='asm.structural_posted_maximum_20mph':
                    ids=binding.get('device_ids',[]);devices={d['id']:d for d in old['devices']}
                    _check(len(ids)==2 and len(set(ids))==2,'missing posting identities')
                    for ident in ids:
                        d=devices.get(ident,{})
                        _check(d.get('kind')=='speed_limit_sign' and d.get('speed_kind')=='maximum'
                               and abs(d.get('speed_value',-1)-8.9408)<1e-8 and bool(d.get('governs')),'posting equivalence')
                else:
                    ids=binding.get('region_ids',[]);regions={r['id']:r for r in old['structures']}
                    want='median_or_divider' if key=='asm.authored_divided_highway' else 'one_way_roadway'
                    _check(bool(ids) and all(regions.get(i,{}).get('kind')==want for i in ids),'structural equivalence')
                    if want=='median_or_divider':_check(any(regions[i].get('opening') is False for i in ids),'no physical divider')
            expected['assumptions']=[p for p in old.get('assumptions',[]) if p[0] not in remove]
            if keys:
                _check('intents' not in old,'unexpected original intentions')
                entry={'vehicle':old['subject']}
                if spec.get('intent_target') is not None:
                    _check(spec['intent_target'] in {s['id'] for s in old['structures']},'missing original target')
                    entry['target']=spec['intent_target']
                entry.update(source='authored_scenario',values=[[LEGACY[k],pairs[k]] for k in LEGACY if k in keys])
                expected['intents']=[entry]
        elif kind=='intentions-core-reconcile-v1':
            _check(receipt.get('operation')=='omit_unscoped_intent','unapproved reconciliation')
            _check(receipt.get('cell_id')=='C230281' and receipt.get('case_id') in
                   ('C230281-bus-above-55','C230281-bus-below-55'),'unapproved targetless source')
            _check(old.get('intents')==[{'vehicle':old['subject'],'source':'authored_scenario',
                                        'values':[['int.preparing_left_turn',False]]}], 'not the approved unscoped declaration')
            expected['intents']=[]
        else:raise ValueError('Unsupported trace derivation format: '+str(kind))
        _check(json.dumps(new,sort_keys=True,separators=(',',':'),allow_nan=False)==
               json.dumps(expected,sort_keys=True,separators=(',',':'),allow_nan=False),
               'unrelated data or declaration values changed')
    _check(n==receipt.get('frames'),'receipt frame count mismatch')
    return True


def verify_trace_origin(folder, metadata, expected_hash, root):
    """Prove current bytes descend from the certificate's original trace bytes."""
    root=Path(root).resolve();folder=Path(folder).resolve();current=folder/'trace.json'
    current_hash=sha(current)
    _check(current_hash==metadata.get('trace_sha256'),'current trace hash mismatch')
    reference=metadata.get('trace_migration');seen=set()
    while current_hash!=expected_hash:
        _check(isinstance(reference,dict) and len(seen)<16,'missing or excessive chain')
        receipt_path=inside(root,reference.get('receipt',reference.get('path','')))
        receipt_hash=sha(receipt_path)
        _check(receipt_hash==reference.get('receipt_sha256',reference.get('sha256')),'receipt hash mismatch')
        _check(receipt_hash not in seen,'cyclic chain');seen.add(receipt_hash)
        receipt=json.loads(receipt_path.read_text())
        _check(receipt.get('recording_id')==folder.name,'wrong recording identity')
        _check(receipt.get('trace_sha256')==current_hash,'broken current hash link')
        original=inside(root,receipt.get('original_trace',''))
        # Workspace cleanup can remove the migration's redundant archive link.
        # The same recording's immutable adapter evidence is an exact-byte fallback,
        # only when its hash matches the untouched historical receipt.
        if not original.is_file():
            original=inside(root,folder/'evidence/traffic_spec/trace.json')
        original_hash=sha(original)
        _check(original_hash==receipt.get('original_trace_sha256'),'source hash mismatch')
        for path,record in receipt.get('mapping',{}).get('sources',{}).items():
            _check(sha(inside(root,path))==record['sha256'],'source dependency changed')
        _prove(str(original),str(current),original_hash,current_hash,json.dumps(receipt,sort_keys=True))
        current,current_hash=original,original_hash
        reference=receipt.get('previous_receipt')
    return True
