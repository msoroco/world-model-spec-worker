"""Fail-closed authored-overhead candidate construction audit; no physical claim."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
LABELS = ('overhead_candidate', 'no_overhead')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    manifest = json.loads((HERE / 'crossref-060b-manifest.json').read_text())
    if len(manifest['cases']) != 2:
        raise ValueError('Two 060(B) authored context alternatives required')
    records = []
    for label in LABELS:
        case = HERE.name + '__crossref_lvmc_11_30_060_b_' + label
        entry = next(x for x in manifest['cases'] if x['case_id'] == case)
        path = HERE / entry['construction']
        if digest(path) != entry['construction_sha256'] or entry['native_overhead_visibility_verified'] or entry['pedestrian_tunnel_or_overhead_provided_verified']:
            raise ValueError('Construction binding or physical claim differs')
        construction = json.loads(path.read_text())
        if construction['case_id'] != case:
            raise ValueError('Construction case identity differs')
        files = {item['path']: item['content'] for item in construction['files']}
        road = ET.fromstring(files['road.xodr'])
        objects = road.findall('.//objects/object')
        if len(road.findall('road')) != 1 or road.findall('.//junction'):
            raise ValueError('Original cell road geometry differs')
        if label == 'overhead_candidate':
            if len(objects) != 1 or objects[0].get('type') != 'bridge' or objects[0].get('zOffset') != '5':
                raise ValueError('Overhead survey target absent')
        elif objects:
            raise ValueError('No-overhead control contains authored objects')
        config = json.loads(files['config.json'])
        if config['duration_s'] != 30 or config['rate_hz'] != 20 or config['case_id'] != case or len(config['cameras']) != 4:
            raise ValueError('Capture contract differs')
        proof = HERE / 'crossref-060b-native' / label / 'offline.log'
        if not proof.is_file() or 'Traceback' in proof.read_text():
            raise ValueError('Pinned offline proof missing or failed')
        records.append({'case_id':case,'construction_sha256':digest(path),
                        'road_sha256':hashlib.sha256(files['road.xodr'].encode()).hexdigest(),
                        'offline_log_sha256':digest(proof),
                        'authored_overhead_candidate':label=='overhead_candidate'})
    if records[0]['road_sha256'] == records[1]['road_sha256']:
        raise ValueError('Context variable unchanged')
    return {'format':'c230222-060b-authored-overhead-cpu-proof-v1',
            'records':records,'original_native_visibility_verified':False,
            'pedestrian_tunnel_or_overhead_provided_verified':False,
            'legal_applicability_conclusion':None}


if __name__ == '__main__':
    path = HERE / 'crossref-060b-native/proof.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(audit(), indent=2) + '\n')
    print(json.dumps({'authored_context_cases': 2, 'physical_verified': False}))
