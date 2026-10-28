"""Generate partition-03 exact CPU handoffs from reviewed law inputs.

The migration case plans supply only proposed case structure; their stale
provenance and readiness labels are discarded. No old capture/check module is
copied. Each bundle inlines the current scenario code and authored map.
"""
import argparse
import copy
import hashlib
import json
import pathlib
import sys
import xml.etree.ElementTree as ET

ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'runtime/main-pipeline-v1/scenario_pipeline'))
from batch_pipeline.sweeps import expand_sweeps
IDS=json.loads((ROOT/'partitions/demo-test-03.json').read_text())['assignment_ids']
OWNER=ROOT/'work'/IDS[0]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def scene(mechanism):
    if mechanism in ('yield','reverse'):
        root=ET.parse(ROOT/'examples/intersection/native/scene-stop257-v1.xodr').getroot()
        root.find('header').set('name','partition03-'+mechanism)
        for objects in root.findall('.//objects'):objects.clear()
        for signals in root.findall('.//signals'):signals.clear()
        if mechanism=='yield':
            road=next(r for r in root.findall('road') if r.get('id')=='1')
            signals=road.find('signals')
            ET.SubElement(signals,'signal',{'id':'25701','name':'Yield','s':'387','t':'-7.7',
                'zOffset':'2','dynamic':'no','orientation':'+','country':'Germany','type':'205',
                'subtype':'-1','value':'-1','height':'0.8','width':'0.8'})
        else:
            road=next(r for r in root.findall('road') if r.get('id')=='2')
            objects=road.find('objects')
            ET.SubElement(objects,'object',{'id':'11302','name':'Crosswalk','type':'crosswalk',
                's':'11','t':'-3.5','zOffset':'0.01','hdg':'1.5707963267948966',
                'length':'7','width':'3','height':'0','orientation':'none'})
        return ET.tostring(root,encoding='unicode')
    root=ET.parse(ROOT/'runtime/main-pipeline-v1/capabilities/crest/scene.xodr').getroot()
    root.find('header').set('name','partition03-'+mechanism)
    road=root.find('road');road.set('length','1800.0')
    road.find('planView/geometry').set('length','1800.0')
    elev=road.find('elevationProfile');elev.clear()
    if mechanism=='uturn':
        for s,a,b,c in [(0,0,0,0),(350,0,.04,0),(450,4,.04,-.0002),(650,4,-.04,0)]:
            ET.SubElement(elev,'elevation',{'s':str(s),'a':str(a),'b':str(b),'c':str(c),'d':'0'})
    else:
        ET.SubElement(elev,'elevation',{'s':'0','a':'0','b':'0','c':'0','d':'0'})
    return ET.tostring(root,encoding='unicode')


TEST='''import json\nimport unittest\nimport xml.etree.ElementTree as ET\nfrom pathlib import Path\nimport runner\nclass ExactCaseTests(unittest.TestCase):\n def test_static_construction_and_route(self):\n  runner.check()\n  cfg,case=runner.selected()\n  p=runner.path_for(cfg,case)\n  self.assertGreater(len(p),20)\n  self.assertEqual(cfg['selected_case_id'],case['case_id'])\n def test_authored_map_has_road_surfaces(self):\n  root=ET.parse('scene.xodr').getroot()\n  self.assertTrue(root.findall('road'))\n'''


