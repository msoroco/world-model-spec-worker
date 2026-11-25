"""Audit original no-line stop contrasts, preserving physical and legal scope."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

BASE='training__C111331__NRS-484B-250-4__motor_vehicle_driver'
PAIRS={'crosswalk':('crosswalk_stop','crosswalk_no_stop',-23.0),
       'visible_point':('visible_point_stop','visible_point_no_stop',-21.0)}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]


def measure(path,kind,reference):
    path=Path(path)
    names=('native-raw-actors.jsonl','native-signal-readback.jsonl',
           'native-map-readback.json','video_frames.jsonl')
    for name in names:
        if not (path/name).is_file():raise ValueError('Missing required original source: '+name)
    mapping=read(path/'native-map-readback.json')
    if mapping.get('source_kind')!='original_native' or mapping.get('incoming')!={
        '250':{'reference_x_m':reference},'253':{'reference_y_m':reference}}:
        raise ValueError('Original governing reference map readback differs')
    road=ET.parse(path/'road.xodr').getroot()
    for rid in ('250','253'):
        approach=next(r for r in road.findall('road') if r.get('id')==rid)
        types=[obj.get('type') for obj in approach.findall('./objects/object')]
        if types!=(['crosswalk'] if kind=='crosswalk' else []):
            raise ValueError('Original no-line reference hierarchy differs')
    actors=rows(path/'native-raw-actors.jsonl')
    signals=rows(path/'native-signal-readback.jsonl')
    video=rows(path/'video_frames.jsonl')
    if any(len(stream)!=600 for stream in (actors,signals,video)):
        raise ValueError('Complete original 600-frame reference join required')
    low=[];entry=None
    for i,(actor,signal,frame) in enumerate(zip(actors,signals,video)):
        if (actor.get('frame')!=i or signal.get('frame')!=i or frame.get('video_frame')!=i or
                actor.get('native_frame')!=frame.get('native_frame') or
                abs(actor.get('time_s',-100)-frame.get('time_s',-200))>.051):
            raise ValueError('Original reference actor/video join differs')
        if (actor.get('source_kind')!='original_native' or
                signal.get('source_kind')!='original_native' or
                set(signal.get('governing_heads',{}))!={'250:-1','253:-1'} or
                any(head.get('state')!='Off' or head.get('light_box_count',0)<1
                    for head in signal['governing_heads'].values())):
            raise ValueError('Original two-head Off readback differs')
        ego=actor['ego'];front=max(p[0] for p in ego['body_native_xyz_m'])
        if front<reference and ego['speed_mps']<.05:low.append(i)
        if entry is None and front>=-20:entry=i
    if entry is None:raise ValueError('Original ego never entered junction')
    return {'case_id':read(path/'config.json')['case_id'],'reference_kind':kind,
            'reference_x_m':reference,'pre_reference_low_speed_frames':low,
            'ego_entry_frame':entry,'source_sha256':{name:sha(path/name) for name in names},
            'speed_probe_mps':.05,'speed_probe_is_statutory_threshold':False,
            'actual_pixels_reviewed':False,'legal_verdict':None}


def audit(kind,stop,no_stop):
    names=PAIRS[kind];paths=[Path(stop),Path(no_stop)]
    configs=[read(path/'config.json') for path in paths]
    if [c.get('case_id') for c in configs]!=[BASE+'__'+names[0],BASE+'__'+names[1]]:
        raise ValueError('Original exact reference pair differs')
    for key in ('law_id','cell_id','actor','rate_hz','frames','cameras','required_atoms','source_packets'):
        if configs[0].get(key)!=configs[1].get(key):
            raise ValueError('Fixed original reference configuration differs: '+key)
    if sha(paths[0]/'road.xodr')!=sha(paths[1]/'road.xodr'):
        raise ValueError('Original reference comparison road differs')
    metric=[measure(path,kind,names[2]) for path in paths]
    actors=[rows(path/'native-raw-actors.jsonl') for path in paths]
    for left,right in zip(*actors):
        a,b=left['other'],right['other']
        if (any(abs(x-y)>.5 for x,y in zip(a['center_native_xyz_m'],b['center_native_xyz_m'])) or
                abs(a['speed_mps']-b['speed_mps'])>.2):
            raise ValueError('Fixed original other-vehicle trajectory differs')
    if not metric[0]['pre_reference_low_speed_frames'] or metric[1]['pre_reference_low_speed_frames']:
        raise ValueError('Original reference stop/no-stop contrast differs')
    if metric[0]['ego_entry_frame']<=metric[1]['ego_entry_frame']:
        raise ValueError('Original reference entry contrast differs')
    if kind=='visible_point':
        for path in paths:
            review=path/'human-review.json'
            if not review.is_file() or read(review).get('findings',{}).get('view_opening_visible') is not True:
                raise ValueError('Original view-opening pixel review missing')
    return {'format':'c111331-original-stop-reference-comparison-v1',
            'case_ids':[m['case_id'] for m in metric], 'measurements':metric,
            'fixed_conditions_checked':True,'original_native_sources_joined':True,
            'actual_pixels_reviewed':kind=='visible_point','legal_verdict':None}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--kind',choices=PAIRS,required=True)
    p.add_argument('--stop',required=True);p.add_argument('--no-stop',required=True)
    p.add_argument('--output',required=True);a=p.parse_args()
    Path(a.output).write_text(json.dumps(audit(a.kind,a.stop,a.no_stop),indent=2)+'\n')
