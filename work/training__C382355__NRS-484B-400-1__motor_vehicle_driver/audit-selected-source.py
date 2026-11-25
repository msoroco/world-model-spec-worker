"""Verify the exact statutory branch text and selected authored lane sources."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c3823554001-selected-public-through-v2/attempt'
CASES = ('witness_1', 'witness_2', 'extreme_right_1', 'extreme_right_2')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    law = {}
    for ref in plan['sources']:
        path = ROOT / ref['path']
        if sha(path) != ref['sha256']:
            raise ValueError('Frozen source changed: ' + ref['path'])
        assignment = json.loads(path.read_text())
        law[assignment['law_id']] = assignment['law']['text']
    exact = law['NRS-484B-400-1']
    right_only = law['NRS-484B-223-4a']
    through_prohibition = law['NRS-484B-223-4b']
    if not (all(part in exact for part in
                ('right turn lane if the highway has a right turn lane',
                 'or must be made from the extreme right lane')) and
            'single right lane to be used only for turning' in right_only and
            'not travel through an intersection' in through_prohibition):
        raise ValueError('Exact frozen branch text differs')
    selected = json.loads((HERE / 'selected-probe-manifest.json').read_text())
    if {case['case_id'].rsplit('__', 1)[-1] for case in selected['cases']} != set(CASES):
        raise ValueError('Selected case roster differs')
    records = []
    for suffix in CASES:
        path = SCRATCH / (suffix + '-primary') / 'road.xodr'
        root = ET.fromstring(path.read_text())
        connectors = {row.attrib['connectingRoad']: row.find('laneLink').attrib
                      for row in root.findall('junction/connection')}
        arrow = root.find("road[@id='1']/objects/object[@name='right_turn_arrow']")
        through = root.find("road[@id='14']")
        expected = suffix.startswith('witness_')
        if expected:
            if arrow is None or through is not None or set(connectors) != {'13'}:
                raise ValueError('Qualifying right-only design differs')
        elif arrow is not None or through is None or set(connectors) != {'13', '14'}:
            raise ValueError('Alternative rightmost lane lacks a real through option')
        if any(link != {'from': '-2', 'to': '-2'} for link in connectors.values()):
            raise ValueError('Original rightmost lane link differs')
        records.append({'case': suffix, 'authored_map_sha256': sha(path),
                        'branch': 'qualifying_right_only_lane' if expected
                        else 'alternative_extreme_right_lane',
                        'native_design_verified': False})
    return {'format': 'c382355-400-1-source-audit-v1', 'passed': True,
            'frozen_law_sources': {key: hashlib.sha256(value.encode()).hexdigest()
                                   for key, value in sorted(law.items())},
            'selected_cases': records, 'original_native_pixels_reviewed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
