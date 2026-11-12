"""Independent exact-case original-source, participant, time and pixel delivery audit.

Synthetic saved-attempt proofs exercise this script without claiming Native acceptance.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1] if HERE.name.startswith('heldout__C305951') else Path.cwd()
sys.path.insert(0,str(ROOT/'runtime/scenario_pipeline'))
from worker_exchange import media, physical_preparation

PREFIX='heldout__C305951__NRS-484B-223-2__motor_vehicle_driver__'
CAMERAS=('overview','approach','reference_corner','driver_reference')

def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]

def audit(case,attempt,processing,tamper=False):
    attempt,processing=Path(attempt),Path(processing)
    if not case.startswith(PREFIX):raise ValueError('Wrong exact three-lane case')
    receipt=json.loads(processing.read_text())
    report=json.loads((processing.parent/'analysis/analysis-report.json').read_text())
    result=json.loads((processing.parent/'analysis/result.json').read_text())
    if (receipt.get('case_id')!=case or report.get('case_id')!=case or result.get('case_id')!=case or receipt.get('passed') is not True or receipt.get('recorded_only') is not True or receipt.get('originals_preserved') is not True or result.get('physical_acceptance_claimed') is not False or result.get('legal_acceptance_claimed') is not False):
        raise ValueError('Exact saved analysis identity or status differs')
    measures=report.get('measurements',{})
    source_hashes={}
    for name,measure in measures.items():
        sources=measure.get('sources',{})
        if not sources:raise ValueError('Missing original source inventory: '+name)
        if result.get('measured_values',{}).get(name)!=measure.get('value'):
            raise ValueError('Measured value differs: '+name)
        for source,expected in sources.items():
            if source in source_hashes and source_hashes[source]!=expected:
                raise ValueError('Contradictory original source hash: '+source)
            source_hashes[source]=expected
    if tamper:source_hashes['three_lane_frames.jsonl']='0'*64
    for source,expected in source_hashes.items():
        if not (attempt/source).is_file() or digest(attempt/source)!=expected:
            raise ValueError('Original source hash differs: '+source)
    trace=rows(attempt/'trace.jsonl'); mapping=rows(attempt/'video_frames.jsonl'); lanes=rows(attempt/'three_lane_frames.jsonl')
    if len(trace)<2 or not len(trace)==len(mapping)==len(lanes):raise ValueError('Incomplete original frame/participant join')
    for index,(m,t,l) in enumerate(zip(mapping,trace,lanes)):
        if (m.get('video_frame')!=index or (m.get('carla_frame'),m.get('time_s'))!=(t.get('frame'),t.get('time_s')) or (m.get('carla_frame'),m.get('time_s'))!=(l.get('frame'),l.get('time_s'))):
            raise ValueError('Original frame/time join differs')
        if not isinstance(l.get('ego_actor_id'),str) or not isinstance(l.get('ego_corners_xy'),list):
            raise ValueError('Missing original ego body')
    for extra in ('passing_frames.jsonl','allocation_frames.jsonl','left_turn_frames.jsonl'):
        if extra not in source_hashes:continue
        other=rows(attempt/extra)
        if len(other)!=len(mapping) or any((v.get('frame'),v.get('time_s'))!=(m.get('carla_frame'),m.get('time_s')) for v,m in zip(other,mapping)):
            raise ValueError('Original participant/branch time join differs: '+extra)
        if extra=='passing_frames.jsonl' and any(not v.get('other_vehicle_bodies') for v in other):
            raise ValueError('Missing original passing participants')
    # Each original camera is independently decoded in full. The pixel checker
    # checks decoded RGB buffers, but cannot establish camera visibility.
    camera={}
    for name in CAMERAS:
        path=attempt/(name+'.mkv')
        if not path.is_file():raise ValueError('Missing original camera: '+name)
        def visible(frame):
            if len(frame.pixels)!=frame.width*frame.height*3:
                raise ValueError('Original camera pixel buffer differs: '+name)
        camera[name]=media.audit(path,len(mapping),mapping_sha256=digest(attempt/'video_frames.jsonl'),checkers={'actual_pixels':('1'*64,visible)},threads=2)
    manifest=json.loads((HERE/'execution-manifest.json').read_text())
    entry=next(x for x in manifest['cases'] if x['case_id']==case)
    physical_preparation.validate(ROOT,HERE,entry)
    return {'case_id':case,'source_count':len(source_hashes),'joined_frames':len(mapping),'camera_decodes':{name:v['rgb_sequence_sha256'] for name,v in camera.items()},'physical_source_protocol_checked':True,'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--attempt',required=True);p.add_argument('--processing',required=True);p.add_argument('--tamper-source-hash',action='store_true');a=p.parse_args()
    print(json.dumps(audit(a.case,a.attempt,a.processing,a.tamper_source_hash)))
if __name__=='__main__':main()
