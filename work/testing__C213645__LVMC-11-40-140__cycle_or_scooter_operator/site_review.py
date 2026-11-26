"""Validate source bytes of a reviewed original driveway-sidewalk packet."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from driveway_case import SOURCE_ROLES, validate_site


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reviewed_site(path,case_id):
    path=Path(path).resolve();site=json.loads(path.read_text(encoding='utf-8'))
    if (site.get('format')!='c213645-reviewed-original-driveway-v1' or
            site.get('source_kind')!='original_reviewed' or
            site.get('diagnostic_fixture') is not False or
            site.get('case_id')!=case_id or not site.get('reviewer')):
        raise ValueError('reviewed original driveway identity missing')
    sources=site.get('sources')
    if not isinstance(sources,dict):raise ValueError('reviewed driveway source inventory missing')
    for role in SOURCE_ROLES:
        item=sources.get(role)
        if not isinstance(item,dict) or not item.get('path') or not item.get('sha256'):
            raise ValueError('reviewed original source missing: '+role)
        candidate=path.parent/item['path'];source=candidate.resolve()
        if candidate.is_symlink() or not source.is_relative_to(path.parent) or not source.is_file():
            raise ValueError('reviewed source path escapes packet: '+role)
        if sha(source)!=item['sha256'] or site.get(role+'_source_sha256')!=item['sha256']:
            raise ValueError('reviewed driveway source hash differs: '+role)
    validate_site(site)
    return site
