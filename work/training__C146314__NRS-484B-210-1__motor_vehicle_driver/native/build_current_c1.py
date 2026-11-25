"""Build current-runtime paragraph (c)(1) distance requests."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
OUT = HERE / 'current-c1'
SOURCE = HERE / 'selected-paragraph-d' / 'witness_1' / 'primary' / 'construction.json'
DISTANCES = {'exception_3_1': 61.06, 'exception_3_2': 60.96}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def encoded(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def request_check():
    return '''"""Check the exact paragraph (c)(1) authored request."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def check(bundle):
    bundle = Path(bundle)
    cfg = json.loads((bundle / 'config.json').read_text())
    assignment = json.loads((bundle / 'assignment-source.json').read_text())
    plan = json.loads((bundle / 'case-plan.json').read_text())
    for key, name in {'road_sha256':'one-way-pass.xodr',
                      'tracks_sha256':'requested-tracks.jsonl',
                      'assignment_sha256':'assignment-source.json',
                      'case_plan_sha256':'case-plan.json'}.items():
        if cfg[key] != sha(bundle / name):
            raise ValueError('Changed or missing source: ' + name)
    if (cfg['assignment_id'] != assignment['assignment_id'] or
            cfg['assignment_id'] != plan['assignment_id'] or
            cfg['case_id'] not in [cfg['assignment_id']+'__exception_3_1',
                                   cfg['assignment_id']+'__exception_3_2']):
        raise ValueError('Assignment identity differs')
    if not (cfg['frames']==600 and cfg['rate_hz']==20 and cfg['duration_s']==30 and
            cfg['camera_names']==['overview','approach','reference_corner','driver_reference'] and
            cfg['original_native_observed'] is False and cfg['delivery_ready'] is False):
        raise ValueError('Current source contract differs')
    road = ET.fromstring((bundle / 'one-way-pass.xodr').read_text()).find('road')
    lanes = {int(lane.get('id')):lane for lane in road.findall('./lanes/laneSection/right/lane')}
    if (road.get('id') != '210' or lanes[-1].get('type') != 'driving' or
            lanes[-2].get('type') != 'shoulder' or
            lanes[-2].find('roadMark').get('type') != 'none'):
        raise ValueError('Unmarked shoulder source differs')
    distance = 61.06 if cfg['case_id'].endswith('exception_3_1') else 60.96
    if not math.isclose(cfg['requested_excursion_m'],distance,abs_tol=1e-8):
        raise ValueError('Requested boundary differs')
    lines=(bundle/'requested-tracks.jsonl').read_text().splitlines()
    if len(lines)!=600:
        raise ValueError('Requested frame count differs')
    for i,line in enumerate(lines):
        row=json.loads(line)
        t=(i+1)/20
        x=5+8*t
        blend=max(0,min(1,(x-17.5)/5,(20+distance+2.5-x)/5))
        y=-1.75-3.5*blend
        if not (row['frame']==i and row['time_s']==t and
                row['case_id']==cfg['case_id'] and
                row['source_kind']=='authored_native_request' and
                math.isclose(row['ego_x_m'],x,abs_tol=1e-6) and
                math.isclose(row['ego_y_m'],y,abs_tol=1e-6) and
                row['ego_lane_id']==(-2 if y < -3.5 else -1) and
                row['requested_excursion_m']==distance and
                row['unmarked_pavement_verified'] is False and
                row['actual_right_pass_observed'] is False and row['legal_verdict'] is None):
            raise ValueError('Requested frame differs: '+str(i))
    return {'case_id':cfg['case_id'],'frames':600,'cameras':4,
            'source_bound':True,'original_native_observed':False,'delivery_ready':False}

if __name__=='__main__':
    print(json.dumps(check(Path.cwd())))
