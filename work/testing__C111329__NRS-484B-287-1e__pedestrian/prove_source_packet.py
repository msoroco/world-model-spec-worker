"""Exercise reviewed-site joins with a test double, never an official record."""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from reviewed_site import validate_reviewed_site


def put(root, name, data):
    path = root / name
    path.write_text(data if isinstance(data, str) else json.dumps(data) + '\n')
    return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def run(negative):
    scratch = Path(__file__).resolve().parents[2] / '.runtime-work/c111329-source-probe'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temp:
        root = Path(temp)
        corners = [[0, 0], [10, 0], [10, 10], [0, 10]]
        route = [[0, 0], [5, 5], [10, 10]]
        device = {'id': 'FAKE-DEVICE', 'authority_record_id': 'FAKE-AUTH',
                  'instruction_record_id': 'FAKE-INSTRUCTION',
                  'placement_record_id': 'FAKE-PLACEMENT',
                  'governs': 'pedestrian_diagonal', 'diagonal_authorized': True}
        refs = {}
        refs['map'] = put(root, 'map.xodr', '<OpenDRIVE><road><planView><geometry/></planView></road></OpenDRIVE>\n')
        refs['corner_survey'] = put(root, 'survey.json', {'cell_id': 'C111329',
            'map_sha256': refs['map']['sha256'], 'corners_clockwise': corners,
            'route_xy': route, 'survey_method': 'FAKE test geometry', 'reviewer': 'TEST DOUBLE'})
        refs['authorization'] = put(root, 'authority.json', {'cell_id': 'C111329',
            'record_id': 'FAKE-AUTH', 'movement': 'pedestrian_diagonal',
            'device_id': 'FAKE-DEVICE', 'authorized': True,
            'issuing_authority': 'TEST DOUBLE', 'original_document_ref': 'FAKE-REF',
            'reviewer': 'TEST DOUBLE'})
        refs['device_inventory'] = put(root, 'inventory.json', {'cell_id': 'C111329',
            'device_id': 'FAKE-DEVICE', 'movement': 'pedestrian_diagonal',
            'instruction_record_id': 'FAKE-INSTRUCTION',
            'placement_record_id': 'FAKE-PLACEMENT',
            'authorization_record_id': 'FAKE-AUTH',
            'original_device_observation_ref': 'FAKE-REF', 'reviewer': 'TEST DOUBLE'})
        refs['exception_review'] = put(root, 'exception.json', {'statute': 'NRS 484B.290',
            'review_state': 'unresolved', 'source_ref': 'FAKE-REF', 'reviewer': 'TEST DOUBLE'})
        packet = {'sources': refs, 'coordinate_frame': 'map_xy_m',
                  'corners_clockwise': corners, 'pedestrian_route': route,
                  'governing_device': device, 'observed_device_ids': ['FAKE-DEVICE'],
                  'exception_484b_290_review': 'unresolved'}
        if negative:
            (root / 'authority.json').write_text('{"changed": true}\n')
            try:
                validate_reviewed_site(packet, root)
            except ValueError as exc:
                print('expected rejection:', exc)
                return
            raise AssertionError('changed authorization source accepted')
        result = validate_reviewed_site(packet, root)
        assert result['official_status'] == 'source_review_required'
        assert result['physical_realization'] == 'unconfirmed'
        print('FAKE source packet joins valid; official review required; physical unconfirmed')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--negative', action='store_true')
    run(p.parse_args().negative)
