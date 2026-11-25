"""Create source-shaped, explicitly synthetic nine-frame green diagnostics."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
SUFFIXES = ('green_clear', 'green_vehicle_present', 'green_pedestrian_present', 'green_pedestrian_late')


def sha(data):
    return hashlib.sha256(data.encode()).hexdigest()


def make(suffix):
    fixture = json.loads((REPO / 'runtime/fixtures/example.json').read_text())
    files = fixture['files']
    frames = [json.loads(row) for row in files['video_frames.jsonl'].splitlines() if row.strip()]
    if len(frames) != 9:
        raise ValueError('pinned example frame count changed')
    source_names = ('map-source.json', 'signal-source.json', 'route-source.json', 'crosswalk-source.json')
    for name in source_names:
        files[name] = json.dumps({'diagnostic_only': True, 'original_kind': name}, sort_keys=True) + '\n'
    original_refs = [{'path': name, 'sha256': sha(files[name])} for name in source_names]
    site = {'cell_id': 'C111125', 'actor': 'motor_vehicle_driver',
            'original_sources': original_refs, 'map_source_path': source_names[0],
            'signal_source_path': source_names[1], 'route_source_path': source_names[2],
            'crosswalk_source_path': source_names[3],
            'official_head_id': 'diagnostic-head-7', 'ego_approach_id': 'diagnostic-west',
            'facing_relation': True, 'ego_route_xy': [[-4, 0], [0, 0], [4, 0]],
            'straight_tolerance_m': 0.2,
            'intersection_polygon_xy': [[-1,-1],[1,-1],[1,1],[-1,1]],
            'adjacent_crosswalk_polygon_xy': [[-1,2],[1,2],[1,3],[-1,3]],
            'native_map_name': 'DiagnosticStraightIntersection',
            'initial_lit_aspects': ['circular_green'], 'spawn_z_m': 0.3,
            'approach_yaw_deg': 0, 'other_user_spawn_xy': [0, 2.5]}
    files['site.json'] = json.dumps(site, sort_keys=True) + '\n'
    other = None if suffix == 'green_clear' else ('motor_vehicle' if suffix == 'green_vehicle_present' else 'pedestrian')
    rows = []
    for i, frame in enumerate(frames):
        ego_x = [-4,-3,-2,-1,0,1,2,3,4][i]
        if other == 'motor_vehicle': position = [0,0]
        elif suffix == 'green_pedestrian_present': position = [0,2.5]
        elif suffix == 'green_pedestrian_late': position = [0,4] if i < 4 else [0,2.5]
        else: position = None
        persons = [] if other is None else [{'id':'diagnostic-other-1', 'kind':other,
            'xy':position, 'lawful_presence_source':'other-context.json'}]
        rows.append({'frame':frame['carla_frame'], 'elapsed_seconds':frame['time_s'],
            'official_head_id':site['official_head_id'], 'facing_approach_id':site['ego_approach_id'],
            'lit_aspects':['circular_green'], 'ego_xy':[ego_x,0], 'other_users':persons})
    files['original-events.json'] = json.dumps(rows, sort_keys=True) + '\n'
    files['other-context.json'] = json.dumps({'diagnostic_only': True, 'other_user_kind': other,
                                               'lawful_presence_verdict': None}) + '\n'
    files['camera-profile.json'] = json.dumps({'fps':20, 'views': {'overview':[1920,1080],
        'approach':[1280,720], 'reference_corner':[1280,720], 'driver_reference':[1280,720]}}) + '\n'
    packet = {'assignment_id':AID, 'case_id':AID+'__'+suffix, 'case_suffix':suffix,
              'candidate':'primary', 'attempt_id':'diagnostic-'+suffix,
              'recording_id':'diagnostic-'+suffix,
              'site_ref':{'path':'site.json','sha256':sha(files['site.json'])},
              'event_ref':{'path':'original-events.json','sha256':sha(files['original-events.json'])},
              'duration_frames':len(frames), 'camera_profile_sha256':sha(files['camera-profile.json'])}
    files['original-green-packet.json'] = json.dumps(packet, sort_keys=True) + '\n'
    names = ('original-green-packet.json', 'site.json', 'original-events.json',
             'video_frames.jsonl')
    files['acquisition.json'] = json.dumps({name: {'kind':'original_native','sha256':sha(files[name])}
                                            for name in names}, sort_keys=True) + '\n'
    # The runtime example itself marks synthetic diagnostics and four generated camera videos.
    provenance = json.loads(files['fixture-provenance.json'])
    provenance.update({'diagnostic_fixture':True, 'physical_acceptance_claimed':False,
                       'scope':'CPU synthetic green source-shape diagnostic'})
    files['fixture-provenance.json'] = json.dumps(provenance, sort_keys=True) + '\n'
    path = ROOT / ('diagnostic-' + suffix + '.json')
    path.write_text(json.dumps(fixture, ensure_ascii=False, separators=(',', ':')) + '\n')
    recipe = {'format':'worker-fixture-recipe',
              'sources':[{'path':'diagnostic-input.json',
                          'source':str((REPO/'inputs'/AID/'assignment.json').relative_to(REPO)),
                          'sha256':hashlib.sha256((REPO/'inputs'/AID/'assignment.json').read_bytes()).hexdigest()}],
              'generator':{'source':str(path.relative_to(REPO)),
                           'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}
    recipe_path = ROOT / ('diagnostic-' + suffix + '-recipe.json')
    recipe_path.write_text(json.dumps(recipe, sort_keys=True, indent=2) + '\n')
    return str(recipe_path.relative_to(REPO))


if __name__ == '__main__':
    print(json.dumps([make(suffix) for suffix in SUFFIXES]))
