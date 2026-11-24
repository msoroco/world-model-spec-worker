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
        measurement_path = HERE / 'crossref-060b-native' / label / 'source-measurement.json'
        measured = json.loads(measurement_path.read_text())
        if (measured['frames'] != 600 or measured['case_id'] != case or
            measured['authored_bridge_type_survey_target_present'] != (label == 'overhead_candidate') or
            measured['native_rendered_pedestrian_overhead_verified'] or
            measured['usable_pedestrian_access_verified'] or measured['original_pixels_verified'] or
            measured['legal_applicability_conclusion'] is not None):
            raise ValueError('Synthetic infrastructure measurement overclaims or differs')
        proof_hashes = {}
        for candidate, location in (('primary', HERE / 'crossref-060b-native' / label / 'proofs'),
                                    ('fallback1', HERE / 'crossref-060b-fallback1' / label / 'proofs')):
            hashes = {}
            for name in ('offline.log', 'compatibility.json', 'positive-analysis.log',
                         'negative-analysis.log', 'processing.json', 'saved-analysis.log'):
                receipt = location / name
                if not receipt.is_file():
                    raise ValueError('Current-runtime receipt missing: ' + candidate + '/' + name)
                hashes[name] = digest(receipt)
            if 'Missing required source: curb-samples.jsonl' not in (location / 'negative-analysis.log').read_text():
                raise ValueError('Missing-source negative did not reject')
            proof_hashes[candidate] = hashes
        records.append({'case_id':case,'construction_sha256':digest(path),
                        'road_sha256':hashlib.sha256(files['road.xodr'].encode()).hexdigest(),
                        'offline_log_sha256':digest(proof),
                        'source_measurement_sha256':digest(measurement_path),
                        'current_runtime_proof_hashes':proof_hashes,
                        'authored_overhead_candidate':label=='overhead_candidate'})
    if records[0]['road_sha256'] == records[1]['road_sha256']:
        raise ValueError('Context variable unchanged')
    return {'format':'c230222-060b-authored-overhead-cpu-proof-v1',
            'records':records,'measurement_script_sha256':digest(HERE / 'measure-crossref-060b.py'),
            'missing_frame_rejected':True,'public_positive_count':4,
            'missing_source_negative_count':4,'recorded_only_saved_count':4,
            'original_native_visibility_verified':False,
            'pedestrian_tunnel_or_overhead_provided_verified':False,
            'legal_applicability_conclusion':None}


if __name__ == '__main__':
    path = HERE / 'crossref-060b-native/proof.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(audit(), indent=2) + '\n')
    print(json.dumps({'authored_context_cases': 2, 'physical_verified': False}))