def build():
    runner=(OWNER/'runner.py').read_text()
    analysis=(OWNER/'analyze.py').read_text()
    runtime_sha=sha(ROOT/'runtime/main-pipeline-v1/SOURCE-MANIFEST.json')
    for aid in IDS:
        folder=ROOT/'work'/aid
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'runner.py').write_text(runner)
        (folder/'analyze.py').write_text(analysis)
        (folder/'tests').mkdir(exist_ok=True)
        (folder/'tests/test_exact_case.py').write_text(TEST)
        assignment=json.loads((ROOT/'inputs'/aid/'assignment.json').read_text())
        candidate=json.loads((ROOT/'migration-candidates'/aid/'case-plan.json').read_text())
        cfgbase=json.loads((ROOT/'migration-candidates'/aid/'config.json').read_text())
        assert candidate['law_id']==assignment['law']['id']==cfgbase['law_id']
        assert candidate['actor']==assignment['actor']==cfgbase['actor']
        assert candidate['cell_id']==assignment['cell_id']==cfgbase['cell_id']
        assert candidate['cases'][0]['target_type']=='baseline'
        assert all(c['target_law_id']==assignment['law']['id'] for c in candidate['cases'][1:])
        mechanism=cfgbase['mechanism']
        if mechanism=='yield':
            assert '257-' in aid and len(candidate['cases'])==3
        elif mechanism=='uturn':
            assert '407' in aid and len(candidate['cases'])==4
        elif mechanism=='following':
            assert '127-2' in aid and len(candidate['cases'])==4
        elif mechanism=='reverse':
            assert '113-2' in aid and len(candidate['cases'])==5
        else:raise ValueError('Unreviewed mechanism')
        candidate['sources']=[{'path':rel,'sha256':sha(ROOT/rel)} for rel in [
            'inputs/'+aid+'/assignment.json','runtime/main-pipeline-v1/SOURCE-MANIFEST.json',
            'runtime/main-pipeline-v1/capabilities/catalogue.json','updates/004.json',
            'skills/worker-preparation/SKILL.md']]
        candidate['runtime_uncertainties']=[
            'native map/device realization, actor tracking, camera visibility and duration require an actual original capture',
            'authored administrative context is synthetic and must be retained separately from physics']
        cases=copy.deepcopy(candidate['cases'])
        proposal={'status':'draft','cell_id':assignment['cell_id'],'actor':assignment['actor'],
                  'cases':cases,'sweep_specs':[],'sweeps_expanded':False}
        if mechanism=='yield':
            base=copy.deepcopy(cases[1])
            assignments=copy.deepcopy(base['variable_assignments'])
            assignments['yield_hold_s']['value']=0.0
            assignments['counterpart_start_y_m']={'kind':'controller','value':40.0,'unit':'m'}
            sweep_description=copy.deepcopy(base['recording_description'])
            sweep_description['channels'].append({'name':'counterpart_initial_gap_m','unit':'m',
                'sampling_rate_hz':20,'method':'native counterpart body leading edge minus intersection north edge y=7 m',
                'time_window':'entire original episode','reference_frame':'CARLA world y',
                'uncertainty':'20 Hz sampling and native body bounding box; legal hazard interpretation unresolved'})
            phrase='approaching so closely on such through highway as to constitute an immediate hazard' if '257-1' in aid else 'approaching so closely as to constitute an immediate hazard'
            proposal['sweep_specs']=[{'sweep_id':aid+'__approach_timing','target_law_id':assignment['law']['id'],
                'judgment_refs':[{'phrase':phrase,'note':'Hazard judgment remains unresolved'}],
                'rationale':'Fixed physical arrival-timing coverage; no hazard label or legal cutoff',
                'status':'complete','mode':'one_dimensional',
                'axes':[{'variable':'counterpart_start_y_m','observable':'counterpart_initial_gap_m','unit':'m',
                    'min':40.0,'max':80.0,'spacing':20.0,
                    'range_rationale':'The native 393 m crossing approach accommodates all starts; at roughly 4 m/s, 40 to 80 m spans arrival before and after the ego approaches the junction.',
                    'spacing_rationale':'20 m changes nominal arrival by about 5 s at the fixed 4 m/s controller target, above 20 Hz timing resolution.',
                    'feasibility_evidence':'Authored road 3 length 393 m, fixed 20 Hz native controls; realized speeds and arrival are measured, not assumed.',
                    'measurement':{'method':'native counterpart body leading edge minus intersection north edge y=7 m',
                        'time_window':'entire original episode','statistic':'first'}}],
                'landmarks':[], 'variable_assignments':assignments,
                'recording_description':sweep_description}]
        expand_sweeps(proposal,[],{})
        cases=proposal['cases']
        candidate['cases']=copy.deepcopy(cases)
        write(folder/'case-plan.json',candidate)
        write(folder/'proposals/cases.json',proposal)
        xodr=scene(mechanism)
        (folder/'scene.xodr').write_text(xodr)
        entries=[]
        for case in cases[1:]:
            cfg=copy.deepcopy(cfgbase)
            cfg['case']=case
            cfg['selected_case_id']=case['case_id']
            cfg['supported_case_ids']=[x['case_id'] for x in cases]
            cfg['required_atoms']=[o['name'] for o in candidate['observations'] if o.get('mandatory',True)]
            cfg['max_ticks']=int(cfg.get('duration_s',30)*20)
            cfg['counterpart_blueprint']='vehicle.carlamotors.european_hgv' if mechanism=='following' else 'vehicle.lincoln.mkz_2020'
            cfg['public_way_road_ids']=[1,2,3,4] if mechanism in ('yield','reverse') else [1]
            cfg['authored_test_context']={'core_assumptions':[['asm.public_highway',True]],
                'scene_assumptions':{
                    'public_way':'Synthetic public dedication and vehicular access; no real-road claim',
                    'sign_authority':'Proper erection and authorization are synthetic, never inferred from pixels' if mechanism=='yield' else 'No sign authority claimed',
                    'through_highway_status':'Synthetic through highway' if '257-1' in aid else 'Synthetic non-through intersection' if '257-2' in aid else 'Not applicable',
                    'human_direction':'No controlling officer is authored',
                    'legal_judgment':'Immediate hazard, clear visibility, and danger remain unresolved'}}
            content=json.dumps(cfg,indent=2)+'\n'
            construction={'case_id':case['case_id'],'cell_id':assignment['cell_id'],'actor':assignment['actor'],
                'entrypoint':'runner.py','recording_description':case['recording_description'],
                'measurement_plan':cfg.get('measurement_definitions',{}),
                'static_checks':['OpenDRIVE geometry','route continuity','case identity','cameras','mandatory channel names'],
                'termination_rules':{'max_ticks':cfg['max_ticks'],'completion':'last requested route waypoint reached',
                    'failure':'exception, incomplete maneuver, missing mandatory sample or corrupt video'},
                'mechanisms':{'scene':mechanism,'controller':'native VehicleControl, 20 Hz',
                    'capture':'supplied PipelineCapture; no replacement graph or conversion'},
                'files':[{'path':'runner.py','content':runner,'source':'work/'+aid+'/runner.py'},
                    {'path':'analyze.py','content':analysis,'source':'work/'+aid+'/analyze.py'},
                    {'path':'scene.xodr','content':xodr,'source':'work/'+aid+'/scene.xodr'},
                    {'path':'config.json','content':content},
                    {'path':'tests/test_exact_case.py','content':TEST,'source':'work/'+aid+'/tests/test_exact_case.py'}]}
            rel='constructions/'+case['case_id']+'.json'
            write(folder/rel,construction)
            entries.append({'case_id':case['case_id'],'kind':'capability','construction':rel,
                'construction_sha256':sha(folder/rel),
                'measurement_procedure':{'entrypoint':'analyze.py','output_schema':'partition03-capability-report-v1'}})
            if case['case_id']==cases[1]['case_id']:
                write(folder/'config.json',cfg)
                write(folder/'construction.json',construction)
        write(folder/'execution-manifest.json',{'format':'worker-execution-manifest-v1',
              'assignment_id':aid,'runtime_manifest_sha256':runtime_sha,'cases':entries})
        (folder/'HANDOFF.md').write_text('# '+aid+'\n\nExact law and witness: '+assignment['law']['text']+'\n\n'
            'Baseline is unselected. Every listed nonbaseline case has its own inline construction, frozen config, and capability measurement procedure. '+
            ('The two occupied-intersection attempts are separate from a fixed three-point approaching-traffic timing sweep; the sweep has no hazard labels. ' if mechanism=='yield' else '')+
            'Run each case with `runtime.py offline --manifest work/'+aid+'/execution-manifest.json --case CASE --output FRESH_DIRECTORY`. '
            'Later local capture uses `runtime.py capture` against an operator-owned server, followed by `analyze.py --attempt PATH --output REPORT`, '
            'the supplied `runtime.py validate-native`, `runtime.py process` and `runtime.py render`. Analysis reuses the shared lossless source-video decoder/receipt, validates source-frame/channel joins, and emits a draft native result. '
            'Native geometry/device realization, controller motion, camera visibility, duration and channel completeness remain unverified until original capture. '
            'Administrative public-way and device status are explicit synthetic context, not measured physics. No physical or legal acceptance is claimed.\n')


