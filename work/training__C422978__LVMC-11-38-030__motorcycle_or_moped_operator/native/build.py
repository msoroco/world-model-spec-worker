"""Source-bound C422978 motorcycle/sidewalk construction requests.

These are Native inputs and synthetic CPU checks, never observed motorcycle motion.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
AID = CASE.name
CASES = ('witness_1', 'witness_2')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
WIDTH_M = 0.8
ROAD = '''<?xml version="1.0" standalone="yes"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="4" name="C422978-sidewalk" version="1.00" date="2026-11-08" north="0" south="0" east="140" west="0" vendor="worker"/>
  <road name="C422978 two-way with right sidewalk" length="140" id="1" junction="-1">
    <link/><type s="0" type="town"><speed max="30" unit="mph"/></type>
    <planView><geometry s="0" x="0" y="0" hdg="0" length="140"><line/></geometry></planView>
    <elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/></elevationProfile>
    <lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/><laneSection s="0">
      <left><lane id="1" type="driving" level="false"><link/><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" weight="standard" color="white" width="0.12"/></lane></left>
      <center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" weight="standard" color="yellow" width="0.12"/></lane></center>
      <right>
        <lane id="-1" type="driving" level="false"><link/><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" weight="standard" color="white" width="0.12"/></lane>
        <lane id="-2" type="sidewalk" level="true"><link/><width sOffset="0" a="2.0" b="0" c="0" d="0"/><roadMark sOffset="0" type="curb" weight="standard" color="white" width="0.15"/></lane>
      </right>
    </laneSection></lanes><objects/><signals/>
  </road>
</OpenDRIVE>
'''
POLICIES = {
    'primary': {'lateral_start_frame': 60, 'lateral_duration_frames': 40,
                'camera_fov_deg': 85, 'speed_mps': 4.0},
    'fallback1': {'lateral_start_frame': 45, 'lateral_duration_frames': 40,
                  'camera_fov_deg': 85, 'speed_mps': 4.0},
    'fallback2': {'lateral_start_frame': 60, 'lateral_duration_frames': 55,
                  'camera_fov_deg': 85, 'speed_mps': 4.0},
    'fallback3': {'lateral_start_frame': 60, 'lateral_duration_frames': 40,
                  'camera_fov_deg': 100, 'speed_mps': 4.0},
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in values))


def requested(case, policy):
    output = []
    for frame in range(480):
        x = round(10 + policy['speed_mps'] * frame / 20, 4)
        if case == 'witness_1':
            y = -1.75
        else:
            fraction = max(0, min(1, (frame - policy['lateral_start_frame']) /
                                     policy['lateral_duration_frames']))
            y = round(-1.75 - 2.75 * fraction, 4)
        output.append({'frame': frame, 'time_s': round(frame / 20, 4),
                       'motorcycle_blueprint': 'vehicle.kawasaki.ninja',
                       'requested_center_xy_m': [x, y],
                       'requested_speed_mps': policy['speed_mps'],
                       'requested_body_width_m': WIDTH_M,
                       'source_kind': 'authored_native_request'})
    return output


def occupancy(packet):
    # The sidewalk is the authored lane -2, y in [-5.5, -3.5].
    moving = [r['frame'] for r in packet if r['requested_speed_mps'] > 0.1]
    overlap = [r['frame'] for r in packet if r['requested_speed_mps'] > 0.1 and
               r['requested_center_xy_m'][1] - WIDTH_M / 2 < -3.5 and
               r['requested_center_xy_m'][1] + WIDTH_M / 2 > -5.5]
    return {'requested_moving_frames': len(moving),
            'requested_sidewalk_overlap_frames': len(overlap),
            'first_requested_overlap_frame': overlap[0] if overlap else None}


def build():
    assignment = ROOT / 'inputs' / AID / 'assignment.json'
    plan = CASE / 'case-plan.json'
    if json.loads(assignment.read_text())['cell_id'] != 'C422978':
        raise ValueError('Frozen assignment differs')
    (HERE / 'road.xodr').write_text(ROAD)
    entries = []
    for case in CASES:
        for candidate in CANDIDATES:
            policy = POLICIES[candidate]
            folder = HERE / 'drafts' / case / candidate
            packet = requested(case, policy)
            rows(folder / 'requested-tracks.jsonl', packet)
            metric = occupancy(packet)
            write(folder / 'config.json', {
                'case_id': AID + '__' + case, 'case_suffix': case,
                'candidate_id': candidate, 'cell_id': 'C422978',
                'law_id': 'LVMC-11-38-030', 'actor': 'motorcycle_or_moped_operator',
                'rate_hz': 20, 'duration_s': 24, 'policy': policy,
                'road_sha256': sha(HERE / 'road.xodr'),
                'tracks_sha256': sha(folder / 'requested-tracks.jsonl'),
                'assignment_sha256': sha(assignment), 'case_plan_sha256': sha(plan),
                'status': 'unselected_native_request'})
            entries.append({'case_id': AID + '__' + case, 'candidate_id': candidate,
                            'config': str((folder / 'config.json').relative_to(CASE)),
                            'tracks': str((folder / 'requested-tracks.jsonl').relative_to(CASE)),
                            'metric': metric,
                            'trigger': {
                                'primary': 'baseline requested motion',
                                'fallback1': 'measured late sidewalk entry from saved original body frames',
                                'fallback2': 'measured sidewalk occupancy below target window',
                                'fallback3': 'measured original-camera motorcycle visibility below 75 percent',
                            }[candidate]})
    manifest = {'format': 'c422978-sidewalk-native-request-v1',
                'assignment_sha256': sha(assignment),
                'case_plan_sha256': sha(plan),
                'road_sha256': sha(HERE / 'road.xodr'),
                'entries': entries, 'original_native_observed': False,
                'delivery_ready': False}
    write(HERE / 'drafts' / 'manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps({'drafts': len(build()['entries'])}))
