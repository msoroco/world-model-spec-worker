"""Review-gated original intersection packet loader for Native capture."""
import hashlib
import json
from pathlib import Path

from through_highway import ASSIGNMENT, validate_site


REQUIRED = ('road.xodr', 'municipal_jurisdiction', 'through_highway_designation',
            'intersection_geometry', 'entrance_control', 'antecedent_review')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_reviewed_site(manifest_path, site_path, case_id):
    manifest_path, site_path = Path(manifest_path), Path(site_path)
    if not manifest_path.is_file() or not site_path.is_file() or manifest_path.is_symlink() or site_path.is_symlink():
        raise ValueError('reviewed original site packet missing')
    manifest = json.loads(manifest_path.read_text())
    site = json.loads(site_path.read_text())
    if (manifest.get('format') != 'reviewed-through-highway-site-v1' or
            manifest.get('case_id') != case_id or manifest.get('site_sha256') != sha(site_path) or
            not manifest.get('reviewer') or not manifest.get('citation') or
            manifest.get('source_kind') != 'reviewed_original_site' or
            site.get('source_kind') != 'reviewed_original_site' or
            site.get('case_id') != case_id or
            site.get('accepted_original_source') is not True or
            not case_id.startswith(ASSIGNMENT + '__')):
        raise ValueError('reviewed original site identity/provenance missing')
    sources = manifest.get('sources', {})
    if not isinstance(sources, dict) or not set(REQUIRED) <= set(sources):
        raise ValueError('reviewed original site source list incomplete')
    for name in REQUIRED:
        item = sources[name]
        relative = Path(item.get('path', ''))
        if relative.is_absolute() or '..' in relative.parts or not str(relative) or str(relative) == '.':
            raise ValueError('unsafe reviewed original source path: ' + name)
        path = manifest_path.parent / relative
        if (not path.is_file() or path.is_symlink() or path.stat().st_size == 0 or
                sha(path) != item.get('sha256')):
            raise ValueError('reviewed original source seal changed: ' + name)
    if site.get('map_sha256') != sources['road.xodr']['sha256']:
        raise ValueError('reviewed original map seal changed')
    for name, field in (('municipal_jurisdiction', 'municipal_jurisdiction_source'),
                        ('through_highway_designation', 'through_highway_designation_source'),
                        ('intersection_geometry', 'intersection_geometry_source'),
                        ('entrance_control', 'entrance_control_source'),
                        ('antecedent_review', 'antecedent_review_source')):
        if site.get(field) != sources[name]['sha256']:
            raise ValueError('reviewed site field source differs: ' + field)
    key = case_id.removeprefix(ASSIGNMENT + '__')
    validate_site(site, key, site['map_sha256'])
    return site
