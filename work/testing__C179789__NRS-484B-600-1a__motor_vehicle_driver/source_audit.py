"""Exact original-source joins and reusable supplied media decode receipts."""
import hashlib
import json
import sys
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'runtime/main-pipeline-v1/scenario_pipeline'))
from worker_exchange.media import audit as media_audit


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


def audit_sources(attempt,cfg,rows,right_lamp_roi=None):
    attempt=Path(attempt)
    mapping_path=attempt/'video_frames.jsonl'
    mapping=read_rows(mapping_path)
    trace=read_rows(attempt/'trace.jsonl')
    evidence=read_rows(attempt/'capture/evidence.jsonl')
    count=len(rows)
    if not count or any(len(series)!=count for series in (mapping,trace,evidence)):
        raise ValueError('Original sample, trace, evidence and frame-map counts differ')
    diagnostic = (attempt/'fixture-provenance.json').is_file() and (attempt/'raw.mkv').is_file() and not (attempt/'view0.mkv').exists()
    for i,(sample,mapped,state,event) in enumerate(zip(rows,mapping,trace,evidence)):
        frame=sample['frame']
        if (mapped['video_frame']!=i or mapped['native_frame']!=frame or mapped.get('carla_frame')!=frame or state['frame']!=frame or
                event['original_frame']!=frame or abs(mapped['time_s']-sample['time_s'])>1e-6 or
                abs(state['time_s']-sample['time_s'])>1e-6 or
                abs(event['recording_time_s']-sample['time_s'])>1e-6):
            raise ValueError('Original frame/time join differs at index %d'%i)
        environment = state.get('environment_measurements')
        if (not isinstance(environment, dict) or environment.get('frame') != frame or
                abs(environment.get('time_s', -1)-sample['time_s']) > 1e-6 or
                not isinstance(environment.get('weather'), dict)):
            raise ValueError('Same-frame environmental acquisition missing')
        source_frames=mapped.get('source_frames',{})
        if not diagnostic and len(source_frames)!=4:
            raise ValueError('Four original camera frame hashes required')
        for metadata in source_frames.values():
            if metadata.get('native_frame')!=frame or len(metadata.get('source_bgra_sha256',''))!=64:
                raise ValueError('Source camera frame/hash join differs')
    for channel in cfg['case']['recording_description']['channels']:
        name=channel['name'];values=read_rows(attempt/'channels'/(name+'.jsonl'))
        if len(values)!=count:
            raise ValueError('Mandatory channel count differs: '+name)
        for value,sample in zip(values,rows):
            item=value.get('value',{})
            if (abs(value.get('time_s',-1)-sample['time_s'])>1e-6 or
                    not isinstance(item.get('original_observations'),dict) or
                    item.get('physical_sample',{}).get('frame')!=sample['frame']):
                raise ValueError('Mandatory channel original-evidence join differs: '+name)
    mapping_sha=sha(mapping_path)
    audits=[];roi_levels=None
    camera_specs = [(0, cfg['cameras'][0])] if diagnostic else list(enumerate(cfg['cameras']))
    for i,spec in camera_specs:
        video=attempt/'raw.mkv' if diagnostic else attempt/('view%d.mkv'%i)
        receipt=attempt/('view%d.source-audit.json'%i)
        checkers={}
        levels=[]
        roi_path=attempt/'right-lamp-roi-measurements.json'
        if i==0 and right_lamp_roi is not None and not diagnostic:
            x,y,w,h=right_lamp_roi
            checker_version=hashlib.sha256(json.dumps({'source_audit_sha256':sha(Path(__file__)),
                'roi_px':right_lamp_roi},sort_keys=True).encode()).hexdigest()
            def check_roi(frame):
                if frame.width!=spec['width'] or frame.height!=spec['height']:
                    raise ValueError('Right-lamp source dimensions differ')
                if not (0<=x<frame.width and 0<=y<frame.height and w>0 and h>0 and x+w<=frame.width and y+h<=frame.height):
                    raise ValueError('Right-lamp ROI outside source frame')
                total=0
                for yy in range(y,y+h):
                    start=(yy*frame.width+x)*3
                    for j in range(start,start+w*3,3):
                        total+=frame.pixels[j]+frame.pixels[j+1]+frame.pixels[j+2]
                levels.append(total/(w*h*3))
            checkers={'right_lamp_roi_brightness':(checker_version,check_roi)}
        result=media_audit(video,count,checkers=checkers,mapping_sha256=mapping_sha,receipt=receipt)
        if not diagnostic and result['dimensions']!=[spec['width'],spec['height']]:
            raise ValueError('Original source camera dimensions differ')
        if i==0 and right_lamp_roi is not None and not diagnostic:
            if levels:
                if len(levels)!=count:raise ValueError('Right-lamp pixel checker count differs')
                roi_path.write_text(json.dumps({'video_sha256':result['video_sha256'],
                    'mapping_sha256':mapping_sha,'checker_version':checker_version,
                    'roi_px':right_lamp_roi,'levels':levels},indent=2)+'\n')
            stored=json.loads(roi_path.read_text())
            if (stored['video_sha256']!=result['video_sha256'] or stored['mapping_sha256']!=mapping_sha or
                    stored['checker_version']!=checker_version or len(stored['levels'])!=count):
                raise ValueError('Right-lamp pixel measurements stale relative to source receipt')
            roi_levels=stored['levels']
        audits.append({'video':video.name,'receipt':receipt.name,
            'video_sha256':result['video_sha256'],'decoded_frames':result['frames'],
            'rgb_sequence_sha256':result['rgb_sequence_sha256']})
    if diagnostic and right_lamp_roi is not None:
        roi_levels = []  # Diagnostic source has no matching live-camera ROI.
    return {'source_audits':audits,'right_lamp_roi_levels':roi_levels,
            'joined_original_frames':count,'mapping_sha256':mapping_sha}
