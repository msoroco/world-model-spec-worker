"""Build source-bound flagger response requests for both statutory locations.

These requests describe controller targets. They do not assert a flagger's
authorization, a visible signal, Native motion, or a legal result.
"""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASSIGNMENT = ROOT.name
SOURCE = Path('inputs') / ASSIGNMENT / 'assignment.json'
CAMERAS = {
    'overview': {'width': 1920, 'height': 1080, 'fov': 80},
    'approach': {'width': 1280, 'height': 720, 'fov': 80},
    'flagger': {'width': 1280, 'height': 720, 'fov': 75},
    'rear': {'width': 1280, 'height': 720, 'fov': 80},
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def road_xml():
    return ('<OpenDRIVE><header revMajor="1" revMinor="4" name="C183370-flagger" '
            'version="1" date="2026-11-26" north="20" south="-20" east="130" '
            'west="-90" vendor="full-train-worker"/><road id="1" '
            'name="driving-lane-beside-paved-shoulder" length="220" junction="-1">'
            '<link/><planView><geometry s="0" x="-90" y="0" hdg="0" length="220">'
            '<line/></geometry></planView><elevationProfile><elevation s="0" '
            'a="0" b="0" c="0" d="0"/></elevationProfile><lanes><laneOffset '
            's="0" a="0" b="0" c="0" d="0"/><laneSection s="0"><left/>'
            '<center><lane id="0" type="none" level="false"/></center><right>'
            '<lane id="-1" type="driving" level="false"><width sOffset="0" '
            'a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" '
            'color="white" width="0.12"/></lane><lane id="-2" type="shoulder" '
            'level="false"><width sOffset="0" a="2.5" b="0" c="0" d="0"/>'
            '<roadMark sOffset="0" type="solid" color="white" width="0.12"/>'
            '</lane></right></laneSection></lanes><objects/><signals/></road></OpenDRIVE>')


def requested_rows(cross_during_stop):
    rows = []
    for index in range(600):
        # Both cases share the same signal, route and stop line. The controller
        # alone changes: crossing at frame 200 versus 350 after release at 300.
        crossing = 200 if cross_during_stop else 350
        x = -40.0 + 40.0 * min(index / crossing, 1.0)
        if index > crossing:
            x = min(55.0, (index - crossing) * 0.23)
        rows.append({'frame': 1000 + index, 'time_s': index / 20,
                     'requested_center_x_m': round(x, 4),
                     'requested_center_y_m': -1.75,
                     'signal': 'stop' if 100 <= index < 300 else 'release',
                     'flagger_target_x_m': 0.0,
                     'flagger_target_y_m': -7.0,
                     'motorcycle_blueprint': 'vehicle.kawasaki.ninja',
                     'source_kind': 'authored_native_request'})
    return rows


def build(repo=Path('.')):
    repo = Path(repo).resolve()
    source = repo / SOURCE
    assignment = json.loads(source.read_text())
    if (assignment['assignment_id'] != ASSIGNMENT or
            assignment['law_id'] != 'NRS-484B-330-1' or
            assignment['cell_id'] != 'C183370' or
            assignment['actor'] != 'motorcycle_or_moped_operator'):
        raise ValueError('Frozen flagger assignment differs')
    outputs = []
    for suffix, crossing in (('probe_a', False), ('probe_b', True),
                             ('probe_c', False), ('probe_d', True)):
        folder = ROOT / 'native' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        road = folder / 'road.xodr'
        tracks = folder / 'requested-tracks.jsonl'
        road.write_text(road_xml() + '\n')
        tracks.write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                                  for row in requested_rows(crossing)))
        config = {
            'assignment_id': ASSIGNMENT,
            'case_id': ASSIGNMENT + '__' + suffix,
            'candidate_id': 'primary',
            'law_id': 'NRS-484B-330-1',
            'cell_id': 'C183370',
            'actor': 'motorcycle_or_moped_operator',
            'rate_hz': 20, 'duration_s': 30, 'frame_count': 600,
            'controller_policy': 'cross_during_stop' if crossing else 'hold_until_release',
            'stop_line_x_m': 0.0,
            'requested_route': 'driving_lane_beside_paved_shoulder',
            'signal_policy': {'stop_begin_frame': 1100, 'release_frame': 1300},
            'cameras': CAMERAS,
            'assignment_source': str(SOURCE),
            'assignment_sha256': digest(source),
            'road_sha256': digest(road),
            'tracks_sha256': digest(tracks),
            'source_review_required': [
                'flagger_authorization', 'temporary_zone_designation',
                'signal_governance_and_visibility', 'motorcycle_operator_control',
                'native_paved_shoulder_geometry'],
            'physical_or_legal_outcome_claimed': False,
        }
        if suffix in ('probe_c', 'probe_d'):
            config['zone_basis'] = 'clearly_marked_construction_or_maintenance_area'
            config['source_review_required'] = [
                'flagger_authorization', 'marked_highway_work_area',
                'signal_governance_and_visibility', 'motorcycle_operator_control',
                'native_paved_shoulder_geometry']
        (folder / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
        outputs.append({'case_id': config['case_id'], 'config': str(folder / 'config.json'),
                        'config_sha256': digest(folder / 'config.json')})
    return outputs


if __name__ == '__main__':
    print(json.dumps(build()))
