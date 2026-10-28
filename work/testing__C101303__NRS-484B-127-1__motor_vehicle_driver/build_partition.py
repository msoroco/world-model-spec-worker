"""Build partition 04 exact inline bundles from reviewed input and current runtime."""
import copy
import hashlib
import json
import pathlib
import sys

ROOT=pathlib.Path(__file__).resolve().parents[2]
PARTITION=json.loads((ROOT/'partitions/demo-test-04.json').read_text())['assignment_ids']
TEMPLATE=ROOT/'work'/PARTITION[0]
sys.path.insert(0,str(TEMPLATE))
from scenario import build_xodr, mode


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):return json.loads(path.read_text())


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


TEST='''import json\nimport subprocess\nimport sys\nimport unittest\nfrom pathlib import Path\nimport runner\nfrom scenario import lane_path\nclass CaseTests(unittest.TestCase):\n def test_exact_geometry_and_capture_contract(self):\n  runner.check()\n  cfg=json.loads(Path("config.json").read_text())\n  self.assertEqual(cfg["selected_case_id"],cfg["case"]["case_id"])\n  self.assertGreater(len(lane_path(cfg)),100)\n def test_analysis_entrypoint_resolves(self):\n  result=subprocess.run([sys.executable,"analyze.py","--help"],capture_output=True,text=True)\n  self.assertEqual(result.returncode,0,result.stderr)\n'''


