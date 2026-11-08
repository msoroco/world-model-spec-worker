"""Build six exact, unselected rider cases with four distinct Native policies."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')
RIDERS = ('bicycle', 'electric_bicycle', 'electric_scooter')
RESPONSES = ('clear', 'conflict')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def substitute(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Rider Native patch anchor changed: ' + old[:70])
    return source.replace(old, new)


def rider_runner(source, rider, response, candidate):
    source = substitute(source,
        "from alley_engineering import parameters",
        "from rider_candidates import parameters")
    source = substitute(source,
        "return [{**spec,'name':'reference_corner'} if spec['name']=='facility' else spec\n            for spec in camera_plan(candidate)]",
        "return [{**spec,'name':'reference_corner',\n"
        "             'xyz_m':parameters('bicycle','clear',candidate)['reference_camera_xyz_m']}\n"
        "            if spec['name']=='facility' else spec for spec in camera_plan(candidate)]")
    source = substitute(source,
        "from geometry import (ALLEY_ENTRANCE_BOUNDS_M,BICYCLE_BOUNDS_M,",
        "from rider_engineering import rider_pose, RELEASE_FRAME\n"
        "from geometry import (ALLEY_ENTRANCE_BOUNDS_M,BICYCLE_BOUNDS_M,")
    source = substitute(source,
        "if suffix not in ('probe_c_alley_entry','probe_d_no_entry') or candidate not in ('primary','fallback1','fallback2','fallback3'):",
        "if suffix not in ('rider_bicycle_clear','rider_bicycle_conflict','rider_electric_bicycle_clear','rider_electric_bicycle_conflict','rider_electric_scooter_clear','rider_electric_scooter_conflict') or candidate not in ('primary','fallback1','fallback2','fallback3'):")
    source = substitute(source,
        "engineering=parameters(candidate)\n    (route if suffix=='probe_c_alley_entry' else route_no_entry)(engineering['approach_start_x_m'])",
        "rider_type,response=suffix.removeprefix('rider_').rsplit('_',1)\n"
        "    engineering=parameters(rider_type,response,candidate)\n"
        "    route(engineering['approach_start_x_m'])")
    source = substitute(source,
        "engineering=parameters(candidate)\n        start=engineering['approach_start_x_m']",
        "rider_type,response=suffix.removeprefix('rider_').rsplit('_',1)\n"
        "        engineering=parameters(rider_type,response,candidate)\n"
        "        start=engineering['approach_start_x_m']")
    source = source.replace("engineering['turn_speed_mps']", "engineering['ego_speed_mps']")
    source = substitute(source,
        "owned.append(pedestrian)\n        wheels=ego.get_physics_control().wheels",
        "owned.append(pedestrian)\n"
        "        # Actor class is checked from the original Native blueprint ID.\n"
        "        # Electric classes require an explicit matching Native asset.\n"
        "        asset_ids={'bicycle':'vehicle.bh.crossbike',\n"
        "                   'electric_bicycle':'vehicle.c10052.electric_bicycle',\n"
        "                   'electric_scooter':'vehicle.c10052.electric_scooter'}\n"
        "        rider_bp=world.get_blueprint_library().find(asset_ids[rider_type])\n"
        "        if rider_bp is None or rider_bp.id!=asset_ids[rider_type]:\n"
        "            raise RuntimeError('Exact Native rider asset unavailable: '+rider_type)\n"
        "        rider_bp.set_attribute('role_name','c10052_'+rider_type)\n"
        "        rider_actor=world.spawn_actor(rider_bp,carla.Transform(\n"
        "            carla.Location(x=-20,y=-4,z=.5),carla.Rotation(yaw=0)))\n"
        "        owned.append(rider_actor)\n"
        "        if rider_actor.type_id!=asset_ids[rider_type]:\n"
        "            raise RuntimeError('Native rider actor class differs from requested class')\n"
        "        wheels=ego.get_physics_control().wheels")
    source = substitute(source,
        "(route if suffix=='probe_c_alley_entry' else route_no_entry)(start)", "route(start)")
    source = substitute(source,
        "'pedestrian_control_blueprint':pedestrian.type_id,",
        "'pedestrian_control_blueprint':pedestrian.type_id,\n"
        "            'rider_blueprint':rider_actor.type_id,'rider_actor_id':rider_actor.id,")
    source = substitute(source,
        "        if suffix=='probe_d_no_entry':\n            reference=next",
        "        if False:  # No instance view required for this rider construction.\n            reference=next")
    source = substitute(source,
        "        with (output/'native_samples.jsonl').open('x') as native_file, \\",
        "        with (output/'rider_native_samples.jsonl').open('x') as rider_file, \\\n+             (output/'native_samples.jsonl').open('x') as native_file, \\")
    source = substitute(source,
        "                ego.apply_control(carla.VehicleControl(throttle=command['throttle'],",
        "                if before.location.x>=-9 and index < RELEASE_FRAME[response]+engineering['release_shift_frames']:\n"
        "                    command={**command,'throttle':0.0,'brake':1.0,'hand_brake':True}\n"
        "                requested_rider=rider_pose(index)\n"
        "                rider_actor.set_transform(carla.Transform(carla.Location(\n"
        "                    x=requested_rider['center_xy'][0],y=-4,z=.5),carla.Rotation(yaw=0)))\n"
        "                ego.apply_control(carla.VehicleControl(throttle=command['throttle'],")
    source = substitute(source,
        "                native_file.write(json.dumps(sample,allow_nan=False)+'\\n')",
        "                native_file.write(json.dumps(sample,allow_nan=False)+'\\n')\n"
        "                rider_pose_native=rider_actor.get_transform()\n"
        "                rider_velocity=rider_actor.get_velocity()\n"
        "                rider_speed=math.sqrt(rider_velocity.x**2+rider_velocity.y**2+rider_velocity.z**2)\n"
        "                rider_row={'native_frame':frame,'time_s':time_s,'rider_type':rider_type,\n"
        "                    'rider_actor_id':rider_actor.id,'rider_blueprint':rider_actor.type_id,\n"
        "                    'rider_body_xy':body_xy(rider_actor),'rider_speed_mps':rider_speed,\n"
        "                    'ego_body_xy':body,'ego_speed_mps':speed,\n"
        "                    'ego_native_road_id':lane.road_id,'rider_native_road_id':ROAD_ID,\n"
        "                    'rider_native_lane_id':BICYCLE_LANE_ID,\n"
        "                    'rider_center_xy_m':[rider_pose_native.location.x,rider_pose_native.location.y]}\n"
        "                rider_file.write(json.dumps(rider_row,allow_nan=False)+'\\n')")
    source = substitute(source,
        "'ru.pedestrian':{'native_actor_id':pedestrian.id,",
        "('ru.'+rider_type):{'native_actor_id':rider_actor.id,\n"
        "                        'native_blueprint':rider_actor.type_id,\n"
        "                        'native_body_xy_m':rider_row['rider_body_xy'],\n"
        "                        'native_road_id':ROAD_ID,'native_lane_id':BICYCLE_LANE_ID},\n"
        "                    'ru.pedestrian':{'native_actor_id':pedestrian.id,")
    source = substitute(source,
        "                if suffix=='probe_d_no_entry':\n                    image=camera_queues",
        "                if False:  # No instance view required.\n                    image=camera_queues")
    source = substitute(source,
        "        write_new(output/'entry-sources.json'",
        "        write_new(output/'rider_geometry.json',{'format':'c10052-original-rider-geometry-v1',\n"
        "            'conflict_native_xy_bounds_m':engineering['conflict_bounds_m'],\n"
        "            'bicycle_facility_native_xy_bounds_m':list(BICYCLE_BOUNDS_M),\n"
        "            'ego_road_ids':[1,2],'rider_road_id':ROAD_ID,\n"
        "            'rider_lane_id':BICYCLE_LANE_ID,\n"
        "            'native_map_sha256':native_hash})\n"
        "        write_new(output/'rider-source-manifest.json',{'format':'c10052-original-rider-sources-v1',\n"
        "            'source_kind':'original_native','accepted':False,'rider_type':rider_type,\n"
        "            'rider_actor_id':rider_actor.id,'rider_blueprint':rider_actor.type_id,\n"
        "            'samples_sha256':hashlib.sha256((output/'rider_native_samples.jsonl').read_bytes()).hexdigest(),\n"
        "            'geometry_sha256':hashlib.sha256((output/'rider_geometry.json').read_bytes()).hexdigest(),\n"
        "            'road_geometry_sha256':hashlib.sha256((output/'road_geometry.json').read_bytes()).hexdigest()})\n"
        "        write_new(output/'entry-sources.json'")
    source = substitute(source,
        "    config=json.loads((ROOT/'alley-native-config.json').read_text())",
        "    config=json.loads((ROOT/'config.json').read_text())")
    return source


def main():
    original=json.loads((HERE/'draft-execution-manifest.json').read_text())
    base=next(c for c in original['cases'] if c['case_id'].endswith('__probe_a'))
    plan=json.loads((HERE/'case-plan.json').read_text())
    planned={c['case_id'] for c in plan['cases']}
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
        'assignment_id':AID,'runtime_manifest_sha256':original['runtime_manifest_sha256'],
        'status':'draft_not_selected','cases':[]}
    for rider in RIDERS:
        for response in RESPONSES:
            suffix=f'rider_{rider}_{response}';case_id=AID+'__'+suffix
            if case_id not in planned:raise ValueError('Rider case absent from plan: '+case_id)
            entry={'case_id':case_id,'kind':'draft_not_selected',
                'candidate_risk':{'status':'physical','reason':'Original Native rider asset class, physical turn, view and facility designation need saved readback'},
                'measurement_contract':'rider-yield-measurement-contract.json',
                'measurement_procedure':{'entrypoint':'finalize_rider.py','output_schema':'c10052-saved-rider-conflict-diagnostic-v1'},
                'candidates':[]}
            for name in NAMES:
                ref=base if name=='primary' else next(x for x in base['candidates'] if x['id']==name)
                source=json.loads((HERE/ref['construction']).read_text())
                candidate=dict(source)
                candidate['case_id']=case_id
                candidate['status']='unselected_cpu_draft'
                candidate['measurement_plan']={'method':'saved source-hashed original Native ego/rider body conflict timing',
                    'status':'exact_bundle_unselected_original_native_pending'}
                candidate['static_checks']=['exact case and rider asset class','480 synchronized Native frames',
                    'four original camera views','original rider and ego body samples']
                candidate['recording_description']=json.loads(json.dumps(source['recording_description']))
                candidate['recording_description']['channels'].append({
                    'name':'ru.'+rider,'unit':'structured','sampling_rate_hz':20,
                    'method':'Original Native rider blueprint, actor ID, lane and full body readback',
                    'time_window':'entire original 24 s / 480-frame attempt',
                    'reference_frame':'surveyed Native bicycle facility and original frame',
                    'uncertainty':'50 ms sampling; actor asset classification and physical motion require saved review'})
                files=[]
                for file in source['files']:
                    path=file['path'];content=file['content']
                    if path=='runner.py':content=rider_runner((HERE/'native/alley_runner.py').read_text(),rider,response,name)
                    elif path=='config.json':
                        config=json.loads(content)
                        config.update(case_id=case_id,case_suffix=suffix,candidate_id=name,
                            selected_case_id=case_id,supported_case_ids=[case_id],case={'case_id':case_id},
                            rider_type=rider,rider_response=response)
                        config['required_atoms']=sorted(set(config['required_atoms'])|{'ru.'+rider})
                        config['mandatory_channels']=sorted(set(config['mandatory_channels'])|{'ru.'+rider})
                        config['recording_description']=candidate['recording_description']
                        for camera in config['cameras']:
                            if camera['name']=='facility':
                                camera['name']='reference_corner'
                        content=json.dumps(config,indent=2)+'\n'
                    elif path=='tests/test_bundle.py':
                        content="import json\nimport unittest\nfrom pathlib import Path\nimport runner\n\nclass ExactRiderCase(unittest.TestCase):\n    def test_check(self):\n        config=json.loads(Path('config.json').read_text())\n        result=runner.check(config)\n        self.assertEqual(result['camera_count'],4)\n        self.assertFalse(result['native_imported'])\n"
                    files.append({'path':path,'content':content})
                for module in ('alley_geometry','rider_engineering','rider_candidates','measure_rider_yield','measure_rider_native','finalize_rider'):
                    files.append({'path':module+'.py','content':(HERE/'native'/(module+'.py')).read_text()})
                candidate['files']=files
                path=HERE/'draft-rider-cases'/suffix/name/'construction.json'
                write(path,candidate)
                row={'id':name,'construction':path.relative_to(HERE).as_posix(),
                    'construction_sha256':sha(path)}
                if name=='primary':entry.update(row)
                else:
                    metric={1:('approach_runway_m','under 35 m'),2:('ego_entry_error_frames','over 5 frames'),
                            3:('body_visible_fraction','under 0.95')}[int(name[-1])]
                    row.update(trigger={'source':'source-hashed original Native body and camera frames',
                        'metric':metric[0],'failure_condition':metric[1]},
                        changed_knobs={1:['approach start -45 to -55 m'],2:['release delayed five frames'],
                            3:['reference camera relocated']}[int(name[-1])])
                    entry['candidates'].append(row)
            manifest['cases'].append(entry)
    path=HERE/'draft-rider-execution-manifest.json';write(path,manifest)
    return {'cases':len(manifest['cases']),'candidates':len(manifest['cases'])*4,
            'manifest_sha256':sha(path),'selected':False}


if __name__=='__main__':print(json.dumps(main(),indent=2))
