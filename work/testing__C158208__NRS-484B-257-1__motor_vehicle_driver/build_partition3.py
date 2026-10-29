"""Build five exact, source-bound partition 3 packages from this clean clone."""
import copy, hashlib, json, math, shutil, xml.etree.ElementTree as ET
from pathlib import Path

HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1]
IDS=json.loads((REPO/'partitions/demo-test-03.json').read_text())['assignment_ids']
RUNTIME='d57d974ba163b20b63052ca2c68b917b16e876401aa54ee90f3384af8a30893f'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def row(requirement,source,method,key,kind='measured',inputs=None):return {'requirement':requirement,'source':source,'status':'selected_required','evidence_or_gap':'Saved exact-case source and measured or authored context; native realization and legal conclusion require local review.','method':method,'output_key':key,'kind':kind,'inputs':inputs or ['case_context.json','case_observations.jsonl']}
def spec(a):
    law=a['law_id'];lawsrc=a['law']['source'];aid=a['assignment_id']
    inv={'officers':[],'traffic_signals':[],'survey_scope':'complete diagnostic world actor and environment-object survey'}
    if law.endswith('257-1'):
        mode='yield_257_1';context={'sign':{'kind':'yield','road_id':1,'signal_type':'205','proper_erection':'authored; native rendering and governance unverified'},'approach_road_id':1,'governance_basis':'OpenDRIVE sign position and original actor inventory','stop_lines':[],'near_crosswalks':[],'sidewalk_crosswalk_survey':{'near_sidewalks':0,'basis':'authored OpenDRIVE and native environment-object inventory'},'intersection_polygon_xy_m':[[-7,-7],[7,-7],[7,7],[-7,7]],'view_sample_spacing_m':1.0,'ray_target':'through-vehicle body','native_inventory':inv,'entrances':[{'road_id':1,'sign':'yield'},{'road_id':3,'sign':None},{'road_id':4,'sign':None}], 'through_highway_designation':'north-south public highway'}
        rows=[{'frame':21714+i,'time_s':.05*(i+1),'point_xy_m':[-13+i,1.75],'distance_to_intersection_m':6-i,'clear_ray':i>0,'ego_speed_mps':2.2-i*.5,'ego_inside':False,'other_inside':i==2,'other_distance_to_conflict_m':18-i*2,'other_speed_mps':5.0} for i in range(3)]
        req=[row('Proper yield sign erected and governing the subject approach',lawsrc+'; selected witness','sign_governance','yield_sign_governance','sourced_context',['case_context.json']),row('Neither a stop line nor near-side crosswalk, including sidewalk-derived crossing, exists',lawsrc+'; selected witness','reference_hierarchy','reference_hierarchy','sourced_context',['case_context.json']),row('Nearest point with view of approaching through-highway traffic',lawsrc+'; selected witness','nearest_visible_point','nearest_view_sample'),row('Initial slowing or stopping before intersection entry',lawsrc+'; supplied timing summary','initial_yield_response','initial_yield_samples'),row('Yield interaction with through-highway vehicles throughout crossing',lawsrc+'; supplied timing summary','crossing_interaction','through_vehicle_interaction'),row('No actual officer or signal control at the approach',lawsrc+'; exception text','control_exception_inventory','governing_control_inventory','sourced_context',['case_context.json'])]
        extra=[{'requirement':'Stop-sign or marked-line branch','source':lawsrc,'status':'alternative_pending','evidence_or_gap':'Selected branch is a yield sign with no line or near-side crosswalk.'}]
    elif law.endswith('257-2'):
        mode='yield_257_2';context={'sign':{'kind':'yield','road_id':1,'signal_type':'205'},'approach_road_id':1,'governance_basis':'OpenDRIVE sign and native inventory','stop_lines':[],'near_crosswalks':[],'sidewalk_crosswalk_survey':{'near_sidewalks':0,'basis':'authored and native inventory'},'intersection_polygon_xy_m':[[-7,-7],[7,-7],[7,7],[-7,7]],'view_sample_spacing_m':1.0,'ray_target':'other vehicle body','native_inventory':inv,'entrances':[{'road_id':1,'sign':'yield'},{'road_id':3,'sign':None},{'road_id':4,'sign':None}],'through_highway_designation':'none; no entrance designated through'}
        rows=[{'frame':21714+i,'time_s':.05*(i+1),'point_xy_m':[-12+i,1.75],'distance_to_intersection_m':5-i,'clear_ray':True,'ego_speed_mps':2.5-i*.6,'ego_inside':i==2,'other_inside':i>=1,'other_obligated':False,'other_distance_to_conflict_m':9-i*2,'other_speed_mps':4.0} for i in range(3)]
        req=[row('Yield sign at one or more non-through-highway entrances and other entrance obligations',lawsrc+'; selected witness','entrance_obligations','entrance_obligations','sourced_context',['case_context.json']),row('Incorporated subsection 1 stopping-reference hierarchy',lawsrc+'; NRS 484B.257(1)','reference_hierarchy','incorporated_reference_hierarchy','sourced_context',['case_context.json']),row('Initial yield response before entry',lawsrc+'; supplied timing summary','initial_yield_response','initial_yield_samples'),row('Yield to vehicle already within intersection and not obligated to yield throughout crossing',lawsrc+'; selected witness','occupied_intersection_yield','occupied_intersection_interaction'),row('No actual officer or signal control',lawsrc+'; exception text','control_exception_inventory','governing_control_inventory','sourced_context',['case_context.json'])]
        extra=[{'requirement':'Approaching immediate-hazard timing sweep','source':lawsrc+'; selected witness','status':'alternative_pending','evidence_or_gap':'Separate GPU timing sweep and legal hazard judgment remain unresolved; selected exact case is occupied-intersection instance.'}]
    elif law.endswith('407'):
        mode='curve_407';context={'road_type':'curved mountain public highway','curve_radius_m':300.0,'turning_envelope_xy_m':[[101,11],[119,11],[119,26],[101,26]],'highway_designation':'authored public vehicular highway','ray_origin':'each approaching driver eye','ray_target':'subject vehicle body','opposite_direction_goal_deg':201.0,'native_inventory':inv}
        rows=[]
        for i in range(3):
            for side in ('forward','reverse'):
                rows.append({'frame':21714+i,'time_s':.05*(i+1),'point_xy_m':[120+i,0],'ego_speed_mps':2.0,'heading_deg':i*30,'approach_direction':side,'approach_distance_m':152.4-i*5,'clear_ray':side=='forward' and i==2})
        req=[row('Qualifying curved mountain highway and supported reversal envelope',lawsrc+'; selected witness','curved_turn_context','curve_context','sourced_context',['case_context.json']),row('Vehicle turns to proceed opposite direction at the curve',lawsrc+'; law text','reversal_motion','reversal_motion'),row('Original sightlines from both approach directions within 500 feet',lawsrc+'; law text','bidirectional_visibility','both_direction_visibility')];extra=[]
    elif law.endswith('127-2'):
        mode='trucks_127_2';context={'ego_blueprint':'vehicle.carlamotors.european_hgv','leader_blueprint':'vehicle.carlamotors.european_hgv','one_way':True,'same_direction_available_lanes':1,'road_ids':[1],'overtake_segment':None,'native_inventory':inv}
        rows=[{'frame':21714+i,'time_s':.05*(i+1),'point_xy_m':[30+i,0],'ego_speed_mps':8.0,'ego_width_m':2.5,'other_width_m':2.5,'body_gap_m':150+i,'same_lane':True,'overtaking':False} for i in range(3)]
        req=[row('Both following trucks have overall width at least 80 inches',lawsrc+'; selected witness','truck_class_context','qualifying_trucks'),row('One available same-direction lane on a public one-way highway; no overtaking segment',lawsrc+'; exception text','lane_availability','lane_availability','sourced_context',['case_context.json']),row('Continuous body-to-body space relative to 500 feet while following',lawsrc+'; supplied timing summary','following_gap','following_space')];extra=[{'requirement':'Conditions permit and overtaking vehicle may enter without danger','source':lawsrc,'status':'exception_pending','evidence_or_gap':'Native entry envelope, road/traffic conditions and legal without-danger interpretation remain GPU and legal checks.'}]
    else:
        mode='backing_113_2';context={'crosswalk_polygon_xy_m':[[-14,-3.5],[-8,-3.5],[-8,0],[-14,0]],'marked':True,'residence_district':'authored residential frontage','public_highway':'authored public vehicular access','native_inventory':inv}
        rows=[{'frame':21714+i,'time_s':.05*(i+1),'point_xy_m':[-8-i, -1.75],'ego_speed_mps':1.0,'heading_deg':0,'backing':True,'body_crosswalk_overlap_m2':.5+i*.5} for i in range(3)]
        req=[row('Distinctly marked crosswalk on a public highway in residence district',lawsrc+'; selected witness','crosswalk_context','crosswalk_geometry','sourced_context',['case_context.json']),row('Backing and vehicle-body overlap with crosswalk occur in the same original frames',lawsrc+'; supplied timing summary','simultaneous_backing_overlap','backing_crosswalk_overlap')]
        extra=[{'requirement':'Backing into intersection or around street corner','source':lawsrc,'status':'alternative_pending','evidence_or_gap':'Selected branch is on or over the marked crosswalk.'}]
    return mode,context,rows,req,extra

