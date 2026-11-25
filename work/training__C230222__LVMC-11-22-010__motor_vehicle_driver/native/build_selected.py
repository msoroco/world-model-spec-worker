"""Promote the two CPU-tested drafts to selected exact Native bundles."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name
VIEWS = ('overview','approach','reference_corner','driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def channels():
    cue = 'source-joined original Native motion and synchronized source camera'
    camera = 'original synchronized driver-facing source; independent human attention review pending'
    return [{'name':name,'unit':unit,'sampling_rate_hz':20,
             'method':camera if name=='driver_reference_video' else cue,
             'time_window':'600 frames / 30 seconds',
             'reference_frame':'camera' if name=='driver_reference_video' else 'world',
             'uncertainty':'Original source and operator visibility require independent review'}
            for name,unit in [('ego_pose','structured'),('ego_speed','m/s'),
                              ('ego_yaw_rate','deg/s'),('ego_acceleration','m/s2'),
                              ('driver_attention_to_operation','unknown'),
                              ('driver_reference_video','video')]]


def build():
    out=[]
    for short in ('reference','contrast'):
        base=json.loads((ROOT/f'draft-primary/{short}/primary/construction.json').read_text())
        base['status']='selected_delivery_prepared'
        base['recording_description']={
            'channels':channels(),
            'context_inputs':[{'name':'native_driving_context','unit':'structured',
                               'method':'sealed original vehicle/camera source context'},
                              {'name':'driver_attention_source_review','unit':'structured',
                               'method':'independent original operator-facing review, pending'}],
            'limitations':['Vehicle motion or synthetic camera pixels cannot establish a person\'s attention.',
                           'Actual operator-facing pixels and independent episode review remain required.']}
        base['measurement_plan']='Finalize 600 original Native motion and four decoded camera streams; measure complete operation and driving cues while leaving attention and legal verdict null.'
        base['mechanisms']=['20 Hz synchronous 30-second source capture',
                            'four original source cameras, including driver reference',
                            'source-derived driving cues with no attention inference']
        base['static_checks']=['exact case identity','600 frames','four cameras',
                               'no invented attention verdict','sealed source join']
        files={f['path']:f for f in base['files']}
        files['finalize.py']={'path':'finalize.py',
                              'content':(ROOT/'native/finalize_selected.py').read_text()}
        for candidate in ('primary','fallback1'):
            d=copy.deepcopy(base)
            cfg=json.loads(files['config.json']['content'])
            cfg['candidate_id']=candidate
            cfg['recording_description']=copy.deepcopy(d['recording_description'])
            cfg['supported_case_ids']=[AID+'__reference',AID+'__contrast']
            if candidate=='fallback1':
                for phase in cfg['control_phases']:
                    phase['throttle']=round(min(0.7,phase['throttle']+0.10),3)
            for f in d['files']:
                if f['path']=='config.json':
                    f['content']=json.dumps(cfg,indent=2,ensure_ascii=False)+'\n'
            if short=='contrast' and candidate=='fallback1':
                for f in d['files']:
                    if f['path']=='tests/test_offline.py':
                        f['content']=f['content'].replace('[0.24, 0.10, 0.08]', '[0.34, 0.2, 0.18]')
            d['files'].append(copy.deepcopy(files['finalize.py']))
            path=ROOT/f'native/selected-{short}-{candidate}-construction.json'
            dump(path,d)
            out.append({'case':short,'candidate':candidate,'construction':str(path.relative_to(ROOT)),
                        'sha256':sha(path)})
    root=json.loads((ROOT/'native/selected-reference-primary-construction.json').read_text())
    for f in root['files']:
        destination=ROOT/f['path']
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(f['content'])
    # Canonical config lists both selected cases. The inlined root construction follows it.
    cfg=json.loads((ROOT/'config.json').read_text())
    cfg['supported_case_ids']=[AID+'__reference',AID+'__contrast']
    dump(ROOT/'config.json',cfg)
    for f in root['files']:
        if f['path']=='config.json':f['content']=(ROOT/'config.json').read_text()
    dump(ROOT/'construction.json',root)
    print(json.dumps(out,indent=2))


if __name__=='__main__':build()
