"""Independent source, frame, and pixel audit for an exact Engineer-angle-parking delivery."""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from analysis import measure_saved

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('orientation-history.jsonl', 'orientation-context.json', 'video_frames.jsonl',
           'trace.jsonl', 'reviewed-site/site.json')

def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]

def audit(attempt, case_id, diagnostic=False):
    attempt = Path(attempt).resolve()
    config = json.loads(required(attempt, 'config.json').read_text())
    if config.get('selected_case_id') != case_id:
        raise ValueError('selected exact Engineer-angle case differs')
    fixture = (attempt / 'fixture-provenance.json').exists()
    if fixture != diagnostic:
        raise ValueError('diagnostic fixture cannot establish Native delivery')
    if diagnostic:
        provenance = json.loads(required(attempt, 'fixture-provenance.json').read_text())
        if provenance.get('case_id') != case_id or 'Synthetic' not in provenance.get('scope', ''):
            raise ValueError('diagnostic fixture provenance differs')
    acquisition = json.loads(required(attempt, 'acquisition.json').read_text())
    site = json.loads(required(attempt, 'reviewed-site/site.json').read_text())
    all_sources = list(SOURCES) + ['reviewed-site/' + ref['path'] for ref in site['sources'].values()]
    for name in all_sources:
        path = required(attempt, name)
        ref = acquisition.get(name, {})
        if ref.get('kind') != 'original_native' or ref.get('sha256') != sha(path):
            raise ValueError('original Native source missing or changed: ' + name)
    measured = measure_saved(attempt)
    histories = [rows(required(attempt, name)) for name in
                 ('orientation-history.jsonl', 'trace.jsonl', 'video_frames.jsonl')]
    if not all(len(h) == len(histories[0]) for h in histories):
        raise ValueError('angle and camera frame counts differ')
    if not diagnostic and len(histories[0]) != config['duration_s'] * config['rate_hz']:
        raise ValueError('full duration missing')
    for index, (history, trace, mapped) in enumerate(zip(*histories)):
        if (mapped.get('video_frame') != index or
            history.get('frame') != trace.get('frame') or
            trace.get('frame') != mapped.get('carla_frame') or
            history.get('time_s') != mapped.get('time_s')):
            raise ValueError('original frame join differs')
    media = {}
    for camera in CAMERAS:
        video = required(attempt, camera + '.mkv')
        probe = subprocess.run(['ffprobe','-v','error','-select_streams','v:0',
            '-count_frames','-show_entries','stream=nb_read_frames,width,height,r_frame_rate,codec_name',
            '-of','json',str(video)],capture_output=True,text=True,timeout=60)
        if probe.returncode:
            raise ValueError('video probe failed: ' + camera)
        streams = json.loads(probe.stdout).get('streams', [])
        if len(streams) != 1 or int(streams[0].get('nb_read_frames') or -1) != len(histories[0]):
            raise ValueError('full camera frame count differs: ' + camera)
        decode = subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin',
            '-i',str(video),'-f','null','-'],capture_output=True,timeout=120)
        if decode.returncode:
            raise ValueError('full video decode failed: ' + camera)
        pixel = subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin',
            '-i',str(video),'-frames:v','1','-vf','scale=16:16','-f','rawvideo',
            '-pix_fmt','gray','-'],capture_output=True,timeout=60)
        if pixel.returncode or len(pixel.stdout) != 256 or max(pixel.stdout) == min(pixel.stdout):
            raise ValueError('actual pixel content absent: ' + camera)
        media[camera] = {'sha256': sha(video), 'frames': len(histories[0]),
                         'pixel_range': [min(pixel.stdout), max(pixel.stdout)]}
    if not diagnostic:
        seal = json.loads(required(attempt, 'capture-seal.json').read_text())
        if seal.get('events') != ['capture_finished','encoders_closed','restoration_verified'] or seal.get('restoration',{}).get('restored') is not True:
            raise ValueError('Native lifecycle incomplete')
        for name in all_sources + [camera + '.mkv' for camera in CAMERAS]:
            if seal.get('sources',{}).get(name) != sha(attempt / name):
                raise ValueError('Native seal source missing or changed: ' + name)
        native = json.loads(required(attempt, 'native-exit.json').read_text())
        owner = json.loads(required(attempt, 'owner-release.json').read_text())
        if native.get('capture_seal_sha256') != sha(attempt / 'capture-seal.json') or owner.get('native_exit_sha256') != sha(attempt / 'native-exit.json'):
            raise ValueError('Native ownership closure differs')
        result = json.loads(required(attempt, 'result.json').read_text())
        if result.get('maneuver_completed') is not True or result.get('setup_confirmed') is not True:
            raise ValueError('physical maneuver not accepted')
    return {'format':'worker-angle-delivery-audit','case_id':case_id,'passed':True,
            'diagnostic_only':diagnostic,'physical_acceptance':False,
            'legal_acceptance':False,'frame_count':len(histories[0]),
            'measurement':measured,'media':media}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--case-id',required=True)
    parser.add_argument('--diagnostic',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=audit(args.attempt,args.case_id,args.diagnostic)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'case_id':args.case_id,'diagnostic_only':args.diagnostic,'passed':True}))
if __name__=='__main__':main()