def scene(root,mode):
    source=REPO/('references/accepted-sources/C102372/scene.xodr' if mode in ('curve_407','trucks_127_2') else 'references/accepted-sources/C111325/scene-stop257-v1.xodr')
    t=ET.parse(source);x=t.getroot();x.find('header').set('name',mode+'-exact-v1')
    if mode.startswith('yield'):
        for road in x.findall('road'):
            road.find('objects').clear() if road.find('objects') is not None else None
            road.find('signals').clear() if road.find('signals') is not None else None
            if road.attrib['id'] in ('1','2','11'):
                left=road.find('lanes/laneSection/left')
                if left is not None:left.clear()
        road=next(r for r in x.findall('road') if r.attrib['id']=='1')
        ET.SubElement(road.find('signals'),'signal',id='25701',name='Yield',s='388',t='-4.8',zOffset='2',dynamic='no',orientation='+',country='Germany',type='205',subtype='-1',value='-1',height='.8',width='.8',text='',hOffset='0',pitch='0',roll='0')
        junction=x.find('junction')
        for c in list(junction):
            if c.attrib.get('incomingRoad')=='2':junction.remove(c)
        for c in junction.findall('connection'):
            if c.attrib.get('incomingRoad')=='1':
                for lane in list(c):
                    if lane.attrib.get('from','').startswith('1') or lane.attrib.get('from')=='2':c.remove(lane)
    elif mode=='curve_407':
        road=x.find('road');road.set('length','500');pv=road.find('planView');pv.clear()
        arc=ET.SubElement(pv,'geometry',s='0',x='0',y='0',hdg='0',length='200');ET.SubElement(arc,'arc',curvature=str(1/300))
        angle=200/300;line=ET.SubElement(pv,'geometry',s='200',x=str(300*math.sin(angle)),y=str(300*(1-math.cos(angle))),hdg=str(angle),length='300');ET.SubElement(line,'line')
        ep=road.find('elevationProfile');ep.clear();ET.SubElement(ep,'elevation',s='0',a='0',b='0.02',c='0',d='0')
    elif mode=='trucks_127_2':
        road=x.find('road');road.set('length','450');road.find('planView/geometry').set('length','450')
        ep=road.find('elevationProfile');ep.clear();ET.SubElement(ep,'elevation',s='0',a='0',b='0',c='0',d='0')
        road.find('lanes/laneSection/left').clear()
        lane=road.find('lanes/laneSection/right/lane');lane.find('width').set('a','3.5')
    else:
        for road in x.findall('road'):
            if road.find('signals') is not None:road.find('signals').clear()
            if road.find('objects') is not None:road.find('objects').clear()
        road=next(r for r in x.findall('road') if r.attrib['id']=='1')
        ET.SubElement(road.find('objects'),'object',id='11302',name='Crosswalk',type='roadMark',s='389',t='-1.75',zOffset='.01',hdg='1.57079632679',length='3.5',width='6',height='0',orientation='none')
    ET.indent(t,space='  ');t.write(root/'scene.xodr',encoding='unicode',xml_declaration=True)
    return source

