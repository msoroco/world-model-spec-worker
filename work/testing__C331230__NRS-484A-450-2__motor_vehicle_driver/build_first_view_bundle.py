"""Build the exact no-crosswalk/no-line first-view CPU construction.

The site remains a synthetic selector. The sight stream is sampled from a
Native actor and line-of-sight query during a later physical capture.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SOURCE = HERE / 'cases/no_crosswalk_marked_stop_line'
TARGET = HERE / 'cases/no_crosswalk_no_line_first_view'
CASE = HERE.name + '__no_crosswalk_no_line_first_view'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def emit(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def replace_once(text, old, new):
    assert text.count(old) == 1, (old[:80], text.count(old))
    return text.replace(old, new)


def build():
    TARGET.mkdir(parents=True, exist_ok=True)
    site = json.loads((SOURCE / 'site.json').read_text())
    site['format'] = 'worker-c331230-no-crosswalk-no-line-first-view-site'
    site['stop_line_exists'] = False
    site.pop('stop_line_segment_xy_m')
    site.pop('stop_line_marking_source')
    site['stop_line_absence_source'] = 'synthetic marking inventory; Native and camera review pending'
    site['sight_observer_source'] = 'Native ego pose and world line-of-sight ray; driver visibility unreviewed'
    site['approaching_traffic_source'] = 'Native cross-traffic actor and original-frame position'
    site['sight_probe_start_xy_m'] = [4.0, 0.0]
    site['cross_traffic_spawn_pose'] = [14.0, -18.0, 0.5, 90.0]
    emit(TARGET / 'site.json', site)

    runner = (SOURCE / 'runner.py').read_text()
    runner = replace_once(runner, SOURCE.name, TARGET.name)
    runner = replace_once(runner, 'Exact marked-crosswalk stop case; Native capture requires a reviewed site.', 'Exact first-observed-view stop case; Native capture requires a reviewed site.')
    runner = replace_once(runner, "site.get('stop_line_exists') is not True or\n     not site.get('stop_line_marking_source')", "site.get('stop_line_exists') is not False or\n     not site.get('stop_line_absence_source') or\n     not site.get('sight_observer_source') or\n     not site.get('approaching_traffic_source')")
    runner = replace_once(runner, "line=site['stop_line_segment_xy_m'];junction=site['intersection_polygon_xy_m']\n if (len(line)!=2 or len(junction)<4 or\n     max(x for x,y in line)>=min(x for x,y in junction) or\n     site['ego_spawn_pose'][0]>=min(x for x,y in line) or\n     not (min(y for x,y in line)<=site['ego_spawn_pose'][1]<=max(y for x,y in line))):\n  raise ValueError('Marked stop line must precede junction and spawn')", "junction=site['intersection_polygon_xy_m'];probe=site['sight_probe_start_xy_m']\n if (len(junction)<4 or len(probe)!=2 or\n     not site['ego_spawn_pose'][0]<probe[0]<min(x for x,y in junction) or\n     len(site['cross_traffic_spawn_pose'])!=4):\n  raise ValueError('First-view probe must precede junction and follow spawn')")
    runner = replace_once(runner, "'stop_line_exists':True,'stop_line_marking_source':site['stop_line_marking_source'],\n  'stop_line_segment_xy_m':site['stop_line_segment_xy_m'],", "'stop_line_exists':False,'stop_line_absence_source':site['stop_line_absence_source'],\n  'sight_observer_source':site['sight_observer_source'],\n  'approaching_traffic_source':site['approaching_traffic_source'],")
    old_x = "x0=min(p[0] for p in site['stop_line_segment_xy_m']);x1=min(p[0] for p in site['intersection_polygon_xy_m'])"
    old_y = "y0=min(p[1] for p in site['stop_line_segment_xy_m']);y1=max(p[1] for p in site['stop_line_segment_xy_m'])"
    assert runner.count(old_x) == runner.count(old_y) == 2
    runner = runner.replace(old_x, "x0=site['ego_spawn_pose'][0];x1=min(p[0] for p in site['intersection_polygon_xy_m'])")
    runner = runner.replace(old_y, "y0=min(p[1] for p in site['intersection_polygon_xy_m']);y1=max(p[1] for p in site['intersection_polygon_xy_m'])")
    runner = replace_once(runner, "encoders={};hist=[];frames=[];trace=[];evidence=[];queues={}", "encoders={};hist=[];frames=[];trace=[];evidence=[];sight=[];queues={};traffic=None")
    runner = replace_once(runner, "if ego is None:raise ValueError('Native ego spawn failed')", "if ego is None:raise ValueError('Native ego spawn failed')\n  traffic=world.try_spawn_actor(blueprint,_transform(carla,site['cross_traffic_spawn_pose']))\n  if traffic is None:raise ValueError('Native approaching-traffic spawn failed')\n  traffic.set_autopilot(True)")
    runner = replace_once(runner, "hist.append(row);frames.append({'video_frame':i,'carla_frame':fid,'time_s':time})", "hist.append(row);frames.append({'video_frame':i,'carla_frame':fid,'time_s':time})\n   traffic_pose=traffic.get_transform();traffic_vel=traffic.get_velocity()\n   traffic_speed=(traffic_vel.x**2+traffic_vel.y**2+traffic_vel.z**2)**.5\n   start=carla.Location(x=pose.location.x,y=pose.location.y,z=pose.location.z+1.6)\n   end=carla.Location(x=traffic_pose.location.x,y=traffic_pose.location.y,z=traffic_pose.location.z+1.2)\n   blockers=[]\n   for hit in world.cast_ray(start,end):\n    if ego.bounding_box.contains(hit.location,pose):continue\n    if traffic.bounding_box.contains(hit.location,traffic_pose):continue\n    if hit.location.distance(start)<.05 or hit.location.distance(end)<.02:continue\n    blockers.append({'label':str(hit.label),'position_m':[hit.location.x,hit.location.y,hit.location.z]})\n   visible=(traffic_speed>0 and not blockers)\n   sight.append({'frame':fid,'time_s':time,'approaching_traffic_ids':[traffic.id] if traffic_speed>0 else [],\n      'visible_approaching_traffic_ids':[traffic.id] if visible else [],\n      'ego_position_xy_m':[pose.location.x,pose.location.y],\n      'traffic_position_xy_m':[traffic_pose.location.x,traffic_pose.location.y],\n      'ray_blockers':blockers,'sampled_only':True})")
    runner = replace_once(runner, "rows(root/'stop_history.jsonl',hist);rows(root/'video_frames.jsonl',frames)", "rows(root/'stop_history.jsonl',hist);rows(root/'video_frames.jsonl',frames)\n  rows(root/'sight_history.jsonl',sight)")
    runner = replace_once(runner, "if ego is not None:ego.destroy()", "if traffic is not None:traffic.destroy()\n  if ego is not None:ego.destroy()")
    runner = replace_once(runner, "'halt_before_stop_line_observed'", "'halt_before_first_observed_view'")
    runner = replace_once(runner, "'complete_halt_before_marked_stop_line'", "'complete_halt_relative_to_first_observed_view'")
    runner = replace_once(runner, "'original complete-body speed and marked-line geometry'", "'original complete-body speed and sampled Native sight history'")
    runner = replace_once(runner, "['crosswalk halt ordering unconfirmed']", "['first-view halt ordering unconfirmed']")
    runner = replace_once(runner, "'cause_evidence':['approach_context.json','stop_history.jsonl','video_frames.jsonl']", "'cause_evidence':['approach_context.json','stop_history.jsonl','video_frames.jsonl','sight_history.jsonl']")
    runner = replace_once(runner, "C331230 exact no-crosswalk stop-line CPU check passed", "C331230 exact no-crosswalk first-view CPU check passed")
    (TARGET / 'runner.py').write_text(runner)
    (TARGET / 'finalizer.py').write_text((HERE / 'stop_reference_finalizer.py').read_text())
    cfg = json.loads((SOURCE / 'config.json').read_text())
    cfg['selected_case_id'] = CASE
    cfg['required_atoms'] = [atom for atom in cfg['required_atoms'] if atom != 'st.stop_line']
    cfg['site_packet']['sha256'] = sha(TARGET / 'site.json')
    cfg['recording_description']['context_inputs'][0]['method'] = 'original Native sign, absence inventories and per-frame approaching-traffic sight ray'
    cfg['recording_description']['limitations'] = ['Synthetic site and sampled first-view proxy; actual driver view, Native geometry and legal nearest point unreviewed']
    emit(TARGET / 'config.json', cfg)
    test = '''import unittest\nfrom pathlib import Path\nfrom runner import load_config,CASE,native_crosswalk_absent\nclass BundleTest(unittest.TestCase):\n def test_exact_first_view_case(self):\n  cfg,site=load_config(Path('.'))\n  self.assertEqual(cfg['selected_case_id'],CASE)\n  self.assertFalse(site['near_side_crosswalk_exists'])\n  self.assertFalse(site['stop_line_exists'])\n  self.assertLess(site['sight_probe_start_xy_m'][0],min(x for x,y in site['intersection_polygon_xy_m']))\n  self.assertTrue(native_crosswalk_absent(site,[]))\n  self.assertFalse(site['physical_acceptance_claimed'])\n'''
    files = []
    for name,path in [('runner.py',TARGET/'runner.py'),('finalizer.py',TARGET/'finalizer.py'),('stop_sign_control.py',HERE/'stop_sign_control.py'),('stop_reference_measurements.py',HERE/'stop_reference_measurements.py'),('crosswalk_stop_measurements.py',HERE/'crosswalk_stop_measurements.py'),('site.json',TARGET/'site.json'),('config.json',TARGET/'config.json')]:
        files.append({'path':name,'source':str(path.relative_to(REPO)),'content':path.read_text()})
    files.append({'path':'tests/test_bundle.py','content':test})
    emit(TARGET/'construction.json', {'case_id':CASE,'law_id':'NRS-484A-450-2','cell_id':'C331230','actor':'motor_vehicle_driver','entrypoint':'runner.py','status':'synthetic_diagnostic_only','recording_description':cfg['recording_description'],'measurement_plan':{'procedure':'finalizer.py','source':'original stop, sign, sight, frame map and camera sources'},'static_checks':['Exact no-crosswalk/no-line case and site hash','sight probe precedes junction','Native sign and crosswalk absence checked before capture'],'termination_rules':['900 synchronized frames','sensor/encoder cleanup and world restoration'],'mechanisms':['Native governing stop sign','sampled actor sight ray','four original RGB cameras'],'files':files})
    manifest_path = HERE/'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = {'case_id':CASE,'kind':'delivery','construction':'cases/no_crosswalk_no_line_first_view/construction.json','construction_sha256':sha(TARGET/'construction.json'),'candidate_risk':{'status':'physical','reason':'Native sight opening, approaching actor motion or stop timing may not be realized'},'candidates':[],'measurement_procedure':{'entrypoint':'finalizer.py'},'fixture_recipe':str((TARGET/'diagnostic-recipe.json').relative_to(REPO)),'measurement_contract':str((TARGET/'measurement-contract.json').relative_to(HERE)),'native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'}}
    manifest['cases'] = [x for x in manifest['cases'] if x['case_id'] != CASE] + [entry]
    manifest['status'] = 'partial_three_case_cpu_bundle'
    emit(manifest_path,manifest)
    return entry


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
