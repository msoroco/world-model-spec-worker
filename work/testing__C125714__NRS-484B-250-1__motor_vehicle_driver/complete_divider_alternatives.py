"""Separate divider observations and explicit turning/opening alternatives, with reuse."""
import copy,importlib.util,json,pathlib,xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('b',ROOT/'work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/package_builder.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
ids=json.loads((ROOT/'partitions/demo-test-02.json').read_text())['assignment_ids'];aid=ids[2];folder=ROOT/'work'/aid;spec=json.loads((folder/'package-spec.json').read_text());a=json.loads((ROOT/'inputs'/aid/'assignment.json').read_text());topics=json.loads((ROOT/'inputs/coverage/branch-sources.json').read_text())['laws'][a['law_id']]['topics']
functions='''def divider_relations(p):
    from shapely.geometry import MultiPoint,Polygon
    regions=[Polygon(v) for v in p['barrier_polygons']];rows=p['trajectory'];samples=[]
    for r in rows:
      vertices=r['body_vertices_m'];hull=MultiPoint([v[:2] for v in vertices]).convex_hull
      samples.append({'frame':r['frame'],'partial_xy_overlap':any(hull.intersects(q) for q in regions),'whole_body_xy_within':any(q.covers(hull) for q in regions),'body_bottom_z_m':min(v[2] for v in vertices),'body_top_z_m':max(v[2] for v in vertices),'divider_top_z_m':p.get('divider_top_z_m',.8),'body_lateral_min_y_m':min(v[1] for v in vertices),'body_lateral_max_y_m':max(v[1] for v in vertices)})
    return {'samples':samples,'initial_lateral_body_interval_m':[samples[0]['body_lateral_min_y_m'],samples[0]['body_lateral_max_y_m']],'final_lateral_body_interval_m':[samples[-1]['body_lateral_min_y_m'],samples[-1]['body_lateral_max_y_m']],'opening_source_models':p['opening_source_models'],'legal_over_across_within_definitions_not_assumed':True}

def turn_shape(p):
    import math
    rows=p['trajectory'];moving=[r for r in rows if sum(v*v for v in r['velocity_xy'])>0]
    first,last=moving[0]['velocity_xy'],moving[-1]['velocity_xy'];dot=sum(x*y for x,y in zip(first,last));cross=first[0]*last[1]-first[1]*last[0]
    centers=[[sum(v[j] for v in r['body_vertices_m'])/len(r['body_vertices_m']) for j in [0,1]] for r in rows]
    return {'actual_velocity_direction_change_deg':math.degrees(math.atan2(cross,dot)),'original_body_center_path_xy_m':centers,'original_velocity_xy':[r['velocity_xy'] for r in rows],'movement_count_is_not_a_legal_definition':True}

'''
analysis=spec['analysis'].replace('def statutory_observations(p):',functions+'def statutory_observations(p):').replace("return {'turn_trajectory':", "return {'divider_relations':divider_relations(p),'turn_shape':turn_shape(p),'turn_trajectory':")
pos=analysis.index('    report=');analysis=analysis[:pos]+"    measurements['over_across_within_observations']={'method':'divider_relations','value':divider_relations(p),'sources':{'case_observation.json':h}}\n    measurements['turn_shape_observations']={'method':'turn_shape','value':turn_shape(p),'sources':{'case_observation.json':h}}\n"+analysis[pos:];spec['analysis']=analysis
models=dict(barrier='Physical barrier authored as two0.8m-high OpenDRIVE objects; actual rendering/collision requires Native audit',dividing_section='Non-roadway separating strip bounded by explicit median polygons',dividing_space='Exclusive dividing-space footprint between the opposing roadway boundaries; no legal numeric meaning assigned')
for c in spec['cases']:
 p=c['fixture']['case_observation.json'];p.update(opening_source_models=models,divider_top_z_m=.8)
 # Three diagnostic body positions now follow a semicircle rather than an unrelated collinear shortcut.
 if c['name']!='wrong_roadway':
  shift=c['config'].get('crossing_shift_m',0)
  for v in p['trajectory'][1]['body_vertices_m']:v[0]+=5.25
run=spec['runner'];needle="'opening_width_m':geometry['opening_width_m'],'trajectory':trajectory"
assert needle in run;run=run.replace(needle,needle+",'opening_source_models':"+repr(models)+",'divider_top_z_m':.8")
spec['runner']=run
# Explicit finite inventory alternatives use the same controlled comparison only when the same measured act/context supports them.
branches=spec['branches'];base=branches[0]
for label,rationale in [('drive_over_divider','Original XY footprint plus body bottom/top and divider top Z are separately reported; this evidence is not a legal definition of over.'),('drive_across_divider','Original initial/final lateral body intervals and intermediate footprint overlaps distinguish crossing history; no legal crossing threshold.'),('drive_within_divider','Partial overlap and full-footprint containment are reported separately for every original frame.'),('semicircular_turn','Complete body-center path and actual velocity-direction history on the authored semicircular route; no inference from U-turn label alone.'),('u_turn','Actual opposite-direction velocity change through complete original motion, including paused multiple movement comparison.'),('opening_in_barrier','Source-hashed barrier objects and explicit opening footprint model; actual barrier realization remains a Native audit.'),('opening_in_dividing_section','Same physical gap is an opening in the authored separating section; reuse avoids a redundant recording.'),('opening_in_dividing_space','Same gap in exclusive dividing-space footprint; source model stated separately from physical barrier pixels.')]:
 row=copy.deepcopy(base);row.update(branch_id=a['law_id']+'-'+label,semantic_rationale=rationale);branches.append(row)
spec['branches']=branches;b.write(folder/'package-spec.json',spec);b.build(spec)
# A90-degree left turn needs a different fixed maneuver from the original U-turn cell.
catalog=json.loads((ROOT/'inputs/coverage/candidate-cells.json').read_text())['cells'];cell=next(c for c in catalog if c['cell_id']=='C80909');assert not any('train' in x or 'held' in x for x in cell['allocated_sets']);newaid='testing__C80909__NRS-484B-227-1__motor_vehicle_driver';out=ROOT/'work'/newaid;out.mkdir(exist_ok=True);newa=copy.deepcopy(a);newa.update(assignment_id=newaid,cell_id=cell['cell_id'],cell=cell);b.write(out/'assignment.json',newa)
new=copy.deepcopy(spec);new.update(assignment_id=newaid,seed_assignment_id=aid);r=new['runner'];start=r.index('def check():');end=r.index('\ndef command',start)
r=r[:start]+'''def check():
 cfg=json.loads((ROOT/'config.json').read_text());root=ET.parse(ROOT/'scene.xodr').getroot();roads={r.get('id'):r for r in root.findall('road')}
 assert {'1','2','3','4','13'}<=set(roads);links=roads['13'].find('link');assert links.find('predecessor').get('elementId')=='1' and links.find('successor').get('elementId')=='4'
 assert len(root.findall('.//object[@type="barrier"]'))==2 and cfg['duration_s']==60 and len(cfg['cameras'])==4
 return {'passed':True,'left_turn_connected':True,'physical_motion_verified':False}

def route_points(mapping):
 route=[]
 for road,stations in [(1,range(300,393,2)),(13,[i*10.995574287564276/20 for i in range(21)]),(4,range(2,102,2))]:
  for station in stations:
   p=mapping.get_waypoint_xodr(road,-1,float(station))
   if p is None:raise ValueError('Native90-degree left route missing')
   route.append((p.transform.location.x,p.transform.location.y))
 return route
''' +r[end:]
r=r.replace('mapping.get_waypoint_xodr(1,2 if cfg.get("wrong_initial_roadway",False) else -2,300)','mapping.get_waypoint_xodr(1,-1,300)')
r=r.replace('ego.apply_control(carla.VehicleControl(brake=1,hand_brake=True))',"ego.apply_control(carla.VehicleControl(brake=1,hand_brake=True))\n  other=world.spawn_actor(world.get_blueprint_library().find('vehicle.tesla.model3'),mapping.get_waypoint_xodr(2,-1,100).transform);owned.append(other);other.apply_control(carla.VehicleControl(brake=1,hand_brake=True))")
r=r.replace("'control':requested,'camera_originals':originals", "'other_body_vertices_m':[[v.x,v.y,v.z] for v in other.bounding_box.get_world_vertices(other.get_transform())],'control':requested,'camera_originals':originals")
r=r.replace("'opening_polygon':[[-20,-.5],[20,-.5],[20,.5],[-20,.5]],'opening_width_m':40", "'opening_polygon':cfg['opening_polygon'],'opening_width_m':40").replace("'barrier_polygons':[[[-400,-.5],[-20,-.5],[-20,.5],[-400,.5]],[[20,-.5],[400,-.5],[400,.5],[20,.5]]]", "'barrier_polygons':cfg['barrier_polygons']")
# Source scope must name the actual compatible cell, not the U-turn seed.
r=r.replace("'cell_identity': 'C126120'", "'cell_identity': 'C80909'").replace("'fixed_layout': 'median_opening'", "'fixed_layout': 'divided_road'").replace("'fixed_maneuver': 'u_turn'", "'fixed_maneuver': 'left_turn'").replace("'fixed_control': 'median_barrier'", "'fixed_control': 'other_vehicle'")
new['runner']=r;cases=[]
for name,lo,hi in [('opening_aligned',-20,20),('opening_displaced',-80,-40)]:
 root=ET.parse(ROOT/'references/v6-capability/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/scene.xodr').getroot()
 for roadid,left,right,objid in [('1',-400,lo,227901),('2',hi,400,227902)]:
  road=root.find("road[@id='"+roadid+"']");objects=road.find('objects')
  if objects is None:objects=ET.SubElement(road,'objects')
  center=(left+right)/2;station=center+400 if roadid=='1' else center-7
  ET.SubElement(objects,'object',dict(id=str(objid),name='MedianBarrier'+roadid,type='barrier',s=str(station),t='0',zOffset='0',hdg='0',length=str(right-left),width='1',height='.8',orientation='none'))
 polys=[[[-400,-.5],[lo,-.5],[lo,.5],[-400,.5]],[[hi,-.5],[400,-.5],[400,.5],[hi,.5]]];opening=[[lo,-.5],[hi,-.5],[hi,.5],[lo,.5]]
 c=copy.deepcopy(spec['cases'][0]);c.update(name=name,rationale='Connected actual90-degree left turn; only physical divider-opening alignment changes.',scene=ET.tostring(root,encoding='unicode'));c['config'].update(opening_polygon=opening,barrier_polygons=polys);p=c['fixture']['case_observation.json'];p.update(opening_polygon=opening,barrier_polygons=polys)
 p['scope_context'].update(cell_identity='C80909',fixed_layout='divided_road',fixed_maneuver='left_turn',fixed_control='other_vehicle');p['trajectory'][-1]['velocity_xy']=[0,5]
 for v in p['trajectory'][-1]['body_vertices_m']:v[0]+=8.75
 c['fixture']['scenario_geometry.json'].update(prohibited_median_polygons=polys,median_opening_polygons=[opening]);cases.append(c)
new['cases']=cases;new['comparisons']=[dict(comparison_id='left_turn_opening_alignment',cases=['opening_aligned','opening_displaced'],fixed_conditions=['Same connected90-degree left route and actor controls','Same four-view60s capture, divider dimensions and ordinary vehicle'],deliberate_differences=['Longitudinal opening location only; actual body clearance/overlap measured'])];new['branches']=[dict(name='left_turn',topic_ids=list(topics),cases=['opening_aligned','opening_displaced'],comparison_ids=['left_turn_opening_alignment'])];b.write(out/'package-spec.json',new);b.build(new)
b.write(out/'comparison-audits.json',[dict(comparison_id='left_turn_opening_alignment',case_ids=[newaid+'__opening_aligned',newaid+'__opening_displaced'],fixed_config_selectors=['duration_s','rate_hz','cameras'],checks=[dict(name='opening_full_body_overlap',case_ids=[newaid+'__opening_aligned',newaid+'__opening_displaced'],selector='measurements.over_across_within_observations.value.samples',operator='distinct')])])
bindings=json.loads((ROOT/'work'/ids[0]/'additional-bindings.json').read_text());bindings.append(dict(assignment_id=newaid,original_assignment_id=aid,original_cell_incompatibility='Original fixed U-turn maneuver does not realize a distinct90-degree left turn.',binding_reason='Compatible divided-road left-turn catalog cell; retain separate observed other vehicle.'));b.write(ROOT/'work'/ids[0]/'additional-bindings.json',bindings)
print('completed explicit227 alternatives and',newaid)