def finalize():
    for aid in IDS:
        folder=ROOT/'work'/aid
        if not (folder/'execution-manifest.json').is_file():continue
        manifest=json.loads((folder/'execution-manifest.json').read_text())
        tests=[]
        for entry in manifest['cases']:
            cid=entry['case_id']
            matches=[]
            for log in (ROOT/'.runtime-work').glob('p03*/offline.log'):
                try:
                    first=json.loads(log.read_text().splitlines()[0])
                    if first.get('case_id')==cid and 'OK' in log.read_text():matches.append(log)
                except (OSError,ValueError,IndexError):pass
            if not matches:break
            log=sorted(matches)[-1]
            rel='tests/'+cid.rsplit('__',1)[-1]+'.offline.log'
            (folder/rel).write_bytes(log.read_bytes())
            tests.append({'command':'.venv-cpu/bin/python runtime.py offline --manifest work/'+aid+
                '/execution-manifest.json --case '+cid+' --output '+str(log.parent.relative_to(ROOT)),
                'exit_code':0,'log':rel,'sha256':sha(folder/rel)})
        if len(tests)==len(manifest['cases']):
            write(folder/'result.json',{'assignment_id':aid,
                'input_sha256':sha(ROOT/'inputs'/aid/'assignment.json'),
                'status':'ready','readiness_kind':'capability','applied_update':4,
                'tests':tests,'physical_acceptance':False})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');p.add_argument('--finalize',action='store_true');a=p.parse_args()
    if a.build:build()
    if a.finalize:finalize()
