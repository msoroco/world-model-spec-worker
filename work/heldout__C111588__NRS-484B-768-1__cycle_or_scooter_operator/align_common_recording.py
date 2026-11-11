"""Add six original-source channels and three context records to nine exact bundles."""
from hashlib import sha256
import json
from math import hypot
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PREFIX = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__'
STAGE = {x['case_id']:x for x in json.loads((ROOT/'proposals/cases-stage-proposal.json').read_text())['cases'] if x['target_type']!='baseline'}
VIDEO_SHA = '4d5541f025afa64755261e4f4811e6b61617fd1cd22d0a62dc785fcf61a6d230'
MANIFESTS = {'bicycle_signal_once':'first-execution-manifest.json',
 'bicycle_no_signal':'no-signal-manifest.json','bicycle_signal_continuous':'continuous-manifest.json',
 'electric_bicycle_signal_once':'electric-bicycle-manifest.json','electric_scooter_signal_once':'electric-scooter-manifest.json',
 'turn_lane_no_signal':'turn-lane-manifest.json','both_hands_no_signal':'both-hands-manifest.json',
 'safety_wide':'safety-wide-manifest.json','safety_narrow':'safety-narrow-manifest.json'}

def save(path,value,compact=False):
 path.write_text(json.dumps(value,separators=(',',':') if compact else None,
                            indent=None if compact else 2,allow_nan=False)+'\n')
def sha(path):return sha256(path.read_bytes()).hexdigest()

def runner(source,slug):
 if 'from rider_participant import Recorder, spawn' not in source:
  source=source.replace('from rider_route import control, select_left_turn',
   'from rider_route import control, select_left_turn\nfrom rider_participant import Recorder, spawn')
 if 'from rider_hand_control import capture_hands, capture_stability' not in source:
  source=source.replace('from rider_route import control, select_left_turn',
   'from rider_route import control, select_left_turn\nfrom rider_hand_control import capture_hands, capture_stability')
 marker='        route = select_left_turn(world.get_map())\n'
 assert marker in source
 source=source.replace(marker,marker+'''        (output / 'route_waypoints.json').write_text(json.dumps({'waypoints': [
            {'road_id': point.road_id, 'lane_id': point.lane_id,
             'position_m': [point.transform.location.x, point.transform.location.y, point.transform.location.z]}
            for point in route]}, indent=2) + '\\n')
''')
 if 'participant_recorder' not in source:
  source=source.replace('sinks = {}','sinks = {}\n    participant_recorder = None')
  marker='        actors.append(bicycle)\n'
  assert marker in source
  source=source.replace(marker,marker+'''        participant = spawn(world, carla, library, route, 8.0)
        actors.append(participant)
''',1)
  marker="        bone_rows = (output / 'rider_arm_bones.jsonl').open('x')\n"
  assert marker in source
  source=source.replace(marker,marker+"        participant_recorder = Recorder(output)\n")
  marker='            frame_map.append(frame, time_s)'
  assert marker in source
  source=source.replace(marker,'            participant_recorder.capture(frame, time_s, trace, participant, bicycle)\n'+marker)
  marker='if bone_rows is not None:\n            bone_rows.close()'
  assert marker in source
  source=source.replace(marker,marker+'\n        if participant_recorder is not None:\n            participant_recorder.close()')
 if 'hand_rows = stability_rows = None' not in source:
  source=source.replace('sinks = {}','sinks = {}\n    hand_rows = stability_rows = None')
  marker="        bone_rows = (output / 'rider_arm_bones.jsonl').open('x')\n"
  assert marker in source
  source=source.replace(marker,marker+"        hand_rows = (output / 'hand_contact_readback.jsonl').open('x')\n        stability_rows = (output / 'control_stability.jsonl').open('x')\n")
  control='            bicycle.apply_control(carla.VehicleControl(**_control(bicycle, target)))'
  assert control in source
  source=source.replace(control,'            command = _control(bicycle, target)\n            bicycle.apply_control(carla.VehicleControl(**command))')
  marker='            frame_map.append(frame, time_s)'
  source=source.replace(marker,"            hand_rows.write(json.dumps(capture_hands(rider, frame, time_s)) + '\\n')\n            stability_rows.write(json.dumps(capture_stability(trace, frame, time_s, command)) + '\\n')\n"+marker)
  marker='if bone_rows is not None:\n            bone_rows.close()'
  source=source.replace(marker,marker+'\n        if hand_rows is not None:\n            hand_rows.close()\n        if stability_rows is not None:\n            stability_rows.close()')
 if 'frame_times' not in source:
  source=source.replace('        frames = []','        frames = []\n        frame_times = []')
  source=source.replace('            frames.append(frame)','            frames.append(frame)\n            frame_times.append(time_s)')
 if "(output / 'hand_contact_review.jsonl').write_text" not in source:
  marker="        (output / 'construction-probe.json').write_text"
  assert marker in source
  source=source.replace(marker,"""        for sink in sinks.values():
            sink.close()
        sinks.clear()
        from hashlib import sha256
        video_sha = sha256((output / 'driver_reference.mkv').read_bytes()).hexdigest()
        (output / 'hand_contact_review.jsonl').write_text(''.join(
            json.dumps({'frame': frame, 'time_s': time_s, 'source_video_sha256': video_sha,
                        'left_hand_contact': None, 'right_hand_contact': None}) + '\\n'
            for frame, time_s in zip(frames, frame_times)))
"""+marker)
 return source

