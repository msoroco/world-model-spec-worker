"""Build synthetic 900-frame original-source-shaped CPU audit fixtures.

These fixtures exercise frame joins and media decoding. They are not Native
physical recordings and cannot establish pixel visibility or legal acceptance.
"""
import argparse
import copy
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CASES=(('diagnostic','config'),('second-diagnostic','second-config'),
       ('third-diagnostic','third-config'),('fourth-diagnostic','fourth-config'))

def rows(value):
    return [json.loads(line) for line in value.splitlines() if line.strip()]

def write_rows(path,items):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(x,separators=(',',':'))+'\n' for x in items))

def build(destination,media):
    destination=Path(destination)
    for diagnostic_name,config_name in CASES:
        cfg=json.loads((ROOT/(config_name+'.json')).read_text())
        data=json.loads((ROOT/(diagnostic_name+'.json')).read_text())
        case=cfg['selected_case_id'].split('__')[-1]
        out=destination/case
        if out.exists():
            raise ValueError('Fresh fixture destination required: '+str(out))
        out.mkdir(parents=True)
        (out/'config.json').write_text(json.dumps(cfg,indent=2)+'\n')
        frame_count=round(cfg['duration_s']*cfg['rate_hz'])
        if frame_count!=900:
            raise ValueError('Expected primary 900-frame duration')
        for name,content in data['files'].items():
            target=out/name;target.parent.mkdir(parents=True,exist_ok=True)
            if name.endswith('.jsonl') and name in (
                'crossing_history.jsonl','video_frames.jsonl','trace.jsonl',
                'controller_history.jsonl','capture/evidence.jsonl'):
                source=rows(content)
                padded=[]
                for i in range(frame_count):
                    row=copy.deepcopy(source[i] if i<len(source) else source[-1])
                    frame=100+i;time=round(1+i/20,8)
                    for key in ('frame','carla_frame','original_frame','replay_frame'):
                        if key in row:row[key]=frame
                    if 'video_frame' in row:row['video_frame']=i
                    for key in ('time_s','recording_time_s','replay_simulation_time_s'):
                        if key in row:row[key]=time
                    if 'original_observations' in row:
                        row['original_observations']['frame']=frame
                        row['original_observations']['time_s']=time
                    padded.append(row)
                write_rows(target,padded)
            else:
                target.write_text(content)
        for item in data['videos']:
            src=media/item['path']
            if not src.is_file():raise ValueError('Missing decoded media source '+str(src))
            shutil.copyfile(src,out/item['path'])
        print(out)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--destination',type=Path,required=True)
    p.add_argument('--media',type=Path,required=True);args=p.parse_args()
    build(args.destination,args.media)
