"""Build exact synthetic 600-frame fixtures for public software compatibility.

These textual recipes are schema tests, never original railway observations.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from rail_scene import sight_row
from rail_sight import speed_request

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'work/training__C202463__NRS-484B-560-3__motor_vehicle_driver/diagnostic-probe_a.json'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha_text(value):
    return hashlib.sha256(value.encode()).hexdigest()


def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows_text(rows):
    return ''.join(json.dumps(row, separators=(',', ':'))+'\n' for row in rows)


def video_hash():
    out = ROOT / '.runtime-work/c202465-lvmc-overview-reference.mkv'
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                        '-f','lavfi','-i','color=c=blue:s=1920x1080:r=20',
                        '-frames:v','600','-an','-c:v','ffv1','-threads','1',
                        '-fflags','+bitexact','-flags:v','+bitexact',str(out)],
                       check=True, timeout=120)
    return sha_file(out)


def blocker_for(mode):
    if mode == 'clear_both':
        return []
    edges = {
        'left_sight_obscured': [[-2,-125],[-2,-.3]],
        'right_sight_obscured': [[-2,.3],[-2,125]],
        'crossing_obscured': [[-2,-.3],[-2,.3]],
    }
    return [{'source_ref':'synthetic:opaque-'+mode, 'opaque':True,
             'edge_xy_m':edges[mode]}]


def build_case(template, case, overview_sha):
    spec = {'files': dict(template['files']),
            'graphs': json.loads(json.dumps(template['graphs'])),
            'videos': json.loads(json.dumps(template['videos']))}
    files = spec['files']
    for name in list(files):
        if name in ('actors.jsonl','gate.jsonl','rail-inventory.json','geometry.json') or name.startswith('rail-review/'):
            del files[name]
    design = case['construction_design']
    road_sha = sha_text(files['road.xodr'])
    source_records = {
        'railway': {'crossing_kind':'at_grade','railway_type':'electric',
                    'railway_identity':'synthetic fixture only','crossing_xyz_m':[0,0,0],
                    'rail_unit_direction_xy':[0,1],'surveyed_left_extent_m':122,
                    'surveyed_right_extent_m':122,'rail_vehicle_lateral_tolerance_m':1.5,
                    'rail_vehicle_actor_ids':{'left':2,'right':3}},
        'approach': {'driver_role':'motor_vehicle_driver','municipal_jurisdiction_verified':True,
                     'approach_maneuver':'cross_railway','approach_direction_xy':[1,0],
                     'surveyed_approach_length_m':50,'ego_spawn_xyz_m':[-50,0,2],
                     'ego_spawn_yaw_deg':0},
        'flagman': {'source_method':'original_actor_and_duty_readback',
                    'on_duty_at_capture_start':design['exception_state']=='flagman_on_duty'},
        'signal': {'source_method':'original_device_visibility_and_state_readback',
                   'installed':design['exception_state'].startswith(('visible_','installed_')),
                   'clearly_visible':design['exception_state'].startswith('visible_'),
                   'indicates_immediate_approach':design['exception_state']=='visible_active_signal'},
    }
    for role, values in source_records.items():
        source = 'Synthetic schema-only '+role+'; no physical railway review.\n'
        files['original-source-review/'+role+'.source.txt'] = source
        record = dict(values,role=role,road_sha256=road_sha,
                      source_sha256=sha_text(source),review_status='schema_only',
                      provenance_kind='synthetic_fixture',reviewer_id='cpu-schema-only')
        files['original-source-review/'+role+'.json'] = json.dumps(record,separators=(',',':'))+'\n'
    files['acquisition-provenance.json'] = json.dumps({'provenance_kind':'synthetic_fixture'})+'\n'
    old_trace = [json.loads(line) for line in files['trace.jsonl'].splitlines()]
    old_evidence = [json.loads(line) for line in files['capture/evidence.jsonl'].splitlines()]
    frame_map = [json.loads(line) for line in files['video_frames.jsonl'].splitlines()]
    speed = speed_request(design['speed_mode'])
    barrier = blocker_for(design['sight_mode'])
    bodies,rays,exceptions,trace,evidence = [],[],[],[],[]
    for i in range(600):
        frame = 1000+i
        x = round(-50+speed*i/20, 2 if design['speed_mode'] == 'at_limit_traversal' else 4)
        rail_traffic = [
            {'source_ref':'synthetic:left-rail-vehicle','kind':'rail_vehicle',
             'side':'left','center_xy_m':[0,-70+.01*i]},
            {'source_ref':'synthetic:right-rail-vehicle','kind':'rail_vehicle',
             'side':'right','center_xy_m':[0,70-.01*i]}]
        state = design['exception_state']
        flagman = {'source_ref':'synthetic:flagman','on_duty':state=='flagman_on_duty'}
        signal = {'source_ref':'synthetic:signal',
                  'installed':state in ('visible_inactive_signal','visible_active_signal','installed_not_visible'),
                  'visible':state in ('visible_inactive_signal','visible_active_signal'),
                  'indicates_approach':state=='visible_active_signal'}
        row = sight_row(i, {'source_ref':'synthetic:ego','observer_xy_m':[x,0],
                            'distance_to_crossing_m':-x,'speed_mps':speed,
                            'traversing_grade_crossing':-2<=x<=2},
                        {'source_ref':'synthetic:railway','crossing_xy_m':[0,0],
                         'unit_direction_xy':[0,1],'grade_crossing':True},
                        rail_traffic,barrier,flagman,signal)
        if design['speed_mode'] == 'at_limit_traversal':
            def quantize(value):
                if isinstance(value, float):
                    return round(value, 5)
                if isinstance(value, list):
                    return [quantize(item) for item in value]
                if isinstance(value, dict):
                    return {key: quantize(item) for key, item in value.items()}
                return value
            row = quantize(row)
        body = {'frame':frame,'actor_id':1,'actor_type_id':'vehicle.synthetic.cpu',
                'body_vertices_m':[[x+dx,dy,z] for dx in (-2,2)
                                   for dy in (-1,1) for z in (0,1)],
                'velocity_mps':[speed,0,0]}
        direction = lambda side, aid: {
            'actor_id':aid,'actor_position_m':[0,row['rail_vehicle_positions_m'][side][1],0],
            'rail_rays':[{'clear':True}],'body_rays':[{'clear':True}],
            'clear_distance_m':row['rail_'+side+'_clear_distance_m'],
            'rail_vehicle_visible_proxy':row[side+'_traffic_visible']}
        ray = {'frame':frame,'ego_actor_id':1,
               'review_source_sha256':sha_text(files['original-source-review/railway.source.txt']),
               'observer_m':[x,0,1.4],
               'crossing':{'clear':row['crossing_visible'],'method':'synthetic_collision_proxy'},
               'directions':{'left':direction('left',2),'right':direction('right',3)}}
        exception = {'frame':frame,'video_frame':i,
                     'flagman':{'frame':frame,'source_ref':'synthetic:flagman',
                                'on_duty':flagman['on_duty']},
                     'signal':{'frame':frame,'source_ref':'synthetic:signal',**signal}}
        bodies.append(body);rays.append(ray);exceptions.append(exception)
        mapping = frame_map[i]
        mapping['native_frame']=frame;mapping['carla_frame']=frame
        mapping['camera_native_frames']={name:frame for name in CAMERAS}
        event = old_evidence[i]
        event['ego']['position_m']=[x,0,0.5]
        event['ego']['body_vertices_m']=body['body_vertices_m']
        event['ego']['speed_mps']=speed
        participants = event['original_observations']['participants'][:1]
        participants[0]['body_vertices_m']=body['body_vertices_m']
        participants[0]['velocity_mps']=[speed,0,0]
        participants[0]['speed_mps']=speed
        event['original_observations']['participants']=participants
        event['original_observations']['frame']=frame
        event['original_observations']['rgb_sensors']={name:{'frame':i} for name in CAMERAS}
        evidence.append(event)
        graph = spec['graphs'][i]
        graph['attributes']['observed_evidence']=event['original_observations']
        motion = old_trace[i]
        motion['position']['x']=x
        motion['position']['y']=0
        motion['position']['z']=0.5
        motion['position_m'][0]=x
        motion['position_m'][1:]=[0,0.5]
        motion['speed_mps']=speed
        motion['speed_mph']=speed/.44704
        motion['velocity_mps']=[speed,0,0]
        motion['frame']=frame
        trace.append(motion)
    files['rail-body.jsonl']=rows_text(bodies)
    files['rail-rays.jsonl']=rows_text(rays)
    files['reviewed-exceptions.jsonl']=rows_text(exceptions)
    files['video_frames.jsonl']=rows_text(frame_map)
    files['trace.jsonl']=rows_text(trace)
    files['capture/evidence.jsonl']=rows_text(evidence)
    review={'review_status':'schema_only','provenance_kind':'synthetic_fixture',
            'reviewer_id':'cpu-schema-only',
            'frame_map_sha256':sha_text(files['video_frames.jsonl']),
            'overview_video_sha256':overview_sha,
            'exception_rows_sha256':sha_text(files['reviewed-exceptions.jsonl'])}
    files['reviewed-exceptions-review.json']=json.dumps(review,separators=(',',':'))+'\n'
    manifest=json.loads(files['capture/manifest.json'])
    manifest['sources']={'road.xodr':road_sha,'trace.jsonl':sha_text(files['trace.jsonl'])}
    files['capture/manifest.json']=json.dumps(manifest,separators=(',',':'))+'\n'
    for index,video in enumerate(spec['videos']):
        video['path']=CAMERAS[index]+'.mkv'
        video['width']=1920 if index==0 else 1280
        video['height']=1080 if index==0 else 720
    return spec


def build():
    template=json.loads(TEMPLATE.read_text())
    overview_sha=video_hash()
    plan=json.loads((WORK/'case-plan.json').read_text())
    for case in plan['cases']:
        suffix=case['case_id'].split('__')[-1]
        spec=build_case(template,case,overview_sha)
        path=WORK/('diagnostic-'+suffix+'.json')
        path.write_text(json.dumps(spec,separators=(',',':'))+'\n')
        if path.stat().st_size>2*1024*1024:
            raise ValueError('Diagnostic spec exceeds 2 MiB: '+suffix+' '+str(path.stat().st_size))
        relative='work/'+WORK.name+'/'+path.name
        digest=sha_file(path)
        recipe={'format':'worker-fixture-recipe',
                'sources':[{'path':'diagnostic-input.json','source':relative,'sha256':digest}],
                'generator':{'source':relative,'sha256':digest}}
        (WORK/('diagnostic-'+suffix+'-recipe.json')).write_text(json.dumps(recipe,indent=2)+'\n')
        print(suffix,path.stat().st_size,digest)


if __name__=='__main__':
    build()