def finalizer(source):
 marker="if __name__ == '__main__':\n    main()"
 assert marker in source
 extension='''from rider_common_finalizer import enrich as _common_enrich

_previous_build_result = build_result
def build_result(attempt, report):
    result = _previous_build_result(attempt, report)
    return _common_enrich(attempt, result)

'''
 return source.replace(marker,extension+marker)

def test_source(source,slug):
 if "'position_m': [float(i), 0.0, 0.0]" not in source:
  source=source.replace("'trace.jsonl': [{'frame': i, 'time_s': i * .05} for i in range(4)]",
    "'trace.jsonl': [{'frame': i, 'time_s': i * .05, 'position_m': [float(i), 0.0, 0.0]} for i in range(4)]")
 offset=3 if slug=='safety_narrow' else 8
 marker='    for name, items in rows.items():\n'
 assert marker in source
 extra=f'''    (root / 'route_waypoints.json').write_text(json.dumps({{'waypoints': [{{'road_id': 1, 'lane_id': 1, 'position_m': [float(i), 0, 0]}} for i in range(3)]}}) + '\\n')
    rows['participant_motion.jsonl'] = [{{'frame': i, 'time_s': i * .05, 'actor_id': 'other-1',
        'position_m': [float(i), {offset}.0 - i * .05, 0.0],
        'rider_half_width_m': .45, 'participant_half_width_m': .35}} for i in range(4)]
    rows['clearance_samples.jsonl'] = [{{'frame': i, 'time_s': i * .05,
        'participant_actor_id': 'other-1', 'center_distance_m': {offset}.0 - i * .05}} for i in range(4)]
    rows['hand_contact_readback.jsonl'] = [{{'frame': i, 'time_s': i * .05, 'rider_id': 'rider-1',
        'hand_bone_readback': {{'crl_hand__L': None, 'crl_hand__R': None}},
        'physical_handlebar_contact_verified': None}} for i in range(4)]
    rows['control_stability.jsonl'] = [{{'frame': i, 'time_s': i * .05,
        'wheel_steer_angle_deg': 0, 'speed_mps': 1, 'accel_longitudinal_mps2': 0,
        'commanded_steer': 0, 'control_stability_judgment': None}} for i in range(4)]
    rows['hand_contact_review.jsonl'] = [{{'frame': i, 'time_s': i * .05,
        'source_video_sha256': video_sha, 'left_hand_contact': None,
        'right_hand_contact': None}} for i in range(4)]
'''
 return source.replace(marker,extra+marker)

