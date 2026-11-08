"""CPU proof for preparing a source-hashed diagnostic geometry packet."""
import copy
import hashlib
import json
import tempfile
from pathlib import Path

from prepare_city_context import prepare
from measure_context import measure

ROOT = Path(__file__).resolve().parent
ATTEMPT = ROOT / 'saved-fixtures/witness_2/primary'
FIXTURE = ROOT / 'context-fixtures/witness_2/primary/city-context.json'
SOURCE = ROOT / 'context-fixtures/survey-diagnostic.geojson'
CALIBRATION = ROOT / 'context-fixtures/survey-diagnostic-calibration.json'
OUTPUT = ROOT / 'context-fixtures/prepared-diagnostic.json'
PROOF = ROOT / 'city-context-preparation-proof.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def feature(name, vertices):
    return {'type': 'Feature', 'id': name,
            'geometry': {'type': 'Polygon', 'coordinates': [vertices + [vertices[0]]]},
            'properties': {}}


context = json.loads(FIXTURE.read_text())
source = {'type': 'FeatureCollection', 'source_kind': 'synthetic_cpu',
          'city_authority_reviewed': False, 'source_crs': 'diagnostic-native-metres',
          'features': [feature('city_boundary', context['city_boundary_polygon']),
                       feature('sidewalk', context['sidewalk_polygon'])]}
calibration = {'source_crs': 'diagnostic-native-metres',
               'map_readback_sha256': sha(ATTEMPT / 'native-map-readback.json'),
               'native_to_context_affine': [[1, 0, 0], [0, 1, 0]],
               'calibration_source': 'synthetic identity diagnostic'}
SOURCE.write_text(json.dumps(source, indent=2) + '\n')
CALIBRATION.write_text(json.dumps(calibration, indent=2) + '\n')
OUTPUT.unlink(missing_ok=True)
packet = prepare(SOURCE, sha(SOURCE), ATTEMPT / 'native-map-readback.json',
                 CALIBRATION, OUTPUT, diagnostic=True)
measured = measure(ATTEMPT, OUTPUT)
assert measured['frames'] == 480 and measured['candidate_city_sidewalk_non_driveway_frames'] == 400
assert measured['legal_verdict'] is None and measured['city_authority_reviewed'] is False

negatives = {}
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    def reject(name, changed_source=None, changed_calibration=None, expected_hash=None, diagnostic=True):
        src, cal, out = tmp / (name + '.geojson'), tmp / (name + '.json'), tmp / (name + '.out')
        src.write_text(json.dumps(changed_source if changed_source is not None else source))
        cal.write_text(json.dumps(changed_calibration if changed_calibration is not None else calibration))
        try:
            prepare(src, expected_hash if expected_hash is not None else sha(src),
                    ATTEMPT / 'native-map-readback.json', cal, out, diagnostic=diagnostic)
        except ValueError as error:
            negatives[name] = str(error)
        else:
            raise AssertionError('Expected rejection: ' + name)
    reject('source_hash', expected_hash='0'*64)
    bad = copy.deepcopy(source); bad['features'] = bad['features'][:1]
    reject('missing_sidewalk', changed_source=bad)
    bad = copy.deepcopy(source); bad['features'][1]['geometry']['coordinates'].append(
        [[1, 1], [2, 1], [2, 2], [1, 1]])
    reject('polygon_hole', changed_source=bad)
    bad = copy.deepcopy(source); bad['city_authority_reviewed'] = True
    reject('false_authority', changed_source=bad)
    bad = copy.deepcopy(calibration); bad['native_to_context_affine'] = [[1, 0, 0], [2, 0, 0]]
    reject('singular_calibration', changed_calibration=bad)
    bad = copy.deepcopy(calibration); bad['map_readback_sha256'] = '0'*64
    reject('map_hash', changed_calibration=bad)
    reject('original_requires_survey', diagnostic=False)

PROOF.write_text(json.dumps({'format': 'c422978-city-context-preparation-proof-v1',
                             'scope': 'synthetic_cpu', 'source_sha256': sha(SOURCE),
                             'calibration_sha256': sha(CALIBRATION),
                             'packet_sha256': sha(OUTPUT),
                             'measurement': measured, 'negative_rejections': negatives,
                             'original_city_source_observed': False,
                             'physical_or_legal_acceptance': False}, indent=2) + '\n')
print('city context preparation: one 480-frame positive, seven negatives')
