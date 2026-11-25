"""Shape-only source protocol test doubles; no original source is supplied."""
import hashlib
import json
import tempfile
from pathlib import Path
from reviewed_site import verify


def write(path, value):
    path.write_text(json.dumps(value) + '\n')
    return {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    repo = Path(__file__).resolve().parents[2]
    scratch = repo / '.runtime-work/c111329-2871d-source-protocol'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temp:
        root = Path(temp)
        device = {'id': 'TEST-DOUBLE-DIAGONAL', 'official_source': 'TEST-DOUBLE authority',
                  'instruction_source': 'TEST-DOUBLE pedestrian instruction',
                  'pedestrian_governance': 'diagonal', 'state': 'permissive',
                  'diagonal_instruction_reviewed': True}
        site = {'cell_id': 'C111329', 'actor': 'pedestrian', 'map_name': 'TEST-DOUBLE',
                'map_sha256': 'a' * 64, 'survey_source': 'TEST-DOUBLE survey',
                'intersection_polygon': [[0, 0], [10, 0], [10, 10], [0, 10]],
                'corners': [[-1, -1], [11, -1], [11, 11], [-1, 11]],
                'devices': [device]}
        map_data = {key: site[key] for key in ('cell_id', 'map_name', 'map_sha256',
                                             'intersection_polygon', 'corners')}
        map_data['diagnostic'] = False
        device_data = {'diagnostic': False, 'cell_id': 'C111329',
                       'map_sha256': site['map_sha256'], 'devices': [device]}
        map_ref = write(root / 'map.json', map_data)
        device_ref = write(root / 'devices.json', device_data)
        site['original_sources'] = {'map': map_ref, 'devices': device_ref}
        positive = verify(root, site, 'opposite', True)
        assert positive['route_kind'] == 'opposite'
        print('shape-only TEST DOUBLE positive joins pass; legal exception unresolved')
        (root / 'devices.json').write_text('{"changed":true}\n')
        try:
            verify(root, site, 'opposite', True)
        except ValueError as exc:
            assert 'hash mismatch' in str(exc)
            print('changed device source rejected:', exc)
        else:
            raise AssertionError('changed device accepted')
        write(root / 'devices.json', device_data)
        without_instruction = dict(device_data)
        without_instruction['devices'] = [dict(device, diagonal_instruction_reviewed=False)]
        site['devices'] = without_instruction['devices']
        site['original_sources']['devices'] = write(root / 'devices.json', without_instruction)
        try:
            verify(root, site, 'opposite', True)
        except ValueError as exc:
            assert 'reviewed diagonal' in str(exc)
            print('unreviewed diagonal instruction rejected:', exc)
        else:
            raise AssertionError('unreviewed instruction accepted')


if __name__ == '__main__':
    main()
