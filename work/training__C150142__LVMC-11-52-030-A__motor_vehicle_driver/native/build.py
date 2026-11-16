"""Author a red-curb parking pair and three distinct candidate requests each.

These are CPU construction requests, not Native motion or exception findings.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]
AID = FOLDER.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def road():
    return '''<?xml version="1.0" standalone="yes"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="4" name="C150142 authored red curb" version="1.00" date="2026-11-16" north="10" south="-10" east="100" west="0" vendor="worker"/>
  <road name="one-way parking beside painted curb" length="100" id="150142" junction="-1">
    <planView><geometry s="0" x="0" y="0" hdg="0" length="100"><line/></geometry></planView>
    <elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/></elevationProfile>
    <lanes><laneSection s="0"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" width="0.15" color="yellow"/></lane></center>
      <right><lane id="-1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" width="0.15" color="white"/></lane>
      <lane id="-2" type="parking" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" width="0.15" color="white"/><roadMark sOffset="30" type="solid" width="0.2" color="red"/><roadMark sOffset="50" type="solid" width="0.15" color="white"/></lane></right></laneSection></lanes>
  </road>
</OpenDRIVE>
'''


def rows(target, approach_frames):
    out = []
    for index in range(240):
        fraction = min(1, (index + 1) / approach_frames)
        x = 5 + (target - 5) * fraction
        out.append({'frame': index, 'time_s': (index + 1) / 20,
                    'requested_ego_x_m': round(x, 6),
                    'requested_ego_y_m': -6.8,
                    'requested_parked': index + 1 > approach_frames,
                    'requested_red_curb_occupancy':
                        index + 1 > approach_frames and 30 <= target <= 50,
                    'source_kind': 'authored_controller_request',
                    'observed_native_motion': False})
    return out


def build():
    HERE.mkdir(exist_ok=True)
    road_path = HERE / 'red-curb-road.xodr'
    road_path.write_text(road())
    assignment = REPO / 'inputs' / AID / 'assignment.json'
    plan = FOLDER / 'case-plan.json'
    entries = []
    risks = {
        'primary': 'none',
        'fallback1': 'observed longitudinal overshoot reaches red paint boundary',
        'fallback2': 'red curb or ego body obscured in overview pixels',
        'fallback3': 'stationary interval insufficient for reviewed parking observation',
    }
    for witness, target in (('reference', 40), ('contrast', 60)):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            approach = 180 if candidate == 'fallback1' else 90 if candidate == 'fallback3' else 120
            tracks = rows(target, approach)
            directory = HERE / 'drafts' / witness / candidate
            directory.mkdir(parents=True, exist_ok=True)
            track_path = directory / 'requested-tracks.jsonl'
            track_path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                                          for row in tracks))
            config = {'format': 'c150142-red-curb-request-v1',
                      'assignment_id': AID, 'case_id': AID + '__' + witness,
                      'candidate_id': candidate, 'law_id': 'LVMC-11-52-030-A',
                      'cell_id': 'C150142', 'actor': 'motor_vehicle_driver',
                      'road_sha256': sha(road_path),
                      'controller_sha256': sha(HERE / 'parking_controller.py'),
                      'assignment_sha256': sha(assignment),
                      'case_plan_sha256': sha(plan),
                      'tracks_sha256': sha(track_path),
                      'frames': 240, 'rate_hz': 20,
                      'painted_curb': {'color': 'red', 'start_x_m': 30,
                                       'end_x_m': 50, 'curb_y_m': -7},
                      'requested_target_x_m': target,
                      'requested_approach_frames': approach,
                      'camera_policy': 'elevated_overview' if candidate == 'fallback2' else 'standard',
                      'risk_trigger': risks[candidate],
                      'ordinary_vehicle': True, 'exception_claimed': False,
                      'original_native_observed': False,
                      'legal_verdict': None,
                      'status': 'unselected_native_request'}
            write_json(directory / 'config.json', config)
            entries.append({'case_id': config['case_id'], 'candidate_id': candidate,
                            'config_sha256': sha(directory / 'config.json'),
                            'tracks_sha256': sha(track_path),
                            'risk_trigger': risks[candidate],
                            'requested_red_stopped_frames': sum(
                                row['requested_red_curb_occupancy'] for row in tracks),
                            'original_native_observed': False})
    result = {'format': 'c150142-red-curb-draft-construction-v1',
              'assignment_id': AID, 'assignment_sha256': sha(assignment),
              'case_plan_sha256': sha(plan), 'road_sha256': sha(road_path),
              'controller_sha256': sha(HERE / 'parking_controller.py'),
              'entries': entries, 'delivery_ready': False,
              'original_native_observed': False}
    write_json(HERE / 'manifest.json', result)
    return result


if __name__ == '__main__':
    print(json.dumps({'entries': len(build()['entries']), 'delivery_ready': False}))
