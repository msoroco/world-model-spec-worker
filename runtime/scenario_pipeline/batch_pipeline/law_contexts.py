"""Content-addressed supplementary corpus context with exact archive attribution."""
import hashlib
import json
from pathlib import Path


def bounded(root,relative):
    root=Path(root).resolve();path=(root/relative).resolve()
    if root not in path.parents:raise ValueError('Context resource escapes reference directory')
    return path


def references(package,law_ids=None):
    root=Path(package)/'references';index=root/'index.json'
    if not index.exists():return []
    selected=[]
    for ref in json.loads(index.read_text())['contexts']:
        if law_ids is None or set(ref['law_ids']) & set(law_ids):
            selected.append(ref)
    return sorted(selected,key=lambda v:(v['id'],v['sha256']))


def load(package,refs,current_laws):
    root=Path(package)/'references';result=[]
    for ref in refs:
        raw=bounded(root,ref['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=ref['sha256']:raise ValueError('Supplemental context hash mismatch')
        value=json.loads(raw)
        if value['id']!=ref['id'] or value['law_ids']!=ref['law_ids']:raise ValueError('Supplemental context identity mismatch')
        provenance=value['provenance'];archive=bounded(root,provenance['snapshot']).read_bytes()
        if hashlib.sha256(archive).hexdigest()!=provenance['archive_sha256']:raise ValueError('Context source archive hash mismatch')
        records={v['id']:v for v in (json.loads(line) for line in archive.decode().splitlines() if line.strip())}
        record=records[provenance['record_id']];start,end=provenance['exact_character_span']
        if record['text'][start:end]!=value['text'] or not value['text'] or record['source']!=provenance['record_source']:
            raise ValueError('Context quotation does not match attributed archive span')
        for law in ref['law_ids']:
            if records[law]['text']!=current_laws[law]['text']:raise ValueError('Referring current law differs from recovered source version')
        result.append(value)
    return result
