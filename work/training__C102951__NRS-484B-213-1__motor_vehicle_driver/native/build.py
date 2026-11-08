"""Author source-bound passing requests. These are targets, not CARLA observations."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
AID = CASE.name
DISTANCES = (70, 120, 170)
BLUEPRINT = 'vehicle.tesla.model3'
POLICIES = {
    'primary': {'entry_start': 30, 'entry_end': 50, 'return_start': 115,
                'return_end': 140, 'ego_speed_mps': 16, 'mode': 'complete_pass'},
    'fallback1': {'entry_start': 45, 'entry_end': 65, 'return_start': 130,
                  'return_end': 155, 'ego_speed_mps': 16, 'mode': 'delayed_entry'},
    'fallback2': {'entry_start': 30, 'entry_end': 50, 'return_start': 102,
                  'return_end': 127, 'ego_speed_mps': 18, 'mode': 'shorter_exposure'},
    'fallback3': {'entry_start': 30, 'entry_end': 50, 'return_start': 65,
                  'return_end': 85, 'ego_speed_mps': 16, 'mode': 'abort_and_rejoin'},
}
ROAD = '''<?xml version="1.0" standalone="yes"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="4" name="C102951-two-way-crest" version="1.00" date="2026-11-08" north="0" south="0" east="600" west="-200" vendor="worker"/>
  <road name="C102951 two-lane two-direction hill crest" length="800" id="1" junction="-1">
    <link/><type s="0" type="rural"><speed max="35" unit="mph"/></type>
    <planView><geometry s="0" x="-200" y="0" hdg="0" length="800"><line/></geometry></planView>
    <elevationProfile>
      <elevation s="0" a="0" b="0" c="0" d="0"/>
      <elevation s="200" a="0" b="0" c="0.0002" d="-0.000000888888888889"/>
      <elevation s="350" a="1.5" b="0" c="-0.0002" d="0.000000888888888889"/>
      <elevation s="500" a="0" b="0" c="0" d="0"/>
    </elevationProfile>
    <lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/><laneSection s="0">
      <left><lane id="1" type="driving" level="false"><link/><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane></left>
      <center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="broken" color="yellow" width="0.12"/></lane></center>
      <right><lane id="-1" type="driving" level="false"><link/><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane></right>
    </laneSection></lanes><objects/><signals/>
  </road>
</OpenDRIVE>
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lateral(frame, policy):
    a, b = policy['entry_start'], policy['entry_end']
    c, d = policy['return_start'], policy['return_end']
    if frame < a:
        return -1.75
    if frame < b:
        return -1.75 + 3.5 * (frame-a)/(b-a)
    if frame < c:
        return 1.75
    if frame < d:
        return 1.75 - 3.5 * (frame-c)/(d-c)
    return -1.75


def requests(distance, policy):
    entry = next(i for i in range(480) if lateral(i, policy)+.9 > 0)
    ego_entry_x = 10 + policy['ego_speed_mps']*entry/20
    oncoming_zero_x = ego_entry_x + 4.4 + distance + 12*entry/20
    for i in range(480):
        t = i/20
        yield {'frame': i, 'time_s': round(t, 4),
               'source_kind': 'authored_native_request',
               'ego_blueprint_request': BLUEPRINT,
               'ego_center_xy_m': [round(10+policy['ego_speed_mps']*t, 4),
                                   round(lateral(i, policy), 4)],
               'ego_speed_mps': policy['ego_speed_mps'],
               'overtaken_center_xy_m': [round(40+8*t, 4), -1.75],
               'overtaken_speed_mps': 8,
               'oncoming_center_xy_m': [round(oncoming_zero_x-12*t, 4), 1.75],
               'oncoming_speed_mps': 12,
               'requested_entry_oncoming_body_gap_m': distance,
               'requested_driver_eye_clear_m': distance,
               'sightline_assumed_visible': True}


def build():
    source_path = ROOT/'inputs'/AID/'assignment.json'
    source = json.loads(source_path.read_text())
    plan_path = CASE/'case-plan.json'
    plan = json.loads(plan_path.read_text())
    if (source['cell_id'], source['law_id'], source['actor']) != ('C102951', 'NRS-484B-213-1', 'motor_vehicle_driver'):
        raise ValueError('Frozen assignment differs')
    if sorted(case['requested_setting'] for case in plan['cases']) != list(DISTANCES):
        raise ValueError('Frozen passing sweep differs')
    road = HERE/'road.xodr'
    road.write_text(ROAD)
    entries = []
    for distance in DISTANCES:
        for candidate, policy in POLICIES.items():
            folder = HERE/'drafts'/str(distance)/candidate
            folder.mkdir(parents=True, exist_ok=True)
            tracks = folder/'requested-tracks.jsonl'
            tracks.write_text(''.join(json.dumps(row, sort_keys=True)+'\n'
                                      for row in requests(distance, policy)))
            config = {'format': 'c102951-native-request-v1',
                      'case_id': AID+'__'+str(distance), 'distance_m': distance,
                      'candidate_id': candidate, 'cell_id': 'C102951',
                      'law_id': 'NRS-484B-213-1', 'actor': 'motor_vehicle_driver',
                      'rate_hz': 20, 'duration_s': 24, 'policy': policy,
                      'assignment_sha256': sha(source_path),
                      'case_plan_sha256': sha(plan_path), 'road_sha256': sha(road),
                      'tracks_sha256': sha(tracks), 'status': 'unselected_native_request'}
            (folder/'config.json').write_text(json.dumps(config, indent=2)+'\n')
            entries.append({'case_id': config['case_id'], 'candidate_id': candidate,
                            'config': str((folder/'config.json').relative_to(CASE)),
                            'tracks': str(tracks.relative_to(CASE)),
                            'request_mode': policy['mode']})
    manifest = {'format': 'c102951-native-request-manifest-v1',
                'assignment_sha256': sha(source_path),
                'case_plan_sha256': sha(plan_path), 'road_sha256': sha(road),
                'entries': entries, 'original_native_observed': False,
                'highway_status_reviewed': False, 'delivery_ready': False}
    (HERE/'drafts/manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    print(json.dumps({'requests': len(build()['entries'])}))
