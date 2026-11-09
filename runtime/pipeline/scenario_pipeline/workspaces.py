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
    """Processing administration is always outside accepted review outputs."""
    from recording_store import safe_name
    work = Path(work_root) if work_root is not None else OUTPUT_ROOT/'work'
    return work.parent/'state/operations'/safe_name(run)


def semantic_directory(output, cell, actor):
    return Path(output)/'cells'/cell/actor


def law_directory(cell, law, *, category='train', root=None, set_id=None):
    from recording_store import safe_name
    root = Path(root) if root is not None else OUTPUT_ROOT
    chosen = set_id or {'train':'full-train','test':'full-test','demo':'demo-train',
                        'held-out':'held-out'}.get(category,category)
    if chosen not in ('demo-train','demo-test','full-train','full-test','held-out'):
        raise ValueError('Unknown review set')
    return root/'work'/chosen/(safe_name(cell)+'--'+safe_name(law))


def artifact_directory(output, cell, actor, case, job):
    """Construction/report metadata belongs to its operation, not review files."""
    return Path(output)/'artifacts'/str(job)


def validator_path(run, work_root=None):
    work = Path(work_root) if work_root is not None else OUTPUT_ROOT/'work'
    return work.parent/'inputs/shared/tools/adapterCheck'