def build(aid):
    root=REPO/'work'/aid;root.mkdir(parents=True,exist_ok=True);a=json.loads((REPO/'inputs'/aid/'assignment.json').read_text());mode,context,rows,req,extra=spec(a)
    for name in ('runner.py','analyze.py'):
        target=root/name
        if target!=HERE/name:shutil.copyfile(HERE/name,target)
    source=scene(root,mode);case_id=aid+'__selected';channels=[{'name':n,'unit':u,'sampling_rate_hz':20,'method':m,'time_window':'entire original 25-second attempt','reference_frame':'original CARLA frame/time and map','uncertainty':'native physical and pixel visibility unverified'} for n,u,m in [('kin.speed','m/s','original actor velocity'),('case_observations','structured','original per-tick actor, footprint and ray samples'),('scene_geometry','structured','native map and authored public-way/crosswalk role'),('control_inventory','structured','original sign, signal and actor inventory')]]
    desc={'channels':channels,'context_inputs':[],'limitations':['No CARLA run in worker; actual motion, sign/crosswalk rendering and visibility require GPU verification.']}
    case={'case_id':case_id,'target_law_id':a['law_id'],'target_type':'boundary_probe','rationale':a['branch'],'variable_assignments':{'target_speed_mps':{'value':3.0 if mode.startswith('yield') else (1.5 if mode=='backing_113_2' else 8.0),'unit':'m/s','kind':'controller'}},'unresolved_judgment_calls':['No diagnostic fixture or sampled geometry establishes physical/legal acceptance.'],'recording_description':desc}
    put(root/'proposals/cases.json',{'cell_id':a['cell_id'],'actor':a['actor'],'status':'draft','sweep_specs':[],'cases':[case]})
    posture={'yield_257_1':([-25,-1.75,.5,0],[-1.75,30,.5,-90],[35,-1.75],[-1.75,-35],'vehicle.lincoln.mkz_2020','vehicle.tesla.model3'),'yield_257_2':([-25,-1.75,.5,0],[-1.75,4,.5,-90],[35,-1.75],[-1.75,-35],'vehicle.lincoln.mkz_2020','vehicle.tesla.model3'),'curve_407':([108.2,18.3,.5,21],None,[80,18],None,'vehicle.lincoln.mkz_2020',None),'trucks_127_2':([25,-1.75,.5,0],[185,-1.75,.5,0],[430,-1.75],[440,-1.75],'vehicle.carlamotors.european_hgv','vehicle.carlamotors.european_hgv'),'backing_113_2':([-6,-1.75,.5,0],None,[-25,-1.75],None,'vehicle.lincoln.mkz_2020',None)}[mode]
    ego_pose,other_pose,ego_target,other_target,ego_bp,other_bp=posture
    measurement_specs=[{'output_key':r['output_key'],'method':r['method'],'inputs':r['inputs']} for r in req]
    cfg={'case':case,'case_id':case_id,'selected_case_id':case_id,'supported_case_ids':[case_id],'cell_id':a['cell_id'],'law_id':a['law_id'],'actor':a['actor'],'mode':mode,'required_atoms':['kin.speed'],'source_packets':['scenario_geometry'] if mode.startswith('yield') or mode=='trucks_127_2' else [],'duration_s':25,'camera':{'width':960,'height':540,'fov_deg':90},'recording_description':desc,'measurement_specs':measurement_specs,'authored_context':context,'ego_blueprint':ego_bp,'other_blueprint':other_bp,'ego_pose':ego_pose,'other_pose':other_pose,'ego_target_xy':ego_target,'other_target_xy':other_target,'target_speed_mps':case['variable_assignments']['target_speed_mps']['value'],'public_way_road_ids':[1,2,3,4,11,12] if mode.startswith('yield') or mode=='backing_113_2' else [1],'authored_test_context':{'core_assumptions':[['asm.public_highway',True]]}}
    put(root/'config.json',cfg)
    term_map={}
    for t in a['source_observation_terms']:
        term=t['term'];name='control_inventory' if term.startswith('dev.') else ('scene_geometry' if term.startswith('st.') else ('kin.speed' if term=='kin.speed' else 'case_observations'))
        term_map[term]={'evidence':'Original-frame '+name+' for '+t['note']+'; legal interpretation separately limited','channels':[name],'source_refs':['inputs/'+aid+'/assignment.json']}
    sources=[{'path':'inputs/'+aid+'/assignment.json','sha256':sha(REPO/'inputs'/aid/'assignment.json')},{'path':str(source.relative_to(REPO)),'sha256':sha(source)}]
    for path in (['references/accepted-sources/C111325/stop257_controller_v2.py','references/accepted-sources/C111325/stop257_native_inventory_v1.py'] if mode.startswith('yield') else ['references/accepted-sources/C102372/following_controller.py'] if mode=='trucks_127_2' else []):sources.append({'path':path,'sha256':sha(REPO/path)})
    plan={'assignment_id':aid,'actor':a['actor'],'cell_id':a['cell_id'],'law_id':a['law_id'],'selected_branch':a['branch'],'requirement_dispositions':[{k:v for k,v in r.items() if k not in ('method','output_key','kind','inputs')} for r in req]+extra,'cases':[{'case_id':case_id,'target_law_id':a['law_id']}],'comparisons':[],'observations':[{'name':x['name'],'mandatory':True} for x in channels],'sources':sources,'existing_evidence':a['existing_evidence'],'runtime_uncertainties':['Native route, actor class, sign/crosswalk role, rays, optical visibility and legal judgment unverified.']+(['No accepted implementation reference selected for this law/cell.'] if mode in ('curve_407','backing_113_2') else []),'source_observation_mapping':term_map}
    put(root/'case-plan.json',plan)
    contract={'format':'worker-measurement-contract-v1','requirements':[{'disposition_index':i,'requirement':r['requirement'],'source':r['source'],'output_key':r['output_key'],'method':r['method'],'kind':r['kind'],'value_type':'object','inputs':r['inputs']} for i,r in enumerate(req)],'negative':{'remove':['case_observations.jsonl'],'error_contains':'Missing required source: case_observations.jsonl'}}
    put(root/'measurement-contract.json',contract);put(root/'case_context.json',context)
    (root/'case_observations.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    additions=[]
    for name in ('case_context.json','case_observations.jsonl'):
        additions.append({'path':name,'source':'work/'+aid+'/'+name,'sha256':sha(root/name)})
    if cfg['source_packets']:
        geo={'source':'authored exact scenario with native topology check required','physical_verification':'diagnostic fixture checks converter path only; native map and road-role inventory required','directed_roadways':[{'direction_xy':[1,0],'one_way':True,'polygon':[[-60,-3.5],[60,-3.5],[60,0],[-60,0]]}]}
        put(root/'scenario_geometry.json',geo);additions.append({'path':'scenario_geometry.json','source':'work/'+aid+'/scenario_geometry.json','sha256':sha(root/'scenario_geometry.json')})
    put(root/'fixture-recipe.json',{'format':'worker-fixture-recipe-v1','base':'runtime/main-pipeline-v1/fixtures/retained-speed','remove':['case.json','config.json','result.json'],'additions':additions})
    test='''import importlib.util,json,unittest,xml.etree.ElementTree as ET\nfrom pathlib import Path\nROOT=Path(__file__).resolve().parents[1]\ndef module(name):\n s=importlib.util.spec_from_file_location(name,ROOT/(name+".py"));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m\nclass ExactCase(unittest.TestCase):\n def test_offline_scene(self):\n  module("runner").check()\n def test_law_specific_measurement(self):\n  a=module("analyze");c=json.loads((ROOT/"case_context.json").read_text());r=[json.loads(x) for x in (ROOT/"case_observations.jsonl").read_text().splitlines()];config=json.loads((ROOT/"config.json").read_text())\n  for spec in config["measurement_specs"]:\n   value=getattr(a,spec["method"])(c,r);self.assertIsInstance(value,dict);self.assertTrue(value)\n def test_negative_case_source(self):\n  with self.assertRaisesRegex(ValueError,"Missing required source: case_observations.jsonl"):module("analyze").read(ROOT/"missing","case_observations.jsonl")\nif __name__=="__main__":unittest.main()\n'''
    (root/'tests').mkdir(exist_ok=True);(root/'tests/test_case.py').write_text(test)
    files=[{'path':n,'content':(root/n).read_text()} for n in ('config.json','runner.py','analyze.py','scene.xodr','tests/test_case.py')]
    construction={'case_id':case_id,'cell_id':a['cell_id'],'actor':a['actor'],'entrypoint':'runner.py','files':files,'measurement_plan':{'selected_requirement_contract':'measurement-contract.json','physical_acceptance':False},'recording_description':desc,'static_checks':['connected authored OpenDRIVE topology','law-specific scene components','camera and duration','mandatory channels'],'termination_rules':['25 seconds or explicit native failure, preserve original capture and restore world'],'mechanisms':['native VehicleControl and actor frame capture','PipelineCapture original channels','FrameMap and original RGB FFV1 video']}
    put(root/'construction.json',construction)
    manifest={'format':'worker-execution-manifest-v1','assignment_id':aid,'runtime_manifest_sha256':RUNTIME,'cases':[{'case_id':case_id,'kind':'capability','construction':'construction.json','construction_sha256':sha(root/'construction.json'),'measurement_procedure':{'entrypoint':'analyze.py','output_schema':'analysis-report.json'},'measurement_contract':'measurement-contract.json','fixture_recipe':'work/'+aid+'/fixture-recipe.json','native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'},'acquisition':{n:{'entrypoint':'runner.py','method':n,'evidence':'original map/actor/frame acquisition and saved finalizer'} for n in ['kin.speed','case_observations','scene_geometry','control_inventory']}}]}
    put(root/'execution-manifest.json',manifest)

if __name__=='__main__':
    for aid in IDS:build(aid)
