"""Source-bound, fail-closed NRS 484B.307 applicability preflight."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ROAD = HERE / 'cases/branch-requests/alley-signal.xodr'
OUT = HERE / 'cases/branch-requests/signal-law-applicability.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    refs = {}
    for part in ('2a', '8a'):
        path = ROOT / f'inputs/training__C110919__NRS-484B-307-{part}__motor_vehicle_driver/assignment.json'
        law = json.loads(path.read_text())['law']
        assert law['id'] == f'NRS-484B-307-{part}'
        assert 'intersection' in law['text']
        refs[part] = {'path': str(path.relative_to(ROOT)), 'sha256': sha(path),
                      'source': law['source'], 'intersection_reference': True}
    tree = ET.parse(ROAD).getroot()
    roads = tree.findall('road')
    assert len(roads) == 1 and roads[0].get('id') == '389'
    assert roads[0].get('junction') == '-1'
    assert not tree.findall('.//junction')
    assert not tree.findall('.//crosswalk')
    signal = tree.find('.//signal')
    assert signal is not None and signal.get('id') == '3892'
    assert signal.get('type') == '1000001'
    result = {'format': 'c10389-signal-applicability-preflight-v1',
              'frozen_law_sources': refs,
              'authored_source': {'path': str(ROAD.relative_to(ROOT)), 'sha256': sha(ROAD),
                                  'road_id': 389, 'road_junction': '-1',
                                  'junction_count': 0, 'crosswalk_count': 0,
                                  'signal_id': '3892', 'signal_type': '1000001'},
              'condition': 'signal red/green requests on an authored single-road alley',
              'disposition': 'intersection-dependent NRS 484B.307 applicability not established by this source',
              'original_native_topology_required': True,
              'official_placement_verified': False,
              'legal_outcome_claimed': False}
    OUT.write_text(json.dumps(result, indent=2) + '\n')
    print(str(OUT.relative_to(ROOT)), sha(OUT))


if __name__ == '__main__':
    run()
