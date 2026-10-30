"""Apply validated supplemental test bindings as a versioned scope extension."""
from pathlib import Path
import shutil
from .common import read, write, sha, digest


def _link_selections(root, version, batch_id, proposed):
    """Version frozen selections when their referenced scopes are extended."""
    receipt_path = version/'selection-link-receipt.json'
    result = {}
    for sid, scope in proposed.items():
        path = root/'sets'/sid/'selection.json'
        before_scope = read(version/(sid+'-before.json'))
        prior_hash, next_hash = digest(before_scope), digest(scope)
        current = read(path)
        archive = version/(sid+'-selection-before.json')
        after = version/(sid+'-selection-after.json')
        if current.get('scope_sha256') == prior_hash:
            if archive.exists() and sha(archive) != sha(path):
                raise ValueError('Frozen selection differs from archived predecessor: '+sid)
            if not archive.exists():
                shutil.copy2(path, archive)
            updated = dict(current, scope_sha256=next_hash,
                           selection_version='worker-coverage-'+batch_id)
            if after.exists() and read(after) != updated:
                raise ValueError('Selection extension differs from frozen successor: '+sid)
            if not after.exists():
                write(after, updated)
            write(path, updated)
            current = updated
        if current.get('scope_sha256') != next_hash or read(after) != current or not archive.exists():
            raise ValueError('Frozen selection does not match extended scope: '+sid)
        result[sid] = {'before_sha256': sha(archive), 'after_sha256': sha(path),
                       'members': len(current['members'])}
    receipt = {'batch_id': batch_id, 'selections': result}
    if receipt_path.exists():
        if read(receipt_path) != receipt:
            raise ValueError('Selection-link receipt changed')
    else:
        write(receipt_path, receipt)
    return receipt


def apply(root, repo, batch_id):
    from .exchange import check_return
    from .branch_coverage import assignments, assignment_path
    root, repo = Path(root).resolve(), Path(repo).resolve()
    checked = check_return(root, repo, batch_id)
    batch = read(repo/'batch.json'); items = assignments(repo,batch)
    additional = [read(assignment_path(repo,aid,item)) for aid,item in items.items() if item.get('supplemental')]
    candidates = read(repo/'inputs/coverage/candidate-cells.json')
    if sha(root/'inputs/catalog/vocabulary_catalog.json') != candidates['catalog_sha256']:
        raise ValueError('Local cell catalog changed since export')
    target_set = batch.get('target_set') or next(iter({row['set_id'] for row in
        (read(p) for p in (repo/'partitions').glob('*.json'))}))
    targets = {'demo-train': ('demo-train','full-train'), 'full-train': ('full-train',),
               'demo-test': ('demo-test','full-test'), 'full-test': ('full-test',),
               'held-out': ('held-out',)}[target_set]
    conflicting = ({'demo-test','full-test','held-out'} if target_set in ('demo-train','full-train')
                   else {'demo-train','full-train','held-out'} if target_set in ('demo-test','full-test')
                   else {'demo-train','full-train','demo-test','full-test'})
    forbidden = set()
    for sid in conflicting:
        forbidden.update(read(root/'sets'/sid/'scope.json')['scope_cell_ids'])
    if any(a['cell_id'] in forbidden for a in additional):
        raise ValueError('Supplemental binding conflicts with current training or held-out allocation')
    if not additional: return {'batch_id':batch_id,'additional_bindings':0,'scope_changed':False}
    version = root/'inputs/planning'/('worker-coverage-'+batch_id)
    proposed = {}
    for sid in targets:
        path=root/'sets'/sid/'scope.json'; scope=read(path)
        existing={(a['law_id'],a['cell_id'],a['actor']) for a in scope['assignments']}
        for a in additional:
            key=(a['law_id'],a['cell_id'],a['actor'])
            if key not in existing:
                scope['assignments'].append({'law_id':a['law_id'],'cell_id':a['cell_id'],'actor':a['actor'],
                    'branch':a['branch'],'worker_binding':{'batch_id':batch_id,'package_sha256':checked['package_sha256']}})
                existing.add(key)
        cells=sorted(set(scope['scope_cell_ids'])|{a['cell_id'] for a in additional})
        scope.update(scope_cell_ids=cells,precomputed_cell_ids=cells,coverage_extension=batch_id,
                     precomputed_cells_source=str((version/(sid+'-cells.json')).relative_to(root)))
        proposed[sid]=scope
    # Validate all destinations before writing. The old snapshots remain retained.
    receipt_path=version/'receipt.json'
    receipt={'batch_id':batch_id,'package_sha256':checked['package_sha256'],
             'before':{sid:sha(root/'sets'/sid/'scope.json') for sid in proposed},
             'after':{sid:digest(scope) for sid,scope in proposed.items()},'additional_bindings':len(additional)}
    if receipt_path.exists():
        old=read(receipt_path)
        if old['package_sha256']!=checked['package_sha256']:raise ValueError('Scope extension already belongs to another return')
        if any(digest(read(root/'sets'/sid/'scope.json')) != old['after'][sid] for sid in proposed):
            raise ValueError('Extended scope differs from receipt')
        _link_selections(root, version, batch_id, {sid:read(root/'sets'/sid/'scope.json') for sid in proposed})
        return old
    for sid,scope in proposed.items():
        write(version/(sid+'-before.json'),read(root/'sets'/sid/'scope.json'))
        write(version/(sid+'-cells.json'),scope['scope_cell_ids'])
        write(root/'sets'/sid/'scope.json',scope)
    write(receipt_path,receipt)
    _link_selections(root, version, batch_id, proposed)
    from organize_work import refresh_workspaces
    refresh_workspaces(root)
    return receipt
