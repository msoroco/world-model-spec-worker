"""Generate compact synthetic hose fixtures with separate authority source shapes."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / 'work/training__C394566__LVMC-11-48-060__motor_vehicle_driver/diagnostic-probe_01.json'
AID = HERE.name
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
sys.path.insert(0, str(HERE / 'runtime_native'))
from layout import HOSE_LINE, HOSE_RADIUS_M, open_drive


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows)


def rows(text):
    return [json.loads(line) for line in text.splitlines()]


for suffix in ('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2'):
    spec = json.loads(BASE.read_text())
    spec['files'] = {key: value for key, value in spec['files'].items() if key in
        ('trace.jsonl', 'video_frames.jsonl', 'capture/recorder_info.txt',
         'capture/evidence.jsonl', 'capture/native/frames.jsonl', 'capture/manifest.json')}
    case = AID + '__' + suffix
    crossing = suffix != 'witness_1'
    consent = suffix == 'exception_1_2'
    y = -3.5 if crossing else -8.5
    spec['files']['road.xodr'] = open_drive()
    trace = rows(spec['files']['trace.jsonl'])
    mapping = rows(spec['files']['video_frames.jsonl'])
    evidence = rows(spec['files']['capture/evidence.jsonl'])
    frames = rows(spec['files']['capture/native/frames.jsonl'])
    actors = []
    camera_rows = []
    for i in range(600):
        native = mapping[i]['native_frame']
        time = i / 20
        x = round(-20 + min(i, 118) * .2, 3)
        speed = 4 if i < 118 else 0
        body = [[round(x + dx, 3), y + dy, z] for dx, dy in ((-2, -1), (-2, 1), (2, -1), (2, 1)) for z in (0, 2)]
        footprint = [[x - 2, y - 1], [x + 2, y - 1], [x + 2, y + 1], [x - 2, y + 1]]
        mapping[i].update(time_s=time, camera_native_frames={name: native for name in CAMERAS})
        trace[i].update(frame=native, time_s=time, position={'x': x, 'y': y, 'z': 0},
                        position_m=[x, y, 0], speed_mps=speed, speed_mph=speed * 2.2369362921,
                        velocity_mps=[speed, 0, 0])
        evidence[i].update(original_frame=native, replay_frame=native,
                           recording_time_s=time, replay_simulation_time_s=time)
        evidence[i]['ego'].update(position_m=[x, y, 0], speed_mps=speed, body_vertices_m=body)
        evidence[i]['world'].pop('weather', None)
        evidence[i]['world']['road_projection']['s_m'] = round(evidence[i]['world']['road_projection']['s_m'], 3)
        frames[i]['simulation_time'] = time
        original = evidence[i]['original_observations']
        original.update(frame=native, time_s=time)
        subject = next(a for a in original['participants'] if a['actor_id'] == evidence[i]['actor_id'])
        subject.update(position_m=[x, y, 0], velocity_mps=[speed, 0, 0],
                       speed_mps=speed, body_vertices_m=body)
        graph = spec['graphs'][i]
        graph['attributes']['observed_evidence'] = original
        graph['nodes'][0]['attributes']['vertex'] = [x, y, 0]
        graph['nodes'][0]['attributes']['threedbbox'] = body
        actors.append({'frame': i, 'case_id': case, 'time_s': time,
                       'native_frame': native, 'actor_id': evidence[i]['actor_id'],
                       'vehicle_type': 'vehicle.lincoln.mkz_2020',
                       'driver_role': 'synthetic_subject_human_driver',
                       'ego_footprint_xy_m': footprint, 'ego_speed_mps': speed})
        for name in CAMERAS:
            camera_rows.append({'frame': i, 'camera': name, 'native_frame': native,
                                'rgb_sha256': sha(name + ':' + str(i))})
    spec['files']['trace.jsonl'] = lines(trace)
    spec['files']['video_frames.jsonl'] = lines(mapping)
    spec['files']['capture/evidence.jsonl'] = lines(evidence)
    spec['files']['capture/native/frames.jsonl'] = lines(frames)
    spec['files']['actor-sources.jsonl'] = lines(actors)
    spec['files']['camera-frames.jsonl'] = lines(camera_rows)
    spec['files']['hose-source.json'] = json.dumps({'case_id': case, 'source_kind': 'synthetic_cpu',
        'way_kind': 'highway', 'way_designation_status': 'synthetic_diagnostic',
        'public_access_status': 'synthetic_diagnostic',
        'hose_centerline_xy_m': HOSE_LINE, 'hose_radius_m': HOSE_RADIUS_M,
        'hose_asset_status': 'synthetic_diagnostic',
        'department_hose_source': 'asset_inventory',
        'purpose': 'practice_run', 'cover_inventory_source': 'asset_inventory',
        'cover_or_ramp_present': False, 'official_in_command_id': 301,
        'consent_record': {'type': 'signed_log', 'official_in_command_id': 301,
            'vehicle_case_id': case, 'permission': 'drive_over_hose'} if consent else None}) + '\n'
    spec['files']['department-presence.json'] = json.dumps({
        'source_kind': 'synthetic_cpu', 'fire_apparatus_actor_id': 300,
        'fire_apparatus_blueprint': 'vehicle.carlamotors.firetruck',
        'command_role_actor_id': 301,
        'command_role_status': 'synthetic_diagnostic',
        'department_affiliation_confirmed': False}) + '\n'
    spec['files']['communication-setup.json'] = json.dumps({
        'source_kind': 'synthetic_cpu', 'case_id': case, 'official_actor_id': 301,
        'communication_setup': 'authored_radio_permission' if consent else 'explicit_no_communication',
        'permission': 'drive_over_hose' if consent else None,
        'timing': 'before_first_capture_frame', 'scope_case_id': case,
        'legal_consent_confirmed': False}) + '\n'
    spec['files']['way-review.json'] = json.dumps({'review_status': 'synthetic_diagnostic',
        'reviewer': 'synthetic fixture generator', 'source': 'synthetic way dedication record',
        'road_sha256': sha(spec['files']['road.xodr']), 'way_kind': 'highway',
        'road_access_basis': 'synthetic public vehicular access and highway dedication',
        'hose_on_actual_route': True}) + '\n'
    spec['files']['hose-review.json'] = json.dumps({'review_status': 'synthetic_diagnostic',
        'reviewer': 'synthetic fixture generator', 'source': 'synthetic department asset inventory',
        'hose_source_sha256': sha(spec['files']['hose-source.json']),
        'department_presence_sha256': sha(spec['files']['department-presence.json']),
        'pixel_sha256': 'synthetic_rgb_source',
        'department_affiliation': True, 'fire_use_purpose': 'practice_run',
        'protection_arrangements': 'synthetic no barrier, cover, ramp or other protection arrangement',
        'unprotected': True}) + '\n'
    spec['files']['command-review.json'] = json.dumps({'review_status': 'synthetic_diagnostic',
        'reviewer': 'synthetic fixture generator', 'source': 'synthetic command communication log',
        'actor_sha256': sha(spec['files']['actor-sources.jsonl']), 'case_id': case,
        'communication_setup_sha256': sha(spec['files']['communication-setup.json']),
        'vehicle_class': 'ordinary_motor_vehicle', 'human_driver': True,
        'official_identity': 'synthetic_command_301', 'command_status': 'official_in_command',
        'communication_status': 'documented_consent' if consent else 'explicit_none',
        'permission': 'drive_over_hose' if consent else None,
        'scope_case_id': case if consent else None,
        'timing_source': 'synthetic signed log before passage' if consent else None,
        'monitoring_window': 'full_original_capture' if not consent else None}) + '\n'
    spec['files']['fixture-provenance.json'] = json.dumps({'diagnostic_fixture': True,
        'source': 'synthetic hose source shape', 'physical_acceptance_claimed': False}) + '\n'
    spec['files']['law-text.json'] = json.dumps({'source': 'NRS 484B.913',
        'text': json.loads((ROOT / 'inputs' / AID / 'assignment.json').read_text())['law']['text']}) + '\n'
    manifest = json.loads(spec['files']['capture/manifest.json'])
    manifest.update(case_id=case, frames=600,
                    sources={'road.xodr': sha(spec['files']['road.xodr']),
                             'trace.jsonl': sha(spec['files']['trace.jsonl'])})
    spec['files']['capture/manifest.json'] = json.dumps(manifest, separators=(',', ':')) + '\n'
    for video, name in zip(spec['videos'], CAMERAS):
        video['path'] = name + '.mkv'
        if name == 'overview':
            video['width'], video['height'] = 1920, 1080
    target = HERE / ('diagnostic-' + suffix + '.json')
    target.write_text(json.dumps(spec, separators=(',', ':'), allow_nan=False) + '\n')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': str(target.relative_to(ROOT)),
                           'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}],
              'generator': {'source': str(target.relative_to(ROOT)),
                            'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}}
    (HERE / ('diagnostic-' + suffix + '-recipe.json')).write_text(json.dumps(recipe, indent=2) + '\n')
    print(suffix, target.stat().st_size)
