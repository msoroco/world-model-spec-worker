"""Materialize the canonical first-case root package from the selected bundle."""

import json
from pathlib import Path


FOLDER = Path(__file__).resolve().parent.parent


def build():
    selected = json.loads((FOLDER / 'native-selected/probe_2/construction.json').read_text())
    selected['status'] = 'selected_delivery_draft_physical_unverified'
    selected['static_checks'] = [
        'frozen C111334 pedestrian identity and exact case',
        'two authored device identities and highway crossing geometry',
        '30 seconds, 20 Hz and four exact camera poses',
    ]
    selected['termination_rules'] = [
        '600 synchronized Native and camera frames',
        'abort on missing pedestrian, device head, source camera or restoration failure',
    ]
    selected['mechanisms'] = [
        'authored intersection highway crossing and two signal requests',
        'per-frame walker controller and Native signal state readback',
        'four synchronized FFV1 source streams and original frame map',
    ]
    selected['measurement_plan'] = (
        'Original pedestrian footprint and first highway occupancy joined to '
        'independently reviewed arrow, facing and other-device permission by '
        'Native frame, with four source cameras retained.')
    for item in selected['files']:
        target = FOLDER / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    (FOLDER / 'construction.json').write_text(
        json.dumps(selected, indent=2, allow_nan=False) + '\n')
    return {'root_case_id': selected['case_id'],
            'files': len(selected['files'])}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
