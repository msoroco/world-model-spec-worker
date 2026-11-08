"""Materialize two exact, unselected pedestrian Native candidate cases."""
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Pedestrian Native patch anchor changed: '+old[:80])
    return source.replace(old, new)


def runner(source):
    source = once(source,
        'from alley_geometry import check as geometry_check,open_drive,route,route_no_entry',
        'from alley_geometry import check as geometry_check,route,route_no_entry\n'
        'from pedestrian_native_geometry import check as pedestrian_geometry_check,open_drive')
    source = once(source,
        'from rider_engineering import rider_pose, RELEASE_FRAME',
        'from pedestrian_engineering import pedestrian_pose\n'
        'from rider_engineering import RELEASE_FRAME')
    source = once(source,
        "if suffix not in ('rider_bicycle_clear','rider_bicycle_conflict','rider_electric_bicycle_clear','rider_electric_bicycle_conflict','rider_electric_scooter_clear','rider_electric_scooter_conflict') or candidate not in ('primary','fallback1','fallback2','fallback3'):",
        "if suffix not in ('pedestrian_clear','pedestrian_conflict') or candidate not in ('primary','fallback1','fallback2','fallback3'):")
    source = source.replace("rider_type,response=suffix.removeprefix('rider_').rsplit('_',1)",
                            "rider_type='pedestrian';response=suffix.removeprefix('pedestrian_')")
    source = source.replace('parameters(rider_type,response,candidate)',
                            "parameters('bicycle',response,candidate)")
    source = once(source,
        "'alley_entrance':(0,-10,2,-1,carla.LaneType.Driving)}",
        "'alley_entrance':(0,-10,2,-1,carla.LaneType.Driving),\n"
        "              'sidewalk':(-12,-6.25,ROAD_ID,-3,carla.LaneType.Sidewalk)}")
    source = once(source, 'geometry=geometry_check();suffix=config[\'case_suffix\'];candidate=config[\'candidate_id\']',
                  "geometry=geometry_check();pedestrian_geometry_check();suffix=config['case_suffix'];candidate=config['candidate_id']")
    source = once(source,
        "carla.Location(x=8,y=-4,z=.5),carla.Rotation(yaw=0)))",
        "carla.Location(x=-20,y=-7,z=.5),carla.Rotation(yaw=0)))")
    start = source.index('        # Actor class is checked from the original Native blueprint ID.')
    end = source.index('        wheels=ego.get_physics_control().wheels', start)
    source = source[:start] + (
        "        if not pedestrian.type_id.startswith('walker.pedestrian.'):\n"
        "            raise RuntimeError('Original Native pedestrian actor class differs')\n"
        "        rider_actor=pedestrian\n"
        "        obstacle_bp=world.get_blueprint_library().find('static.prop.streetbarrier')\n"
        "        if obstacle_bp is None or obstacle_bp.id!='static.prop.streetbarrier':\n"
        "            raise RuntimeError('Exact Native obstruction asset unavailable')\n"
        "        sidewalk_obstacles=[];buffer_obstacles=[]\n"
        "        for x in (-4.0,-1.0,2.0,5.0):\n"
        "            for y,group in ((-7.0,sidewalk_obstacles),(-5.5,buffer_obstacles)):\n"
        "                obstacle=world.spawn_actor(obstacle_bp,carla.Transform(\n"
        "                    carla.Location(x=x,y=y,z=.5),carla.Rotation(yaw=0)))\n"
        "                if obstacle.type_id!=obstacle_bp.id:\n"
        "                    raise RuntimeError('Native obstruction actor class differs')\n"
        "                owned.append(obstacle);group.append(obstacle)\n"
    ) + source[end:]
    source = once(source, "requested_rider=rider_pose(index)",
                  "requested_rider=pedestrian_pose(index)")
    source = once(source,
        "x=requested_rider['center_xy'][0],y=-4,z=.5),carla.Rotation(yaw=0)))",
        "x=requested_rider['center_xy'][0],y=requested_rider['center_xy'][1],z=.5),carla.Rotation(yaw=0)))")
    source = once(source,
        "'rider_blueprint':rider_actor.type_id,'rider_actor_id':rider_actor.id,",
        "'pedestrian_blueprint':pedestrian.type_id,'pedestrian_actor_id':pedestrian.id,\n"
        "            'sidewalk_obstruction_actor_ids':[a.id for a in sidewalk_obstacles],\n"
        "            'buffer_obstruction_actor_ids':[a.id for a in buffer_obstacles],")
    source = once(source,
        "                    'rider_center_xy_m':[rider_pose_native.location.x,rider_pose_native.location.y]}",
        "                    'rider_center_xy_m':[rider_pose_native.location.x,rider_pose_native.location.y],\n"
        "                    'sidewalk_obstacle_actor_bodies_xy':[body_xy(a) for a in sidewalk_obstacles],\n"
        "                    'buffer_obstacle_actor_bodies_xy':[body_xy(a) for a in buffer_obstacles]}")
    source = once(source,
        "                rider_pose_native=rider_actor.get_transform()",
        "                rider_pose_native=rider_actor.get_transform()\n"
        "                pedestrian_lane_type=(carla.LaneType.Sidewalk if rider_pose_native.location.y < -5\n"
        "                                      else carla.LaneType.Biking)\n"
        "                pedestrian_lane=mapping.get_waypoint(rider_pose_native.location,\n"
        "                    project_to_road=False,lane_type=pedestrian_lane_type)\n"
        "                if pedestrian_lane is None or pedestrian_lane.road_id!=ROAD_ID:\n"
        "                    raise RuntimeError('Original Native pedestrian lane identity missing')")
    source = once(source,
        "                    'ego_native_road_id':lane.road_id,'rider_native_road_id':ROAD_ID,\n"
        "                    'rider_native_lane_id':BICYCLE_LANE_ID,",
        "                    'ego_native_road_id':lane.road_id,\n"
        "                    'rider_native_road_id':pedestrian_lane.road_id,\n"
        "                    'rider_native_lane_id':pedestrian_lane.lane_id,")
    source = once(source,
        "                    ('ru.'+rider_type):{'native_actor_id':rider_actor.id,\n"
        "                        'native_blueprint':rider_actor.type_id,\n"
        "                        'native_body_xy_m':rider_row['rider_body_xy'],\n"
        "                        'native_road_id':ROAD_ID,'native_lane_id':BICYCLE_LANE_ID},\n"
        "                    'ru.pedestrian':{'native_actor_id':pedestrian.id,\n"
        "                        'native_xy_m':[pedestrian.get_location().x,pedestrian.get_location().y]},",
        "                    'ru.pedestrian':{'native_actor_id':pedestrian.id,\n"
        "                        'native_blueprint':pedestrian.type_id,\n"
        "                        'native_body_xy_m':rider_row['rider_body_xy'],\n"
        "                        'native_xy_m':[pedestrian.get_location().x,pedestrian.get_location().y]},")
    source = source.replace('rider_native_samples.jsonl','pedestrian_native_samples.jsonl')
    source = source.replace('rider_geometry.json','pedestrian_geometry.json')
    source = source.replace('rider-source-manifest.json','pedestrian-source-manifest.json')
    source = once(source,
        "            'rider_lane_id':BICYCLE_LANE_ID,",
        "            'rider_lane_id':BICYCLE_LANE_ID,'sidewalk_lane_id':-3,\n"
        "            'sidewalk_passage_bounds_m':[-6,-7.5,6,-6.5],\n"
        "            'buffer_passage_bounds_m':[-6,-6,6,-5],")
    source = source.replace("'rider_type':rider_type,", "'pedestrian_type':rider_type,")
    for old,new in (('rider_body_xy','pedestrian_body_xy'),
                    ('rider_actor_id','pedestrian_actor_id'),
                    ('rider_blueprint','pedestrian_blueprint'),
                    ('rider_speed_mps','pedestrian_speed_mps'),
                    ('rider_center_xy_m','pedestrian_center_xy_m'),
                    ('rider_native_road_id','pedestrian_native_road_id'),
                    ('rider_native_lane_id','pedestrian_native_lane_id'),
                    ('rider_road_id','pedestrian_road_id'),
                    ('rider_lane_id','pedestrian_lane_id')):
        source=source.replace(old,new)
    ast.parse(source)
    return source


