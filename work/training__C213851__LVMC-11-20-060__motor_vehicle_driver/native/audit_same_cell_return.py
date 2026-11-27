"""Audit whether current C213851 exact constructions request roadway re-entry."""

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'native'
AID = ROOT.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    rows = []
    for policy in ('stop_before_sidewalk', 'cross_without_stop'):
        folder = NATIVE / policy
        controls = [json.loads(line) for line in (folder / 'requested-tracks.jsonl').read_text().splitlines()]
        config = json.loads((folder / 'config.json').read_text())
        values = [row['requested_route_s_m'] for row in controls]
        assert len(controls) == 600 and config['duration_s'] == 30
        assert config['route'] == 'road_to_private_driveway'
        assert values[0] < -1.75 and values[-1] > 2
        assert all(b >= a for a, b in zip(values, values[1:]))
        rows.append({'policy': policy, 'config_sha256': sha(folder / 'config.json'),
                     'tracks_sha256': sha(folder / 'requested-tracks.jsonl'),
                     'frame_count': len(controls), 'first_route_s_m': values[0],
                     'last_route_s_m': values[-1], 'nondecreasing_route': True,
                     'return_to_road_requested': False})
    road = NATIVE / 'road/road.xodr'
    root = ET.parse(road).getroot()
    roads = root.findall('road')
    assert len(roads) == 2 and all(not list(r.find('link')) for r in roads)
    runner = NATIVE / 'runner.py'
    code = runner.read_text()
    assert "library.find('vehicle.tesla.model3')" in code
    assert code.count('world.spawn_actor(vehicle_bp,') == 1
    assert "library.filter('walker.pedestrian.*')" in code
    assert 'approaching_vehicle' not in code
    report = {'format': 'worker-same-cell-return-feasibility-audit',
              'assignment_id': AID, 'scope': 'current_two_selected_constructions_only',
              'requested_routes': rows, 'runner_sha256': sha(runner),
              'road_sha256': sha(road), 'authored_road_count': 2,
              'authored_road_link_count': 0,
              'approaching_roadway_vehicle_spawned': False,
              'tested_limitation': 'The two current 30 s exact requests move monotonically from road into driveway; they never request a return to roadway. Their runner spawns one motor vehicle and one pedestrian, no approaching roadway vehicle. Authored OpenDRIVE has no explicit road links. These source-bound constructions cannot measure roadway-entry vehicle yield.',
              'scope_limit': 'This does not prove a redesigned longer same-cell scenario impossible; such a redesign would require a new branch construction and its complete source-bound proof chain. Native topology and physical realization remain unverified.',
              'physical_or_legal_outcome_claimed': False}
    out = NATIVE / 'same-cell-return-feasibility.json'
    out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'receipt_sha256': sha(out)}))


if __name__ == '__main__':
    main()
