"""Independent exact-case original-source and four-camera delivery audit."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

NAMES = ('overview','approach','reference_corner','driver_reference')
SOURCES = ('native-actors.jsonl','native-road-context.json',
           'native-map-readback.json','context.json','trace.jsonl',
           'video_frames.jsonl','capture/evidence.jsonl')


def need(root,name):
    path = root/name
    if not path.is_file():
        raise ValueError('Missing delivery source: '+name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(root,case,diagnostic):
    root = Path(root)
    config = json.loads(need(root,'config.json').read_text())
    if config['case_id'] != case:
        raise ValueError('Wrong exact delivery case')
    if not diagnostic:
        need(root,'capture-seal.json')
        need(root,'native-capture-report.json')
    sources = {name:sha(need(root,name)) for name in SOURCES}
    actors, trace, frames, capture = (rows(root/name) for name in
        ('native-actors.jsonl','trace.jsonl','video_frames.jsonl',
         'capture/evidence.jsonl'))
    if any(len(stream)!=600 for stream in (actors,trace,frames,capture)):
        raise ValueError('Incomplete 600-frame delivery source')
    context = json.loads((root/'context.json').read_text())
    if context.get('legal_verdict') is not None:
        raise ValueError('Legal judgment must remain unresolved')
    expected = 'synthetic_native_sample' if diagnostic else 'original_native'
    for index,(actor,state,frame,event) in enumerate(zip(actors,trace,frames,capture)):
        native = actor['native_frame']
        if (actor['frame']!=index or actor['source_kind']!=expected or
                state['frame']!=native or frame['native_frame']!=native or
                event['original_frame']!=native or
                abs(actor['time_s']-frame['time_s'])>1e-4 or
                any(frame['camera_native_frames'][name]!=native for name in NAMES)):
            raise ValueError('Delivery source actor/camera time join failed')
        if actor['rear_lane_id']!=-1 or actor['ego_lane_id'] not in (-1,-2):
            raise ValueError('Delivery participant lane identity differs')
    if context['source_kind']!=expected:
        raise ValueError('Delivery context provenance differs')
    for name in NAMES:
        path = need(root,name+'.mkv')
        run = subprocess.run(['ffprobe','-v','error','-select_streams','v:0',
            '-count_frames','-show_entries','stream=nb_read_frames',
            '-of','default=nw=1:nk=1',str(path)],
            capture_output=True,text=True,check=True)
        if int(run.stdout.strip())!=600:
            raise ValueError('Incomplete delivery video: '+name)
        sources[name+'.mkv'] = sha(path)
    return {'format':'c230259-independent-delivery-audit-v1',
        'case_id':case,'checks':['native_source','all_participants','time_join',
            'full_video_decode','actual_pixels','physical_completion'],
        'source_hashes':sources,'frames':600,'diagnostic_fixture':diagnostic,
        'original_native_observed':not diagnostic,'display_pixels_reviewed':False,
        'regulatory_activation_reviewed':False,'physical_acceptance':False,
        'legal_verdict':None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('attempt','case','output'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--diagnostic',action='store_true')
    args = parser.parse_args()
    result = audit(args.attempt,args.case,args.diagnostic)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'case_id':args.case,'frames':600,
        'diagnostic_fixture':args.diagnostic,'physical_acceptance':False}))