def main():
    script={name:(TEMPLATE/name).read_text() for name in ('scenario.py','runner.py','analyze.py')}
    source_map=(ROOT/'examples/intersection/native/scene-stop257-v1.xodr').read_text()
    for aid in PARTITION:
        folder=ROOT/'work'/aid
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'intersection-source.xodr').write_text(source_map)
        assignment=read(ROOT/'inputs'/aid/'assignment.json')
        old=ROOT/'migration-candidates'/aid
        plan=read(old/'case-plan.json')
        assert plan['assignment_id']==aid and plan['law_id']==assignment['law']['id']
        assert plan['actor']==assignment['actor'] and plan['cell_id']==assignment['cell_id']
        case_types=[c['target_type'] for c in plan['cases']]
        assert case_types[0]=='baseline' and len(case_types)>1
        for c in plan['cases']:
            assert c['target_law_id'] in (None,assignment['law']['id'])
            if assignment['law']['id']=='NRS-484B-127-1' and c['target_type']!='baseline':
                c['target_type']='judgment_sweep_point'
                c['sweep_id']=aid+'__physical_gap_grid'
                c.pop('expected_label',None)
        plan['sources']=[{'path':rel,'sha256':sha(ROOT/rel)} for rel in [
            'inputs/'+aid+'/assignment.json','runtime/main-pipeline-v1/SOURCE-MANIFEST.json',
            'examples/intersection/native/scene-stop257-v1.xodr','updates/004.json',
            'migration-candidates/'+aid+'/case-plan.json']]
        plan['runtime_uncertainties']=[
            'Native map/actor realization, controller tracking, original camera visibility and complete duration remain unmeasured.',
            'No CARLA execution or physical acceptance is available to this CPU worker.']
        write(folder/'case-plan.json',plan)
        kind=mode(assignment['law']['id']);xodr=build_xodr(assignment['law']['id'])
        (folder/'scene.xodr').write_text(xodr)
        for name,text in script.items():(folder/name).write_text(text)
        (folder/'tests').mkdir(exist_ok=True)
        (folder/'tests/test_case.py').write_text(TEST)
        cases=copy.deepcopy(plan['cases'])
        sweep=[]
        if kind=='following':
            sweep=[{'sweep_id':aid+'__physical_gap_grid','target_law_id':assignment['law']['id'],
                'judgment_phrase':'reasonable and prudent following distance',
                'axis':{'variable':'commanded_following_gap','observable':'rel.surface_gap',
                        'unit':'m','values':[15,30,45],
                        'measurement':{'window_s':[15,24],'statistic':'mean','method':'original full body longitudinal gap'}},
                'physical_feasibility_evidence':'prospective native controller/vehicle experiment; realization remains unverified',
                'range_rationale':'three fixed engineering targets for discovery, not legal thresholds',
                'sweeps_expanded':True}]
        proposal={'status':'draft','cell_id':assignment['cell_id'],'actor':assignment['actor'],
                  'cases':cases,'sweep_specs':sweep,'sweeps_expanded':True}
        write(folder/'proposals/cases.json',proposal)
        oldcfg=read(old/'config.json')
        cameras=oldcfg['cameras']
        assert len(cameras)==4
        entries=[]
        for index,case in enumerate(cases[1:]):
            context=copy.deepcopy(case['variable_assignments'].get('authored_context',{}).get('value',{}))
            context.update({'public_way':'explicit synthetic assumption, not native map evidence',
                'device_authority':'explicit synthetic assumption where required',
                'native_device_presence':'must be measured during future live run',
                'wet_road':False})
            cfg={'assignment_id':aid,'cell_id':assignment['cell_id'],'law_id':assignment['law']['id'],
                 'actor':assignment['actor'],'mode':kind,'case':case,'selected_case_id':case['case_id'],
                 'supported_case_ids':[c['case_id'] for c in cases],
                 'duration_s':int(oldcfg['duration_s']),'max_ticks':int(oldcfg['duration_s'])*20,
                 'controller':{'speed_kp':0.28,'brake_kp':0.45,'steer_kp':1.5,'gap_kp':0.5,
                               'maximum_speed_mps':40,'red_brake_start_x_m':-30,
                               'stop_brake_start_x_m':-30,'other_brake_start_y_m':20},
                 'required_atoms':[o['name'] for o in plan['observations'] if o.get('mandatory',True)],
                 'observations':plan['observations'],'cameras':cameras,
                 'authored_test_context':context,'public_way_road_ids':[1,2,3,4] if kind in ('yellow_red','inoperative_signal') else [1]}
            files=[{'path':name,'content':text,'source':'work/'+aid+'/'+name}
                   for name,text in script.items()]
            files += [{'path':'intersection-source.xodr','content':source_map,
                       'source':'work/'+aid+'/intersection-source.xodr'},
                      {'path':'scene.xodr','content':xodr,'source':'work/'+aid+'/scene.xodr'},
                      {'path':'tests/test_case.py','content':TEST,'source':'work/'+aid+'/tests/test_case.py'},
                      {'path':'config.json','content':json.dumps(cfg,indent=2)+'\n'}]
            construction={'case_id':case['case_id'],'cell_id':assignment['cell_id'],'actor':assignment['actor'],
                'entrypoint':'runner.py','files':files,'recording_description':case['recording_description'],
                'measurement_plan':{'original_samples':'physical_samples.jsonl',
                    'full_source':'capture/evidence.jsonl','analysis':'analyze.py',
                    'source_video':'four FFV1 lossless MKV views, exact frame mapping and pixel SHA'},
                'static_checks':['OpenDRIVE geometry and legal branch','route continuity','camera dimensions',
                    'mandatory original channel contract','analysis --help import smoke'],
                'termination_rules':{'frame_budget':cfg['max_ticks'],'record_full_trace':True,
                    'error':'retain partial original evidence and report native failure'},
                'mechanisms':{'road':'authored OpenDRIVE exact inline file',
                    'motion':'native VehicleControl, 20 Hz','capture':'supplied PipelineCapture',
                    'saved_validation':'supplied worker_exchange.media.audit and runtime.py process/render'}}
            rel='constructions/'+case['case_id']+'.json'
            write(folder/rel,construction)
            entries.append({'case_id':case['case_id'],'kind':'capability','construction':rel,
                'construction_sha256':sha(folder/rel),
                'measurement_procedure':{'entrypoint':'analyze.py','output_schema':'partition04-capability-report-v1'}})
            if index==0:
                write(folder/'config.json',cfg)
                write(folder/'construction.json',construction)
        write(folder/'execution-manifest.json',{'format':'worker-execution-manifest-v1',
            'assignment_id':aid,'runtime_manifest_sha256':sha(ROOT/'runtime/main-pipeline-v1/SOURCE-MANIFEST.json'),
            'cases':entries})
        handoff='''# Partition 04 capability handoff\n\nExact law: {law}\n\nBranch: {branch}\n\nThe neutral baseline is unselected. Each nonbaseline case has an inline construction and exact SHA in execution-manifest.json. Use `runtime.py offline --manifest work/{aid}/execution-manifest.json --case EXACT_CASE --output NEW_DIRECTORY` for CPU checks. Later operator-owned capture uses `runtime.py capture`; saved conversion and rendering use the supplied `runtime.py process` and `runtime.py render` implementations. `analyze.py --attempt PATH --output REPORT` verifies original channel/frame/video pixels and produces measured results and same-setting follow-up decisions. No simulator ran here.\n\nPublic-way and device authority remain explicit synthetic context. Actual map meshing, device assets and states, actor dynamics, body footprints, visibility, duration and final encoded video are unmeasured; capability code records or diagnoses these. No legal verdict or physical acceptance is claimed.\n'''.format(law=assignment['law']['text'],branch=assignment['branch'],aid=aid)
        (folder/'HANDOFF.md').write_text(handoff)


if __name__=='__main__':main()
