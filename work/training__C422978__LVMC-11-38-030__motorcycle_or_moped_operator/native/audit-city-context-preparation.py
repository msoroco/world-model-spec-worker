"""Independent source, calibration and saved-measurement audit."""
import hashlib
import json
from pathlib import Path

from measure_context import measure

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'context-fixtures/survey-diagnostic.geojson'
CALIBRATION = ROOT / 'context-fixtures/survey-diagnostic-calibration.json'
PACKET = ROOT / 'context-fixtures/prepared-diagnostic.json'
ATTEMPT = ROOT / 'saved-fixtures/witness_2/primary'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


proof = json.loads((ROOT / 'city-context-preparation-proof.json').read_text())
source, cal, packet = [json.loads(p.read_text()) for p in (SOURCE, CALIBRATION, PACKET)]
assert proof['scope'] == 'synthetic_cpu'
assert (proof['source_sha256'], proof['calibration_sha256'], proof['packet_sha256']) == (
    sha(SOURCE), sha(CALIBRATION), sha(PACKET))
features = {f['id']: f['geometry']['coordinates'][0][:-1] for f in source['features']}
assert len(features) == len(source['features']) == 2
assert all(f['geometry']['coordinates'][0][0] == f['geometry']['coordinates'][0][-1]
           for f in source['features'])
assert packet['city_boundary_polygon'] == features['city_boundary']
assert packet['sidewalk_polygon'] == features['sidewalk']
assert packet['driveway_crossing_polygons'] == []
assert packet['native_to_context_affine'] == cal['native_to_context_affine']
assert packet['map_readback_sha256'] == sha(ATTEMPT / 'native-map-readback.json')
assert packet['source_provenance']['geojson_sha256'] == sha(SOURCE)
assert packet['source_provenance']['calibration_sha256'] == sha(CALIBRATION)
assert packet['authority_kind'] == 'synthetic_cpu' and packet['city_authority_reviewed'] is False
actual = measure(ATTEMPT, PACKET)
assert actual == proof['measurement'] and actual['candidate_city_sidewalk_non_driveway_frames'] == 400
assert set(proof['negative_rejections']) == {'source_hash', 'missing_sidewalk', 'polygon_hole',
    'false_authority', 'singular_calibration', 'map_hash', 'original_requires_survey'}
assert proof['original_city_source_observed'] is False and proof['physical_or_legal_acceptance'] is False
(ROOT / 'city-context-preparation-audit.json').write_text(json.dumps({
    'format': 'c422978-city-context-preparation-audit-v1', 'passed': True,
    'source_sha256': sha(SOURCE), 'calibration_sha256': sha(CALIBRATION),
    'packet_sha256': sha(PACKET), 'frames': 480, 'negative_count': 7,
    'scope': 'synthetic_cpu', 'original_city_source_observed': False}, indent=2) + '\n')
print('city context independent audit: source, calibration, packet, 480 frames, seven negatives')
