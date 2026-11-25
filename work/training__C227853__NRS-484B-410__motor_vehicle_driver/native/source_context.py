"""Fail-closed pre-capture provenance for the NRS 484B.410 highway start.

An authored OpenDRIVE mesh is not evidence of highway dedication, public use,
parking permission, or the subject's initial parking purpose. The local owner
must supply and retain separate source files for those facts before capture.
"""
import hashlib
import json
from pathlib import Path

FACTS = ('highway_dedication', 'public_access', 'curb_permission', 'parking_purpose')


def load_source_context(path):
    manifest_path = Path(path).resolve()
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    if manifest.get('format') != 'c227853-authority-context-v1':
        raise ValueError('Highway authority context format missing')
    if manifest.get('state') != 'Nevada' or manifest.get('public_highway') is not True:
        raise ValueError('Nevada public highway source conclusion missing')
    if type(manifest.get('parking_permitted')) is not bool:
        raise ValueError('Parking permission source conclusion missing')
    if manifest.get('initial_status') not in ('parked_no_loading',
                                               'stopped_temporary',
                                               'standing_passenger_exchange'):
        raise ValueError('Initial stopped, standing or parked purpose source conclusion missing')
    sources = manifest.get('sources')
    if not isinstance(sources, dict) or set(sources) != set(FACTS):
        raise ValueError('Four independent authority sources required')
    output = {key: manifest[key] for key in
              ('public_highway', 'parking_permitted', 'initial_status')}
    output['source_paths'] = {}
    for fact in FACTS:
        entry = sources[fact]
        if not isinstance(entry, dict) or not entry.get('citation'):
            raise ValueError('Authority citation missing: ' + fact)
        name = entry.get('path')
        if not isinstance(name, str) or not name or Path(name).is_absolute():
            raise ValueError('Authority source path must be relative: ' + fact)
        source = (manifest_path.parent / name).resolve()
        if manifest_path.parent not in source.parents or not source.is_file():
            raise ValueError('Authority source missing: ' + fact)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if entry.get('sha256') != digest:
            raise ValueError('Authority source hash differs: ' + fact)
        output[fact + '_source_sha256'] = digest
        output['source_paths'][fact] = str(source)
    output['manifest_sha256'] = hashlib.sha256(raw).hexdigest()
    output['manifest_path'] = str(manifest_path)
    return output