'''


def build():
    base = json.loads(SOURCE.read_text())
    entries = []
    for suffix, distance in DISTANCES.items():
        case_id = CASE.name + '__' + suffix
        construction = json.loads(json.dumps(base))
        construction['case_id'] = case_id
        construction['status'] = 'paragraph_c1_cpu_draft_physical_unverified'
        construction['measurement_plan']['legal_verdict'] = None
        files = {item['path']: item for item in construction['files']}
        for item in construction['files']:
            if item['path'] not in ('assignment-source.json','case-plan.json'):
                item['content'] = item['content'].replace('__witness_1', '__'+suffix)
        road = files['one-way-pass.xodr']['content']
        road = road.replace('id="-2" type="driving"','id="-2" type="shoulder"')
        # Only the outer right lane marking is removed.
        pos = road.index('id="-2"')
        road = road[:pos] + road[pos:].replace('type="solid"','type="none"',1)
        files['one-way-pass.xodr']['content'] = road
        capture = files['capture.py']['content'].replace('lane_type=carla.LaneType.Driving','lane_type=carla.LaneType.Any')
        files['capture.py']['content'] = capture
        rows = []
        for i in range(600):
            t=(i+1)/20
            x=5+8*t
            blend=max(0,min(1,(x-17.5)/5,(20+distance+2.5-x)/5))
            y=-1.75-3.5*blend
            rows.append({'frame':i,'time_s':t,'case_id':case_id,'candidate_id':'primary',
                'source_kind':'authored_native_request','road_id':210,'ego_x_m':round(x,6),
                'ego_y_m':round(y,6),'ego_lane_id':-2 if y < -3.5 else -1,
                'lead_x_m':round(35+4*t,6),'lead_y_m':-1.75,'lead_lane_id':-1,
                'requested_excursion_m':distance,'unmarked_pavement_verified':False,
                'one_way_designation_verified':False,'unobstructed_pavement_verified':False,
                'actual_right_pass_observed':False,'legal_verdict':None})
        files['requested-tracks.jsonl']['content']=''.join(json.dumps(row,sort_keys=True,allow_nan=False)+'\n' for row in rows)
        files['check.py']['content']=request_check()
        tests=files['tests/test_exact.py']['content']
        tests=tests.replace('class CurrentPrimary','class CurrentC1')
        files['tests/test_exact.py']['content']=tests
        saved=files['saved.py']['content']
        saved=saved.replace("endswith('__witness_1')","endswith(('__exception_3_1','__exception_3_2'))")
        saved=saved.replace('    right = ahead = 0\n', '    right = ahead = 0\n    source_xy = []\n')
        saved=saved.replace("        is_right = ego[3] < lead[2] and actor_row['observed_ego_lane_id'] == -2\n",
            "        source_xy.append(actor_row['ego']['center_native_xyz_m'][:2])\n"
            "        is_right = ego[3] < lead[2] and actor_row['observed_ego_lane_id'] == -2\n")
        saved=saved.replace("    return {'format': 'c146314-current-primary-saved-measurement-v1',",
            "    crossings=[]\n"
            "    for (x0,y0),(x1,y1) in zip(source_xy,source_xy[1:]):\n"
            "        if (y0+3.5)*(y1+3.5) < 0:\n"
            "            crossings.append(x0+(x1-x0)*(-3.5-y0)/(y1-y0))\n"
            "    if len(crossings)!=2:\n"
            "        raise ValueError('Original shoulder crossing count differs')\n"
            "    source_span=round(crossings[1]-crossings[0],6)\n"
            "    return {'format': 'c146314-current-primary-saved-measurement-v1',")
        saved=saved.replace("            'ego_body_right_of_lead_frames': right,\n",
            "            'ego_body_right_of_lead_frames': right,\n"
            "            'observed_shoulder_centerline_span_m': source_span,\n"
            "            'unmarked_pavement_reviewed': False,\n"
            "            'statutory_200ft_verdict': None,\n")
        files['saved.py']['content']=saved
        final=files['finalize.py']['content']
        final=final.replace("('__witness_1', '__witness_2')","('__exception_3_1', '__exception_3_2')")
        final=final.replace('def measure_paragraph_d(metric):','def measure_paragraph_c1(metric):')
        final=final.replace("        'right_pass_pixels_reviewed', 'original_native_observed')}",
            "        'right_pass_pixels_reviewed', 'original_native_observed',\n"
            "        'observed_shoulder_centerline_span_m', 'unmarked_pavement_reviewed',\n"
            "        'statutory_200ft_verdict')}")
        final=final.replace('values = measure_paragraph_d(metric)','values = measure_paragraph_c1(metric)')
        files['finalize.py']['content']=final
        cfg=json.loads(files['config.json']['content'])
        cfg['case_id']=case_id
        cfg['selected_case_id']=case_id
        cfg['case']={'case_id':case_id}
        cfg['supported_case_ids']=[CASE.name+'__'+name for name in DISTANCES]
        cfg['requested_excursion_m']=distance
        cfg['road_sha256']=hashlib.sha256(road.encode()).hexdigest()
        cfg['tracks_sha256']=hashlib.sha256(files['requested-tracks.jsonl']['content'].encode()).hexdigest()
        files['config.json']['content']=encoded(cfg)
        contract=json.loads(files['measurement-contract.json']['content'])
        contract['case_id']=case_id
        contract['requirements'][0]['disposition_index']=3
        contract['requirements'][0]['output_key']='paragraph_c1_unmarked_excursion_source_observation'
        contract['requirements'][0]['method']='measure_paragraph_c1'
        files['measurement-contract.json']['content']=encoded(contract)
        construction['recording_description']['limitations'].append('The shoulder and distance are authored requests. Actual pavement classification and legal verdict are unreviewed.')
        folder=OUT/suffix
        path=folder/'primary'/'construction.json'
        put(path,construction)
        put(folder/'measurement-contract.json',contract)
        entries.append({'case_id':case_id,'kind':'delivery','construction':suffix+'/primary/construction.json',
            'construction_sha256':sha(path),'measurement_contract':suffix+'/measurement-contract.json',
            'measurement_procedure':{'entrypoint':'finalize.py'},'candidate_risk':{'status':'physical',
            'reason':'Original excursion, pavement condition and right pass require independent review.'},
            'candidates':[],'native_handoff':{'python_env_var':'CARLA_PYTHON',
            'host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'}})
    runtime=json.loads((ROOT/'batch.json').read_text())['runtime']['root']
    manifest={'format':'worker-execution-manifest','assignment_id':CASE.name,
        'runtime_manifest_sha256':sha(ROOT/runtime/'SOURCE-MANIFEST.json'),
        'status':'paragraph_c1_cpu_draft_only','delivery_ready':False,
        'original_native_observed':False,'cases':entries}
    put(OUT/'manifest.json',manifest)
    return {'manifest_sha256':sha(OUT/'manifest.json'),'cases':len(entries)}

if __name__=='__main__':
    print(json.dumps(build(),sort_keys=True))
