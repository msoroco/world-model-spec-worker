"""Operational workspace paths; datasets continue to own recording membership."""
import json
from functools import lru_cache
from pathlib import Path
from pipeline_paths import OUTPUT_ROOT


def work_index(root=None):
    root = Path(root) if root is not None else OUTPUT_ROOT
    path = root/'work/index.json'
    if not path.exists(): return {}
    stat=path.stat()
    return _cached_index(str(path),stat.st_mtime_ns,stat.st_size)


@lru_cache(maxsize=4)
def _cached_index(path,mtime,size):
    return json.loads(Path(path).read_text())


def campaign_path(run, work_root=None):
    work = Path(work_root) if work_root is not None else OUTPUT_ROOT/'work'
    index = work_index(work.parent)
    value = index.get('campaigns', {}).get(run)
    if value:
        return work.parent/value
    if index.get('format')=='set-review-workspaces-v2':
        from recording_store import safe_name
        return work.parent/'state/operations'/safe_name(run)
    # Existing pre-migration callers keep working until organize-work commits.
    if not index and (work/run).exists():
        return work/run
    return work/'train/_campaigns'/run


def semantic_directory(output, cell, actor):
    output = Path(output)
    if output.parent.name == '_campaigns':
        root=output.parents[3]
        index=work_index(root)
        for entry in index.get('entries',[]):
            if entry['cell_id']!=cell: continue
            for source in entry.get('shared_sources',[]):
                path=Path(source)
                if path.parent.name=='semantic' and path.name==output.name:
                    return root/path/actor
        return output.parent.parent/cell/'_shared/semantic'/output.name/actor
    return output/'cells'/cell/actor


def law_directory(cell, law, *, category='train', root=None, set_id=None):
    from recording_store import safe_name
    root = Path(root) if root is not None else OUTPUT_ROOT
    if work_index(root).get('format')=='set-review-workspaces-v2':
        chosen=set_id or {'train':'full-train','test':'full-test','demo':'demo-train','held-out':'held-out'}.get(category,category)
        if chosen not in ('demo-train','demo-test','full-train','full-test','held-out'):
            raise ValueError('Unknown review set')
        return root/'work'/chosen/(safe_name(cell)+'--'+safe_name(law))
    if category not in ('demo', 'held-out', 'train', 'test'):
        raise ValueError('Unknown workspace category')
    return root/'work'/category/safe_name(cell)/safe_name(law)


def artifact_directory(output, cell, actor, case, job):
    """Law-specific construction/report metadata; capture stays in recordings/."""
    output = Path(output)
    law = case.get('target_law_id')
    if output.parent.name != '_campaigns' or not law:
        return output/'artifacts'/str(job)
    category = output.parent.parent.name
    root = output.parents[3]
    key = '|'.join((cell, law, actor))
    indexed = work_index(root).get('assignments', {}).get(key, {})
    if category != 'held-out':
        category = indexed.get('category', category)
    return law_directory(cell, law, category=category, root=root)/'actors'/actor/'artifacts'/output.name/str(job)


def validator_path(run, work_root=None):
    work=Path(work_root) if work_root is not None else OUTPUT_ROOT/'work'
    resource=work_index(work.parent).get('resources',{}).get(run,{}).get('validator')
    return work.parent/resource if resource else campaign_path(run,work)/'inputs/validator-core/.lake/build/bin/adapterCheck'
