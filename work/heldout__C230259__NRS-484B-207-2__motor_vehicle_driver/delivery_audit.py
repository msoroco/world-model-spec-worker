"""Independent CPU audit of saved overtaking originals and derived measurements."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from overtake_geometry import measure

HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHANNELS = ('full_body_pass_gap_m', 'ego_right_shift_m', 'ego_speed_mps',
            'overtaker_lateral_offset_right_m', 'notice_source_context',
            'right_pass_permission_context')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file() or not path.stat().st_size:
        raise ValueError('Missing original delivery source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def decode(path, expected_frames):
    probe = subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
                            '-show_entries','stream=nb_read_frames','-of','default=nokey=1:noprint_wrappers=1',
                            str(path)],capture_output=True,text=True,check=True)
    if int(probe.stdout.strip()) != expected_frames:
        raise ValueError('Original camera decoded frame count differs: ' + path.name)
    subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','null','-'],
                   stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=True)
    return {'sha256':digest(path),'decoded_frames':expected_frames}


def audit(case, negative=False):
    manifest=json.loads((HERE/'execution-manifest.json').read_text())
    entries=[entry for entry in manifest['cases'] if entry['case_id']==case]
    if len(entries)!=1:
        raise ValueError('Wrong exact delivery case')
    entry=entries[0]
    saved=json.loads((HERE/entry['saved_processing']['receipt']).read_text())
    if saved.get('case_id')!=case or saved.get('passed') is not True or saved.get('originals_preserved') is not True:
        raise ValueError('Saved-source processing receipt differs')
    root=Path(saved['analysis_directory'])
    report=json.loads(required(root,'analysis-report.json').read_text())
    result=json.loads(required(root,'result.json').read_text())
    receipt=json.loads(required(root,'overtake_source_receipt.json').read_text())
    if report.get('case_id')!=case or result.get('case_id')!=case or receipt.get('case_id')!=case:
        raise ValueError('Saved analysis identity differs')
    sources=receipt.get('source_sha256',{})
    for name, expected in sources.items():
        actual='overview.mkv.missing' if negative and name=='overview.mkv' else name
        if digest(required(root,actual))!=expected:
            raise ValueError('Original delivery source hash differs: '+name)
    body=rows(required(root,'overtake_bodies_original.jsonl'))
    trace=rows(required(root,'trace.jsonl'))
    mapping=rows(required(root,'video_frames.jsonl'))
    if not 3<=len(body)==len(trace)==len(mapping):
        raise ValueError('Original delivery frame count differs')
    for index,(b,t,v) in enumerate(zip(body,trace,mapping)):
        if (b['frame']!=t['frame'] or b['time_s']!=t['time_s'] or
                v['native_frame']!=b['frame'] or v['time_s']!=b['time_s'] or
                v['video_frame']!=index):
            raise ValueError('Original delivery body/trace/video join differs')
    geometry=measure(body,receipt['ego_actor_id'],receipt['overtaker_actor_id'])
    samples=geometry['samples'];baseline=samples[0]['ego_right_projection_m']
    expected={
        'full_body_pass_gap_m':[s['rear_to_front_gap_m'] for s in samples],
        'ego_right_shift_m':[s['ego_right_projection_m']-baseline for s in samples],
        'ego_speed_mps':[s['ego_speed_mps'] for s in samples],
        'overtaker_lateral_offset_right_m':[s['overtaker_lateral_offset_right_m'] for s in samples]}
    if set(report.get('measurements',{}))!=set(CHANNELS):
        raise ValueError('Saved delivery measurement inventory differs')
    for name in CHANNELS:
        measurement=report['measurements'][name]
        if measurement.get('sources')!=sources:
            raise ValueError('Saved delivery measurement source binding differs: '+name)
        values=measurement.get('value',[])
        if len(values)!=len(samples) or any((row['frame'],row['time_s'])!=(sample['frame'],sample['time_s']) for row,sample in zip(values,samples)):
            raise ValueError('Saved delivery measurement frame join differs: '+name)
        if name in expected and [row['value'] for row in values]!=expected[name]:
            raise ValueError('Saved delivery measurement value differs: '+name)
    evidence={item['name']:item for item in result.get('recording_evidence',[])}
    if set(evidence)!=set(CHANNELS):
        raise ValueError('Saved delivery recording evidence inventory differs')
    for name,item in evidence.items():
        if digest(required(root,item['reference']))!=item['sha256']:
            raise ValueError('Saved delivery derived channel hash differs: '+name)
    video={}
    for camera in CAMERAS:
        for index,(row,b) in enumerate(zip(rows(required(root,camera+'-frames.jsonl')),body)):
            if row['video_frame']!=index or row['native_frame']!=b['frame'] or abs(row['time_s']-b['time_s'])>.05:
                raise ValueError('Original camera/body frame join differs: '+camera)
        video[camera]=decode(required(root,camera+'.mkv'),len(body))
    if not geometry['first_complete_frame']:
        raise ValueError('Saved delivery full-body completion absent')
    return {'format':'worker-delivery-audit-fixture','case_id':case,'fixture_only':True,
            'originals_sha256':sources,'frame_count':len(body),'first_complete_frame':geometry['first_complete_frame'],
            'four_camera_decode':video,'source_join_verified':True,'measurements_recomputed':True,
            'actual_pixels_confirmed':None,'physical_acceptance_claimed':False,
            'legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True);parser.add_argument('--negative',action='store_true')
    args=parser.parse_args();print(json.dumps(audit(args.case,args.negative)))


if __name__=='__main__':main()
