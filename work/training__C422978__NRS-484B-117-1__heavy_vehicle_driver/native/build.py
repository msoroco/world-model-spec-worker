"""Source-bound heavy-vehicle sidewalk requests; no physical observation."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
AID = CASE.name
CASES = ('reference', 'contrast')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
BLUEPRINT = 'vehicle.carlamotors.carlacola'
WIDTH_M = 2.4  # Prospective proxy, not a Native blueprint measurement.
SIDEWALK = (-7.5, -3.5)
ROAD = '''<?xml version="1.0" standalone="yes"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="4" name="C422978-heavy-sidewalk" version="1.00" date="2026-11-08" north="0" south="0" east="140" west="0" vendor="worker"/>
  <road name="C422978 two-way heavy-vehicle sidewalk" length="140" id="1" junction="-1">
    <link/><type s="0" type="town"><speed max="30" unit="mph"/></type>
    <planView><geometry s="0" x="0" y="0" hdg="0" length="140"><line/></geometry></planView>
    <elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/></elevationProfile>
    <lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/><laneSection s="0">
      <left><lane id="1" type="driving" level="false"><link/><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane></left>
      <center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" color="yellow" width="0.12"/></lane></center>
      <right>
        <lane id="-1" type="driving" level="false"><link/><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane>
        <lane id="-2" type="sidewalk" level="true"><link/><width sOffset="0" a="4.0" b="0" c="0" d="0"/><roadMark sOffset="0" type="curb" color="white" width="0.15"/></lane>
      </right>
    </laneSection></lanes><objects/><signals/>
  </road>
</OpenDRIVE>
'''
POLICIES = {
    'primary': {'lateral_start_frame': 60, 'lateral_duration_frames': 40, 'camera_fov_deg': 85},
    'fallback1': {'lateral_start_frame': 45, 'lateral_duration_frames': 40, 'camera_fov_deg': 85},
    'fallback2': {'lateral_start_frame': 60, 'lateral_duration_frames': 55, 'camera_fov_deg': 85},
    'fallback3': {'lateral_start_frame': 60, 'lateral_duration_frames': 40, 'camera_fov_deg': 105},
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def requested(case, policy):
    rows = []
    for frame in range(480):
        progress = min(1.0, max(0.0, (frame-policy['lateral_start_frame']) /
                                  policy['lateral_duration_frames']))
        smooth = progress*progress*(3-2*progress)
        y = -1.75 if case == 'reference' else round(-1.75 - 3.75*smooth, 4)
        rows.append({'frame': frame, 'time_s': round(frame/20, 4),
                     'subject_blueprint_request': BLUEPRINT,
                     'requested_center_xy_m': [round(10+4*frame/20, 4), y],
                     'requested_speed_mps': 4.0,
                     'prospective_body_width_m': WIDTH_M,
                     'camera_fov_deg': policy['camera_fov_deg'],
                     'driveway_or_alley_requested': False,
                     'source_kind': 'authored_native_request'})
    return rows


def metrics(rows):
    overlap = [r['frame'] for r in rows if r['requested_speed_mps'] > .1 and
               r['requested_center_xy_m'][1]-WIDTH_M/2 < SIDEWALK[1] and
               r['requested_center_xy_m'][1]+WIDTH_M/2 > SIDEWALK[0]]
    inside = [r['frame'] for r in rows if r['requested_speed_mps'] > .1 and
              r['requested_center_xy_m'][1]-WIDTH_M/2 >= SIDEWALK[0] and
              r['requested_center_xy_m'][1]+WIDTH_M/2 <= SIDEWALK[1]]
    return {'requested_moving_sidewalk_overlap_frames': len(overlap),
            'first_requested_overlap_frame': overlap[0] if overlap else None,
            'requested_full_body_inside_frames': len(inside),
            'first_requested_full_body_inside_frame': inside[0] if inside else None}


def build():
    assignment = ROOT / 'inputs' / AID / 'assignment.json'
    plan = CASE / 'case-plan.json'
    source = json.loads(assignment.read_text())
    if source['cell_id'] != 'C422978' or source['law_id'] != 'NRS-484B-117-1' or source['actor'] != 'heavy_vehicle_driver':
        raise ValueError('Frozen heavy-vehicle assignment differs')
    if 'sidewalk area' not in source['law_record']['text']:
        raise ValueError('Frozen sidewalk statute differs')
    road = HERE / 'road.xodr'
    road.write_text(ROAD)
    entries = []
    for case in CASES:
        for candidate in CANDIDATES:
            policy = POLICIES[candidate]
            folder = HERE / 'drafts' / case / candidate
            folder.mkdir(parents=True, exist_ok=True)
            rows = requested(case, policy)
            tracks = folder / 'requested-tracks.jsonl'
            tracks.write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows))
            save(folder / 'config.json', {
                'case_id': AID + '__' + case, 'case_suffix': case,
                'candidate_id': candidate, 'law_id': 'NRS-484B-117-1',
                'cell_id': 'C422978', 'actor': 'heavy_vehicle_driver',
                'rate_hz': 20, 'duration_s': 24, 'policy': policy,
                'road_sha256': sha(road), 'tracks_sha256': sha(tracks),
                'assignment_sha256': sha(assignment), 'case_plan_sha256': sha(plan),
                'status': 'unselected_native_request'})
            entries.append({'case_id': AID + '__' + case, 'candidate_id': candidate,
                            'config': str((folder/'config.json').relative_to(CASE)),
                            'tracks': str(tracks.relative_to(CASE)), 'metric': metrics(rows),
                            'trigger': {
                                'primary': 'baseline requested heavy-vehicle motion',
                                'fallback1': 'saved original body first enters sidewalk later than frame 75',
                                'fallback2': 'saved original full-body sidewalk occupancy below 360 frames',
                                'fallback3': 'source-hashed original camera body visibility below 75 percent',
                            }[candidate]})
    manifest = {'format': 'c422978-heavy-sidewalk-native-request-v1',
                'assignment_sha256': sha(assignment), 'case_plan_sha256': sha(plan),
                'road_sha256': sha(road), 'entries': entries,
                'physical_or_legal_result_observed': False, 'delivery_ready': False}
    save(HERE/'drafts/manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps({'drafts': len(build()['entries'])}))
