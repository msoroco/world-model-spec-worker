"""Reopen source bytes for the original signed bicycle roadway restriction."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from native_site import validate_site

FIELDS = ('jurisdiction', 'engineer_designation', 'sign_erection',
          'sign_wording', 'sign_orientation', 'route', 'bicycle', 'map')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(path: Path) -> dict:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('reviewed original bicycle site packet missing')
    path = path.resolve()
    packet = json.loads(path.read_text(encoding='utf-8'))
    if (packet.get('format') != 'c143687-reviewed-site-v1' or
            packet.get('review_status') != 'reviewed' or
            packet.get('diagnostic_fixture') is True or
            not packet.get('reviewer')):
        raise ValueError('reviewed original bicycle site status missing')
    site = packet.get('site')
    if not isinstance(site, dict):
        raise ValueError('reviewed original bicycle site absent')
    site_binding = validate_site(site)
    bindings = packet.get('source_bindings')
    if not isinstance(bindings, dict) or set(bindings) != set(FIELDS):
        raise ValueError('reviewed bicycle source inventory incomplete')
    for name, item in bindings.items():
        if not isinstance(item, dict) or not item.get('citation') or not item.get('reviewer'):
            raise ValueError('reviewed bicycle citation absent: ' + name)
        rel = item.get('path')
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or '..' in Path(rel).parts:
            raise ValueError('reviewed bicycle source path invalid: ' + name)
        source = path.parent / rel
        if (source.is_symlink() or not source.is_file() or
                not source.resolve().is_relative_to(path.parent) or
                sha(source) != item.get('sha256') or
                site.get(name + '_source_sha256') != item.get('sha256')):
            raise ValueError('reviewed bicycle source bytes absent or changed: ' + name)
    return {'site': site, 'site_sha256': site_binding['site_sha256'],
            'packet_sha256': sha(path),
            'source_hashes': {name: bindings[name]['sha256'] for name in FIELDS},
            'packet_path': str(path), 'legal_assessment': 'unresolved'}