proposal_path=ROOT/'proposals/cases.json';proposal=json.loads(proposal_path.read_text())
for slug,manifest_name in MANIFESTS.items():
 case=PREFIX+slug;folder=ROOT/'cases'/slug
 paths=[ROOT/'first-construction.json' if slug=='bicycle_signal_once' else folder/'construction.json']
 paths += [folder/f'fallback{i}-construction.json' for i in (1,2,3)]
 for path in paths:
  obj=json.loads(path.read_text());obj['recording_description']=STAGE[case]['recording_description']
  files={row['path']:row for row in obj['files']}
  for name in ('config.json','probe-config.json'):
   config=json.loads(files[name]['content']);config['case']['recording_description']=obj['recording_description']
   files[name]['content']=json.dumps(config,indent=2)+'\n'
  for name in ('runner.py','native_rider_probe.py'):files[name]['content']=runner(files[name]['content'],slug)
  files['rider_signal_finalizer.py']['content']=finalizer(files['rider_signal_finalizer.py']['content'])
  files['tests/test_rider_signal_finalizer.py']['content']=test_source(files['tests/test_rider_signal_finalizer.py']['content'],slug)
  for name in ('rider_participant.py','rider_clearance_measurement.py','rider_hand_control.py','rider_common_finalizer.py'):
   if name not in files:obj['files'].append({'path':name,'content':(ROOT/name).read_text()})
   else:files[name]['content']=(ROOT/name).read_text()
  save(path,obj)
 diagnostic_path=ROOT/'diagnostic-input.json' if slug=='bicycle_signal_once' else folder/'diagnostic-input.json'
 diagnostic=json.loads(diagnostic_path.read_text())
 trace=[json.loads(line) for line in diagnostic['files']['trace.jsonl'].splitlines() if line]
 frames=[json.loads(line) for line in diagnostic['files']['video_frames.jsonl'].splitlines() if line]
 context=json.loads(diagnostic['files']['rider_context.json']);offset=3 if slug=='safety_narrow' else 8
 motion=[];samples=[]
 for row in trace:
  p=row['position_m'];other=[float(p[0]),float(p[1])+offset-float(row['time_s']),float(p[2])]
  distance=hypot(float(p[0])-other[0],float(p[1])-other[1])
  motion.append({'frame':row['frame'],'time_s':row['time_s'],'actor_id':'diagnostic-participant-1',
                 'position_m':other,'rider_half_width_m':.45,'participant_half_width_m':.35})
  samples.append({'frame':row['frame'],'time_s':row['time_s'],
                  'participant_actor_id':'diagnostic-participant-1','center_distance_m':distance})
 diagnostic['files']['participant_motion.jsonl']=''.join(json.dumps(x)+'\n' for x in motion)
 diagnostic['files']['clearance_samples.jsonl']=''.join(json.dumps(x)+'\n' for x in samples)
 diagnostic['files']['hand_contact_readback.jsonl']=''.join(json.dumps({'frame':f['carla_frame'],
   'time_s':f['time_s'],'rider_id':context['rider_id'],
   'hand_bone_readback':{'crl_hand__L':None,'crl_hand__R':None},
   'physical_handlebar_contact_verified':None})+'\n' for f in frames)
 diagnostic['files']['control_stability.jsonl']=''.join(json.dumps({'frame':f['carla_frame'],
   'time_s':f['time_s'],'wheel_steer_angle_deg':0,'speed_mps':1,
   'accel_longitudinal_mps2':0,'commanded_steer':0,'control_stability_judgment':None})+'\n' for f in frames)
 diagnostic['files']['hand_contact_review.jsonl']=''.join(json.dumps({'frame':f['carla_frame'],
   'time_s':f['time_s'],'source_video_sha256':VIDEO_SHA,
   'left_hand_contact':None,'right_hand_contact':None})+'\n' for f in frames)
 diagnostic['files']['route_waypoints.json']=json.dumps({'waypoints':[{'road_id':1,'lane_id':1,
   'position_m':[float(i),0.,0.]} for i in range(3)]},indent=2)+'\n'
 save(diagnostic_path,diagnostic,compact=True)
 recipe_path=ROOT/'diagnostic-recipe.json' if slug=='bicycle_signal_once' else folder/'diagnostic-recipe.json'
 recipe=json.loads(recipe_path.read_text());checksum=sha(diagnostic_path)
 recipe['sources'][0]['sha256']=checksum;recipe['generator']['sha256']=checksum
 save(recipe_path,recipe)
 manifest_path=ROOT/manifest_name;manifest=json.loads(manifest_path.read_text());entry=manifest['cases'][0]
 entry['construction_sha256']=sha(paths[0])
 for i,candidate in enumerate(entry['candidates'],1):
  candidate['construction_sha256']=sha(paths[i]);candidate.pop('offline',None);candidate.pop('compatibility',None)
 entry.pop('physical_preparation',None)
 save(manifest_path,manifest)
 next(row for row in proposal['cases'] if row['case_id']==case)['recording_description']=STAGE[case]['recording_description']
 print(slug,'common original-source bundle aligned')
save(proposal_path,proposal)
