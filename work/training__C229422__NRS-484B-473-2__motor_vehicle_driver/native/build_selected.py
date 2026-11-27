"""Bind four exact selected parked-lamp Native constructions to current runtime."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
SUFFIXES=('witness_1','witness_2','exception_1_1','exception_1_2')
SOURCES=('runner.py','controller.py','lamp_source_measure.py','finalize.py',
         'tests/test_controller.py','tests/test_lamp_source_measure.py')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')


def build():
    entries=[]
    for suffix in SUFFIXES:
        case=ROOT.name+'__'+suffix
        config=ROOT/'cases'/suffix/'config.json'
        files=[{'path':name,'content':(ROOT/name).read_text()} for name in SOURCES]
        files.append({'path':'config.json','content':config.read_text()})
        construction={'format':'worker-inline-construction','case_id':case,
            'law_id':'NRS-484B-473-2','cell_id':'C229422','actor':'motor_vehicle_driver',
            'entrypoint':'runner.py','files':files,
            'recording_description':json.loads(config.read_text())['recording_description'],
            'measurement_plan':{'procedure':'source-hashed original Native parked trace, four optical cameras, offset-aware civil-night and lawful-parking review',
                'sources':['parked-lamp-trace.jsonl','video_frames.jsonl','lamp-pixel-review.json',
                           'original-scene-review.json','overview.mkv','approach.mkv',
                           'reference_corner.mkv','driver_reference.mkv'],
                'selected_measurements':['full-interval displayed lamps','depressed or dimmed headlamps',
                                         'undepressed headlamps','cowl or parking lamps used'],
                'legal_conclusion':None},
            'static_checks':['exact law/cell/case identity','four source cameras at 20 Hz for 600 frames',
                             'Native lamp request separate from optical pixel finding',
                             'civil-night, highway and lawful-parking source review'],
            'termination_rules':['retain 600 original Native frames','close four source encoders',
                                 'restore world settings and destroy owned actors'],
            'mechanisms':['source-reviewed highway parking location','stationary handbraked vehicle',
                          'low/high/position lamp-state request','nighttime sun-altitude request',
                          'original four-view source capture']}
        path=ROOT/'cases'/suffix/'construction.json';write(path,construction)
        entries.append({'case_id':case,'kind':'delivery','construction':str(path.relative_to(ROOT)),
            'construction_sha256':sha(path),'candidate_risk':{
                'status':'none','reason':'No alternate CARLA lamp actuator preserves the low/high/parking comparison while changing the optical outcome; original pixel review must reject an indistinguishable realization.'},
            'candidates':[],'measurement_procedure':{'entrypoint':'finalize.py'},
            'measurement_contract':'native/'+('witness' if suffix.startswith('witness') else 'exception')+'-measurement-contract.json',
            'native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST',
                              'port_env_var':'CARLA_PORT'},
            'delivery_readiness':'cpu_preparation_in_progress_original_capture_pending'})
    write(ROOT/'construction.json',json.loads((ROOT/'cases'/SUFFIXES[0]/'construction.json').read_text()))
    write(ROOT/'execution-manifest.json',{'format':'worker-execution-manifest',
        'assignment_id':ROOT.name,'runtime_manifest_sha256':sha(REPO/'runtime/SOURCE-MANIFEST.json'),
        'status':'draft_cpu_preparation','cases':entries})
    return {'selected_cases':4,'construction_sha256':[e['construction_sha256'] for e in entries]}

if __name__=='__main__':print(json.dumps(build(),sort_keys=True))
