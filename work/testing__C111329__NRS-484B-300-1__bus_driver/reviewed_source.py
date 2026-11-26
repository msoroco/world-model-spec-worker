"""Original site and candidate binding for a bus governed by one device."""
import json
from pathlib import Path

from device_scene import SourceError, construct_native, validate_site
from package_spec import CASES, case_id

FIELDS = ('map', 'device', 'route', 'authority')


def verify(packet_path, case_name, candidate_id='primary'):
    packet_path = Path(packet_path).resolve()
    packet = json.loads(packet_path.read_text())
    expected = next((row for row in CASES if row[0] == case_name), None)
    if expected is None or packet.get('case_id') != case_id(case_name):
        raise SourceError('reviewed packet selects another exact case')
    if packet.get('candidate_id') != candidate_id or packet.get('source_kind') != 'reviewed_original_site':
        raise SourceError('reviewed original candidate source required')
    site = packet.get('site')
    if not isinstance(site, dict):
        raise SourceError('reviewed Native site missing')
    validate_site(site, packet_path.parent)
    if packet.get('device_aspect') != expected[1] or packet.get('bus_control_policy') != expected[2]:
        raise SourceError('case device and controller request changed')
    if packet.get('police_direction') != expected[3]:
        raise SourceError('case police direction request changed')
    hashes = {key: next(ref['sha256'] for ref in site['original_sources']
                        if ref['path'] == site[key + '_source_path']) for key in FIELDS}
    return {'site': site, 'source_hashes': hashes, 'case_id': packet['case_id'],
            'candidate_id': candidate_id, 'packet': packet}


def construct_reviewed(adapter, packet_path, case_name, candidate_id='primary'):
    reviewed = verify(packet_path, case_name, candidate_id)
    if getattr(adapter, 'native_attested', False) is not True:
        raise SourceError('attested original Native adapter required')
    if not all(hasattr(adapter, name) for name in ('world', 'carla', 'bus_blueprint')):
        raise SourceError('Native adapter lacks world, carla or bus blueprint')
    built = construct_native(reviewed['site'], Path(packet_path).parent,
                             adapter.world, adapter.carla, adapter.bus_blueprint)
    return {'bus': built['bus'], 'owned': [built['bus']], 'site': reviewed['site'],
            'case_id': reviewed['case_id'], 'candidate_id': candidate_id,
            'device_id': built['device_id']}
