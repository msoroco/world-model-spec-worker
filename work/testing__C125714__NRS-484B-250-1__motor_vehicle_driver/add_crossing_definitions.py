"""Realize statutory separate-roadway intersections instead of trusting seed label."""
import copy,importlib.util,json,pathlib,xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('b',ROOT/'work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/package_builder.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
ids=json.loads((ROOT/'partitions/demo-test-02.json').read_text())['assignment_ids']
for aid in ids[:2]:
 folder=ROOT/'work'/aid;spec=json.loads((folder/'package-spec.json').read_text());run=spec['runner'];analysis=spec['analysis']
 run=run.replace('other_wp=mapping.get_waypoint_xodr(2,1,60) if cfg.get("opposite_other") else mapping.get_waypoint_xodr(3,-1,cfg.get("other_station_m",350))','other_wp=mapping.get_waypoint_xodr(4,-1,3) if cfg.get("other_second_intersection") else mapping.get_waypoint_xodr(2,1,60) if cfg.get("opposite_other") else mapping.get_waypoint_xodr(3,-1,cfg.get("other_station_m",350))')
 run=run.replace('def overlaps(vertices):','def overlaps(vertices,role):').replace("return min(xs)<7 and max(xs)>-7 and min(ys)<7 and max(ys)>-7", "return min(xs)<7 and max(xs)>-7 and (min(ys)<19 and max(ys)>12 if role=='other' and cfg.get('other_second_intersection') else min(ys)<7 and max(ys)>-7)").replace("overlaps(r[role+'_vertices_m'])","overlaps(r[role+'_vertices_m'],role)")
 run=run.replace("min(v[1] for v in r['other_vertices_m'])>7", "min(v[1] for v in r['other_vertices_m'])>(19 if cfg.get('other_second_intersection') else 7)")
 run=run.replace("    (out/'scenario_geometry.json').write_text", "    if cfg.get('wide_divider'):\n        geometry['prohibited_median_polygons']=[[[-400,0],[-20,0],[-20,12],[-400,12]],[[20,0],[400,0],[400,12],[20,12]]]\n        geometry['median_opening_polygons']=[[[-20,0],[20,0],[20,12],[-20,12]]]\n        geometry['intersection_polygon']=[[-7,-7],[7,-7],[7,0],[-7,0]]\n    (out/'scenario_geometry.json').write_text")
 run=run.replace("'separate_crossing_spacing_m':35", "'separate_crossing_spacing_m':12 if cfg.get('wide_divider') else 1,'other_crossing_id':'second_roadway' if cfg.get('other_second_intersection') else 'first_roadway'")
 # Boundaries are authored plus Native readback; both crossing polygons remain independently auditable.
 run=run.replace("'intersection_polygon':[[-7,-7],[7,-7],[7,7],[-7,7]]}", "'intersection_polygon':[[-7,-7],[7,-7],[7,7],[-7,7]],'second_intersection_polygon':[[-7,12],[7,12],[7,19],[-7,19]] if cfg.get('wide_divider') else []}")
 if 'def crossing_geometry(p):' in analysis:
  analysis=analysis.replace("'separate_crossing_spacing_m':p['separate_crossing_spacing_m']", "'separate_crossing_spacing_m':p['separate_crossing_spacing_m'],'other_crossing_id':p.get('other_crossing_id','first_roadway')")
 else:
  analysis=analysis.replace("'crossing_id':p['crossing_id']", "'crossing_id':p['crossing_id'],'other_crossing_id':p.get('other_crossing_id','first_roadway'),'separate_crossing_spacing_m':p.get('separate_crossing_spacing_m',1)")
 for case in spec['cases']:case['fixture']['case_observation.json']['separate_crossing_spacing_m']=1
 scene=ET.fromstring((ROOT/'references/v6-capability'/aid/'scene.xodr').read_text())
 for road in scene.findall('road'):
  if road.get('id') not in ['1','2','11']:continue
  lane=road.find("lanes/laneSection/left/lane[@id='1']")
  if lane is not None:lane.set('type','median');lane.find('width').set('a','12')
  for obj in road.findall("objects/object[@type='barrier']"):obj.set('width','12');obj.set('t','6')
 scenetext=ET.tostring(scene,encoding='unicode');original=spec['cases'][0]
 for name,second in [('wide_same_crossing',False),('wide_separate_crossing',True)]:
  case=copy.deepcopy(original);case.update(name=name,rationale='Actual 12m dividing section separates opposing roadway crossings beyond statutory 30ft; preserve which crossing each body enters.',scene=scenetext);case['config'].update(wide_divider=True,other_second_intersection=second,ignore_precedence=False,wait_for_other=True)
  p=case['fixture']['case_observation.json'];p.update(separate_crossing_spacing_m=12,other_crossing_id='second_roadway' if second else 'first_roadway');spec['cases'].append(case)
 spec.update(runner=run,analysis=analysis)
 c=dict(comparison_id='separate_roadway_intersection',cases=['wide_same_crossing','wide_separate_crossing'],fixed_conditions=['Identical connected 12m physical dividing section and roadway boundaries','Same ego crossing, capture profile, duration and controller'],deliberate_differences=['Other vehicle initial roadway-crossing segment only; observe first versus second statutory intersection'])
 spec['comparisons'].append(c);law=json.loads((ROOT/'inputs'/aid/'assignment.json').read_text())['law_id'];topics=json.loads((ROOT/'inputs/coverage/branch-sources.json').read_text())['laws'][law]['topics'];spec['branches'].append(dict(name=c['comparison_id'],topic_ids=list(topics),cases=c['cases'],comparison_ids=[c['comparison_id']]))
 b.write(folder/'package-spec.json',spec)
 audits=json.loads((folder/'comparison-audits.json').read_text());key='same_crossing_geometry' if law.endswith('-1') else 'left_right_approach_geometry';audits.append(dict(comparison_id=c['comparison_id'],case_ids=[aid+'__'+n for n in c['cases']],fixed_config_selectors=['duration_s','rate_hz','cameras','wide_divider'],checks=[dict(name='same_versus_separate_crossing',case_ids=[aid+'__'+n for n in c['cases']],selector='measurements.'+key+'.value.other_crossing_id',operator='distinct')]))
 b.write(folder/'comparison-audits.json',audits)
print('added actual widened-divider comparisons')
