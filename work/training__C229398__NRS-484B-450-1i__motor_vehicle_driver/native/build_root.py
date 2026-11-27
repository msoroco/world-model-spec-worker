"""Materialize canonical assignment dispatch template from selected rail bundle."""
import json
from pathlib import Path
FOLDER = Path(__file__).resolve().parents[1]
def build():
    bundle=json.loads((FOLDER/'native/condition_a/construction.json').read_text())
    manifest=json.loads((FOLDER/'execution-manifest.json').read_text())
    files={item['path']:item['content'] for item in bundle['files']}
    config=json.loads(files['config.json'])
    config['supported_case_ids']=[e['case_id'] for e in manifest['cases']]
    config['cameras']=[{'name':name,'width':width,'height':height,'fps':20,'fov':90,
                        'pose_strategy':strategy,'fov_deg':70}
        for name,width,height,strategy in (
        ('overview',1920,1080,'entire approach and both surveyed physical rails'),
        ('approach',1280,720,'vehicle approach and rail gap'),
        ('reference_corner',1280,720,'nearest physical rail and body footprint'),
        ('driver_reference',1280,720,'driver view and original traffic or authority context'))]
    description=json.loads(json.dumps(bundle['recording_description']))
    existing={c['name'] for c in description['channels']}
    plan=json.loads((FOLDER/'case-plan.json').read_text())
    for observation in plan['observations']:
        name=observation['name']
        if observation.get('mandatory',True) and name not in existing:
            description['channels'].append({'name':name,'unit':'structured','sampling_rate_hz':20,
                'method':'original same-frame Native actor and physical rail source review',
                'time_window':'all 600 original frames','reference_frame':'C229398 original road and both physical rails',
                'uncertainty':'Diagnostic source contract only; original rail identity, traffic context and legal applicability remain unreviewed'})
    config['recording_description']=description
    files['config.json']=json.dumps(config,indent=2)+'\n'
    for name,content in files.items():
        target=FOLDER/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content.rstrip()+'\n')
    root={key:bundle[key] for key in ('case_id','cell_id','actor')}
    root['law_id']='NRS-484B-450-1i'
    root.update(entrypoint='runner.py',files=[{'path':name,'content':content.rstrip()+'\n'} for name,content in files.items()],
        recording_description=description,
        measurement_plan={'entrypoint':'rail_finalize.py','required_sources':['original-rail-survey.json','original-native-rows.jsonl','video_frames.jsonl','capture-seal.json'],'source_review_required':True},
        static_checks=['original physical rail survey and Native actor readback required','600 original frames at 20 Hz and four synchronized views'],
        mechanisms=['Native vehicle pose and extent joined to both physical rail polylines','stop, stand and park alternatives plus separately sealed exception requests'],
        termination_rules=['600 original frames','restore Native world and release owned actors'],
        status='selected_native_cpu_draft_original_capture_pending')
    (FOLDER/'construction.json').write_text(json.dumps(root,indent=2)+'\n')
if __name__=='__main__':build()
