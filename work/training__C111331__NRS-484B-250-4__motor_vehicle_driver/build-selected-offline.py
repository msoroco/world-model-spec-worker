"""Build repaired geometry bundles; selection remains pending Native capture."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


RUNNER = '''"""Verify repaired C111331 request and execute original Native capture."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

def check():
    here=Path(__file__).resolve().parent
    cfg=json.loads((here/'config.json').read_text())
    root=ET.parse(here/'road.xodr').getroot()
    assert {s.get('id') for s in root.findall('.//signal')}=={'701','702'}
    for rid in ('250','253'):
        road=next(x for x in root.findall('road') if x.get('id')==rid)
        line,crossing=road.findall('./objects/object')
        assert line.get('type')=='roadMark' and crossing.get('type')=='crosswalk'
        assert float(line.get('s'))<float(crossing.get('s'))<float(road.get('length'))
        assert road.find('./lanes/laneSection/right/lane').get('id')=='-1'
    rows=[json.loads(x) for x in (here/'request.jsonl').read_text().splitlines()]
    assert len(rows)==600 and cfg['rate_hz']==20 and cfg['frames']==600
    for i,row in enumerate(rows):
        assert row['frame']==i and row['time_s']==i/20
        assert row['signal_state_requested']=='Off' and row['native_observed'] is False
        assert row['marked_stop_line_x_m']==-26 and row['near_side_crosswalk_x_m']==-23
    if cfg['case_id'].endswith('controlled_1'):
        assert len({tuple(row['ego_center_xy_m']) for row in rows[130:221]})==1
        assert rows[130]['ego_center_xy_m'][0]+2 < -26
    else:
        assert rows[100]['ego_center_xy_m'][0]+2 >= -26
    return {'case_id':cfg['case_id'],'frames':600,'authored_signals':2,
            'native_signals_observed':False,'physical_stop_observed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true')
    p.add_argument('--output-dir');p.add_argument('--host',default='localhost')
    p.add_argument('--port',type=int,default=2000)
    args=p.parse_args()
    if args.check:print(json.dumps(check()))
    else:
        if not args.output_dir:raise ValueError('Fresh materialized Native output required')
        from capture_selected import capture
        capture(Path(__file__).resolve().parent,Path(args.output_dir),args.host,args.port)
'''

TEST = '''import unittest
from runner import check

class RepairedSource(unittest.TestCase):
    def test_geometry_and_request(self):
        result=check()
        self.assertEqual(result['frames'],600)
        self.assertFalse(result['native_signals_observed'])
'''


def build():
    cases=[]
    road=(HERE/'selected-road.xodr').read_text()
    assignment=(ROOT/'inputs'/ASSIGNMENT/'assignment.json').read_text()
    for suffix, name in (('controlled_1','primary'),('controlled_2','contrast')):
        case_id=ASSIGNMENT+'__'+suffix
        candidates=[]
        for candidate, shift in (('primary',0),('fallback1',2)):
            source=HERE/('selected-'+name+'-request.jsonl')
            if candidate=='fallback1':
                import importlib.util
                spec=importlib.util.spec_from_file_location('request',HERE/'selected_request.py')
                module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
                request=''.join(json.dumps(x,sort_keys=True)+'\n' for x in module.build(suffix,shift))
            else:request=source.read_text()
            config={'assignment_id':ASSIGNMENT,'case_id':case_id,'cell_id':'C111331',
                    'law_id':'NRS-484B-250-4','actor':'motor_vehicle_driver',
                    'candidate_id':candidate,'rate_hz':20,'frames':600,
                    'spawn_shift_m':shift,'required_atoms':[],'source_packets':[],
                    'case':{'case_id':case_id},'supported_case_ids':[case_id],
                    'status':'selected_cpu_construction_in_progress'}
            files=[{'path':path,'content':content} for path,content in (
                ('assignment-source.json',assignment),('config.json',json.dumps(config,indent=2)+'\n'),
                ('road.xodr',road),('request.jsonl',request),('runner.py',RUNNER),
                ('native_signal.py',(HERE/'native/signal_readback.py').read_text()),
                ('original_measure.py',(HERE/'native/original_measure.py').read_text()),
                ('capture_selected.py',(HERE/'native/capture_selected.py').read_text()),
                ('assemble_selected.py',(HERE/'native/assemble_selected.py').read_text()),
                ('original_finalize.py',(HERE/'native/original_finalize.py').read_text()),
                ('tests/test_repaired.py',TEST))]
            construction={'case_id':case_id,'cell_id':'C111331','law_id':'NRS-484B-250-4',
                          'actor':'motor_vehicle_driver','entrypoint':'runner.py',
                          'files':files,'status':'selected_cpu_construction_in_progress',
                          'recording_description':{'channels':[],'context_inputs':[],
                            'limitations':['Original Native readback and physical pixels pending']}}
            path=HERE/'selected-offline'/suffix/candidate/'construction.json'
            write(path,construction)
            if candidate=='primary': primary=path
            else:candidates.append({'id':'fallback1','construction':str(path.relative_to(HERE)),
                                    'construction_sha256':sha(path),
                                    'trigger':{'source':'native-map-readback.json',
                                               'metric':'ego_approach_spawn_clearance_m',
                                               'failure_condition':'primary spawn is obstructed or outside the approach lane'},
                                    'changed_knobs':['spawn_shift_m']})
        cases.append({'case_id':case_id,'kind':'draft_not_selected',
                      'construction':str(primary.relative_to(HERE)),
                      'construction_sha256':sha(primary),'candidates':candidates,
                      'candidate_risk':{'status':'physical',
                                        'reason':'Primary approach spawn may be obstructed at Native map import'}})
    manifest=HERE/'selected-offline-manifest.json'
    write(manifest,{'format':'worker-unselected-draft-construction-manifest-v1',
                    'assignment_id':ASSIGNMENT,'status':'selected_cpu_construction_in_progress',
                    'cases':cases,'original_native_observed':False,'delivery_ready':False})
    return manifest


if __name__=='__main__':
    print(build())
