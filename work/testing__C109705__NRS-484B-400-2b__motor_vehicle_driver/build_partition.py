"""Build partition 01 from reviewed exact inputs and a native capability runner."""
import copy
import hashlib
import runpy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
PART=json.loads((ROOT/'partitions/demo-test-01.json').read_text())['assignment_ids'][1:]
TEMPLATE=ROOT/'work'/PART[0]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2)+'\n')


def map_source(aid):
    if 'C109705' in aid or 'C109749' in aid:
        builder=runpy.run_path(str(ROOT/'examples/judgment/native/build_left253_construction_v1.py'))
        source=builder['xodr']()
        return source.replace('C329654-left253-intersection-v1',aid.split('__')[1]+'-connected-left')
    tree=ET.parse(ROOT/'examples/intersection/native/scene-stop257-v1.xodr')
    root=tree.getroot()
    root.find('header').set('name',aid.split('__')[1]+'-capability-intersection')
    for objects in root.findall('.//objects'):
        objects.clear()
    if 'C331230' not in aid:
        for signals in root.findall('.//signals'):
            signals.clear()
    return ET.tostring(root,encoding='unicode')


def build(aid):
    folder=ROOT/'work'/aid
    folder.mkdir(parents=True,exist_ok=True)
    assignment=json.loads((ROOT/'inputs'/aid/'assignment.json').read_text())
    candidate=ROOT/'migration-candidates'/aid
    plan=json.loads((candidate/'case-plan.json').read_text())
    cfgbase=json.loads((candidate/'config.json').read_text())
    assert plan['assignment_id']==aid
    assert plan['law_id']==assignment['law']['id']
    assert plan['cell_id']==assignment['cell_id']
    assert plan['actor']==assignment['actor']=='motor_vehicle_driver'
    assert plan['cases'][0]['target_type']=='baseline'
    assert all(c['target_law_id']==plan['law_id'] for c in plan['cases'][1:])
    # Replace retired source references and never inherit old readiness.
    refs=['inputs/'+aid+'/assignment.json','runtime/main-pipeline-v1/SOURCE-MANIFEST.json',
          'examples/intersection/native/scene-stop257-v1.xodr','updates/004.json',
          'skills/worker-preparation/SKILL.md']
    if 'C109705' in aid or 'C109749' in aid:
        refs.append('examples/judgment/native/build_left253_construction_v1.py')
    plan['sources']=[{'path':rel,'sha256':sha(ROOT/rel)} for rel in refs]
    if 'C160013' in aid:
        for case in plan['cases'][1:]:
            case['target_type']='sweep_point'
            case['unresolved_judgment_calls']=['sufficient space','without danger']
        plan['runtime_uncertainties'].append('Gap sweep is a physical capability study, not a statutory threshold.')
    write(folder/'case-plan.json',plan)
    proposal={'status':'draft','cell_id':plan['cell_id'],'actor':plan['actor'],
              'cases':copy.deepcopy(plan['cases']),'sweep_specs':[],
              'sweeps_expanded':True}
    if 'C160013' in aid:
        proposal['sweep_specs']=[{'sweep_id':'caravan_gap_10_30_m','target_law_id':plan['law_id'],
          'judgment_refs':['sufficient space','without danger'],'mode':'one_dimensional',
          'axes':[{'variable':'commanded_gap','observable':'measured_footprint_gap_m',
                   'unit':'m','minimum':10,'maximum':30,'spacing':10,
                   'measurement':{'method':'leader rear minus ego front from original native body vertices',
                                  'time_window':'full original run','statistic':'min'}}],
          'physical_feasibility_evidence':'capability experiment; actual spacing and entrant clearance unverified',
          'range_rationale':'fixed 10, 20 and 30 m engineering probe range, not legal standard',
          'spacing_rationale':'10 m gross physical change visible in footprint gap',
          'sourced_landmarks':[],
          'full_assignments':'exact cases in cases[]',
          'recording_description':plan['cases'][1]['recording_description']}]
    write(folder/'proposals/cases.json',proposal)
    runner=(TEMPLATE/'runner.py').read_text()
    analysis=(TEMPLATE/'analyze.py').read_text()
    if aid != PART[0]:
        (folder/'runner.py').write_text(runner)
        (folder/'analyze.py').write_text(analysis)
    xodr=map_source(aid)
    (folder/'intersection.xodr').write_text(xodr)
    markings=None
    if 'C331230' in aid:
        markings=(ROOT/'examples/intersection/native/stop257_reference_markings_geometry_v2.py').read_text()
        (folder/'markings.py').write_text(markings)
    test='''import json\nimport unittest\nfrom pathlib import Path\nimport runner\nclass CaseTests(unittest.TestCase):\n def test_exact_selected_geometry_and_channels(self):\n  runner.check()\n  cfg=json.loads(Path('config.json').read_text())\n  self.assertEqual(cfg['selected_case_id'],cfg['case']['case_id'])\n  self.assertEqual(cfg['law_id'],cfg['case']['target_law_id'])\n def test_route_continuity(self):\n  cfg=json.loads(Path('config.json').read_text())\n  points=runner.route(cfg)\n  self.assertTrue(all(max(abs(a[0]-b[0]),abs(a[1]-b[1]))<=1.5 for a,b in zip(points,points[1:])))\n'''
    (folder/'tests').mkdir(exist_ok=True)
    (folder/'tests/test_case.py').write_text(test)
    entries=[]
    for case in plan['cases'][1:]:
        cfg=copy.deepcopy(cfgbase)
        cfg['case']=copy.deepcopy(case)
        cfg['selected_case_id']=case['case_id']
        cfg['observations']=plan['observations']
        cfg['required_atoms']=[o['name'] for o in plan['observations'] if o.get('mandatory',True)]
        cfg['max_ticks']=600
        cfg['public_way_road_ids']=[1,2,3,4]
        cfg['authored_test_context']={'core_assumptions':[
          'Public highway dedication and access are explicit synthetic assumptions.',
          'Driver control identity is authored; actual motion and device governance require native evidence.',
          'Stop sign authorization is an explicit synthetic assumption where applicable.']}
        files=[{'path':'runner.py','content':runner,'source':'work/'+aid+'/runner.py'},
               {'path':'analyze.py','content':analysis,'source':'work/'+aid+'/analyze.py'},
               {'path':'intersection.xodr','content':xodr,'source':'work/'+aid+'/intersection.xodr'},
               {'path':'config.json','content':json.dumps(cfg,indent=2)+'\n'},
               {'path':'tests/test_case.py','content':test,'source':'work/'+aid+'/tests/test_case.py'}]
        if markings is not None:
            files.append({'path':'markings.py','content':markings,'source':'work/'+aid+'/markings.py'})
        construction={'case_id':case['case_id'],'cell_id':plan['cell_id'],'actor':plan['actor'],
          'entrypoint':'runner.py','recording_description':case['recording_description'],
          'measurement_plan':{'source':'physical_samples.jsonl','analysis':'analyze.py',
             'exact_case_id':case['case_id'],'original_observation_rate_hz':20},
          'static_checks':['OpenDRIVE two-directional lanes','route continuity','four camera dimensions','required channel names'],
          'termination_rules':{'maximum_ticks':600,'success':'route endpoint reached','failure':'incomplete route or exception'},
          'mechanisms':{'road':'authored OpenDRIVE with native map',
                        'controller':'native VehicleControl at 20 Hz',
                        'capture':'supplied PipelineCapture original telemetry, all actors, source video frames'},
          'files':files}
        rel='constructions/'+case['case_id']+'.json'
        write(folder/rel,construction)
        entries.append({'case_id':case['case_id'],'kind':'capability','construction':rel,
          'construction_sha256':sha(folder/rel),
          'measurement_procedure':{'entrypoint':'analyze.py','output_schema':'partition-01-capability-report-v1'}})
        if case['case_id']==plan['cases'][1]['case_id']:
            write(folder/'config.json',cfg)
            write(folder/'construction.json',construction)
    write(folder/'execution-manifest.json',{'format':'worker-execution-manifest-v1','assignment_id':aid,
       'runtime_manifest_sha256':sha(ROOT/'runtime/main-pipeline-v1/SOURCE-MANIFEST.json'),
       'cases':entries})


if __name__=='__main__':
    for aid in PART:
        build(aid)