def main():
    rider_manifest=json.loads((HERE/'draft-rider-execution-manifest.json').read_text())
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
              'assignment_id':AID,'runtime_manifest_sha256':rider_manifest['runtime_manifest_sha256'],
              'status':'draft_not_selected','cases':[]}
    for response in ('clear','conflict'):
        suffix='pedestrian_'+response;case_id=AID+'__'+suffix
        entry={'case_id':case_id,'kind':'draft_not_selected',
               'candidate_risk':{'status':'physical','reason':'Native sidewalk, obstruction actors, pedestrian path, four cameras and yield response require readback'},
               'measurement_contract':'pedestrian-qualification-measurement-contract.json',
               'measurement_procedure':{'entrypoint':'finalize_pedestrian.py',
                                        'output_schema':'c10052-saved-pedestrian-diagnostic-v1'},
               'candidates':[]}
        for name in NAMES:
            source_path=HERE/'draft-rider-cases'/('rider_bicycle_'+response)/name/'construction.json'
            candidate=json.loads(source_path.read_text())
            candidate['case_id']=case_id
            candidate['status']='unselected_cpu_draft'
            candidate['measurement_plan']={'method':'saved original Native pedestrian/ego body, obstruction and return evidence',
                                           'status':'exact_bundle_unselected_original_native_pending'}
            description=candidate['recording_description']
            description['channels']=[channel for channel in description['channels']
                                     if channel['name']!='ru.bicycle']
            pedestrian_channel=next(channel for channel in description['channels']
                                    if channel['name']=='ru.pedestrian')
            pedestrian_channel['method']='Original Native pedestrian actor ID, body and sidewalk-to-lane path'
            files=[]
            for file in candidate['files']:
                path=file['path'];content=file['content']
                if path=='finalize_rider.py':
                    continue
                if path=='runner.py':content=runner(content)
                elif path=='config.json':
                    config=json.loads(content)
                    config.update(case_id=case_id,case_suffix=suffix,candidate_id=name,
                                  selected_case_id=case_id,supported_case_ids=[case_id],
                                  case={'case_id':case_id},rider_type='pedestrian',
                                  rider_response=response)
                    config['required_atoms']=sorted(set(config['required_atoms'])-{'ru.bicycle'}|{'ru.pedestrian'})
                    config['mandatory_channels']=sorted(set(config['mandatory_channels'])-{'ru.bicycle'}|{'ru.pedestrian'})
                    config['recording_description']=description
                    content=json.dumps(config,indent=2)+'\n'
                elif path=='tests/test_bundle.py':
                    content=("import json\nimport unittest\nfrom pathlib import Path\nimport runner\n\n"
                             "class ExactPedestrianCase(unittest.TestCase):\n"
                             "    def test_check(self):\n"
                             "        result=runner.check(json.loads(Path('config.json').read_text()))\n"
                             "        self.assertEqual(result['camera_count'],4)\n"
                             "        self.assertFalse(result['native_imported'])\n")
                files.append({'path':path,'content':content})
            for module in ('pedestrian_engineering','pedestrian_native_geometry'):
                files.append({'path':module+'.py','content':(HERE/'native'/(module+'.py')).read_text()})
            files.append({'path':'finalize_pedestrian.py',
                          'content':(HERE/'native/finalize_pedestrian.py').read_text()})
            candidate['files']=files
            output=HERE/'draft-pedestrian-exact-cases'/suffix/name/'construction.json'
            write(output,candidate)
            row={'id':name,'construction':output.relative_to(HERE).as_posix(),
                 'construction_sha256':sha(output)}
            if name=='primary':entry.update(row)
            else:
                metric={1:'approach_runway_m',2:'ego_entry_error_frames',3:'synthetic_visible_fraction'}[int(name[-1])]
                row.update(trigger={'source':'source-hashed pedestrian CPU fixture; original Native trigger pending',
                                    'metric':metric},
                           changed_knobs={1:['approach start -45 to -55 m'],
                                          2:['release delayed five frames'],
                                          3:['reference camera relocated']}[int(name[-1])])
                entry['candidates'].append(row)
        manifest['cases'].append(entry)
    path=HERE/'draft-pedestrian-execution-manifest.json';write(path,manifest)
    print(json.dumps({'cases':2,'candidates':8,'manifest_sha256':sha(path),
                      'selected':False},indent=2))


if __name__=='__main__':main()
