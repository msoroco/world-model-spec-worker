"""Independent source, candidate and receipt audit for current synthetic matrix."""
import hashlib
import copy
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
SUFFIXES=('below_500_ft','at_500_ft','above_500_ft')
CANDIDATES=('primary','fallback1','fallback2','fallback3')
CAMERAS=('overview','approach','reference_corner','driver_reference')
CHECKS={'actual_analysis','native_validation','mandatory_observations',
        'lean_decoder','render','final_decode','acquisition_unchanged',
        'derived_outputs_rebuilt','four_camera_sources','selected_measurements',
        'negative_case_source'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def require(condition,message):
    if not condition:raise ValueError(message)


def audit(index=None):
    index=index or json.loads((HERE/'update015-proof-index-v2.json').read_text())
    require(index['format']=='c104538-update015-exact-unselected-matrix','Wrong index format')
    require(index['selected'] is False and index['physical_acceptance_claimed'] is False,'False readiness claim')
    require(len(index['cases'])==3,'Missing case')
    road_hashes=set();trace_hashes=set();evidence_hashes=set();limits=[];count=0
    for suffix,case in zip(SUFFIXES,index['cases']):
        case_id=HERE.name+'__'+suffix
        require(case['case_id']==case_id,'Case identity changed')
        require(len(case['candidates'])==4,'Missing candidate')
        obstruction=json.loads((HERE/'draft-sightline'/suffix/'obstruction.json').read_text())
        radius=obstruction['inner_radius_m']
        limit=1000*math.acos(radius/500)/.3048
        require(abs(limit-obstruction['requested_reference_limit_ft'])<1e-6,'Authored limit changed')
        limits.append(round(limit))
        construction_hashes=set();trigger_sources=set();changed_knobs=[]
        for candidate,proof in zip(CANDIDATES,case['candidates']):
            count+=1
            require(proof['case_id']==case_id and proof['candidate_id']==candidate,'Candidate identity changed')
            folder=HERE/'update015-proofs-v2'/suffix/candidate
            require(proof==json.loads((folder/'proof.json').read_text()),'Proof index differs')
            manifest_path=HERE/f'update015-manifest-{candidate}.json'
            manifest=json.loads(manifest_path.read_text())
            recipe_path=HERE/f'update015-{suffix}-{candidate}-recipe.json'
            recipe=json.loads(recipe_path.read_text())
            spec_path=HERE/f'update015-{suffix}-{candidate}-diagnostic.json'
            spec=json.loads(spec_path.read_text())
            require(proof['manifest_sha256']==sha(manifest_path),'Manifest hash changed')
            require(proof['recipe_sha256']==sha(recipe_path),'Recipe hash changed')
            require(recipe['generator']['sha256']==sha(spec_path),'Text source hash changed')
            require(recipe['sources'][0]['sha256']==sha(spec_path),'Fixture source hash changed')
            entry=next(item for item in manifest['cases'] if item['case_id']==case_id)
            require(entry['fixture_recipe']==f'work/{HERE.name}/{recipe_path.name}','Fixture recipe binding changed')
            construction=next((item for item in [entry,*entry['candidates']] if item['id']==candidate),None)
            require(construction is not None,'Construction missing')
            construction_path=HERE/construction['construction']
            require(construction['construction_sha256']==sha(construction_path)==proof['construction_sha256'],
                    'Construction changed')
            construction_hashes.add(construction['construction_sha256'])
            files={item['path']:item['content'] for item in json.loads(construction_path.read_text())['files']}
            config=json.loads(files['config.json'])
            require(config['case_id']==case_id and config['candidate_id']==candidate,'Config identity changed')
            require([item['name'] for item in config['cameras']]==list(CAMERAS),'Camera contract changed')
            require(files['obstruction.json']==(HERE/'draft-sightline'/suffix/'obstruction.json').read_text(),
                    'Authored obstruction changed')
            require(files['authored_road.xodr']==spec['files']['road.xodr'],'Road differs from fixture')
            if candidate!='primary':
                trigger_sources.add(construction['trigger']['metric'])
                changed_knobs.append(tuple(construction['changed_knobs']))
            road_hashes.add(hashlib.sha256(spec['files']['road.xodr'].encode()).hexdigest())
            trace_hashes.add(hashlib.sha256(spec['files']['trace.jsonl'].encode()).hexdigest())
            evidence_hashes.add(hashlib.sha256(spec['files']['capture/evidence.jsonl'].encode()).hexdigest())
            trace=lines(spec['files']['trace.jsonl']);evidence=lines(spec['files']['capture/evidence.jsonl'])
            frames=lines(spec['files']['capture/native/frames.jsonl'])
            mapping=lines(spec['files']['video_frames.jsonl'])
            body=lines(spec['files']['native_body_history.jsonl'])
            viewpoints=lines(spec['files']['driver_eye_rays.jsonl'])
            require(all(len(rows)==480 for rows in (trace,evidence,frames,mapping,body,viewpoints)),
                    'Missing 480-frame source')
            for i,(t,e,f,m,b,v) in enumerate(zip(trace,evidence,frames,mapping,body,viewpoints)):
                require(t['frame']==e['original_frame']==f['frame']==m['native_frame']==
                        b['native_frame']==v['native_frame'],'Raw frame join changed')
                require(m['video_frame']==i and m['carla_frame']==m['native_frame'],
                        'Camera frame join changed')
                require(t['synthetic_diagnostic'] is True and
                        t['speed_provenance']=='synthetic_native_sample' and
                        e['synthetic_diagnostic'] is True and
                        e['ego']['speed_provenance']=='synthetic_native_sample',
                        'Synthetic speed provenance changed')
                require(e['ego']['body_vertices_m']==b['ego_body_vertices_m'],
                        'Body source join changed')
                require(set(m['original_rgb_sha256'])==set(CAMERAS),'Camera hash map changed')
            require(len(spec['graphs'])==480 and
                    [graph['attributes']['frame'] for graph in spec['graphs']]==
                    [frame['frame'] for frame in frames],'Diagnostic graphs changed')
            require([item['path'] for item in spec['videos']]==[name+'.mkv' for name in CAMERAS],
                    'Diagnostic videos changed')
            context=json.loads(spec['files']['native-construction-context.json'])
            require(context['case_id']==case_id and context['candidate_id']==candidate,
                    'Source context identity changed')
            require(context['authored_obstruction_sha256']==sha(HERE/'draft-sightline'/suffix/'obstruction.json'),
                    'Source obstruction hash changed')
            comp=json.loads((folder/'compatibility.json').read_text())
            saved=json.loads((folder/'process-saved.json').read_text())
            require(proof['compatibility_sha256']==sha(folder/'compatibility.json') and
                    proof['compatibility_log_sha256']==sha(folder/'compatibility.log') and
                    proof['process_saved_sha256']==sha(folder/'process-saved.json') and
                    proof['process_saved_log_sha256']==sha(folder/'process-saved.log'),
                    'Retained receipt changed')
            require(comp['passed'] is True and set(comp['checks'])>=CHECKS and
                    comp['case_id']==case_id and comp['candidate_id']==candidate and
                    comp['construction_sha256']==proof['construction_sha256'] and
                    comp['negative_removed']=='native_body_history.jsonl',
                    'Current compatibility incomplete')
            require(saved['passed'] is True and saved['case_id']==case_id and
                    saved['candidate_id']==candidate and saved['originals_preserved'] is True and
                    saved['timestamp_joins']['frames']==480 and
                    saved['missing_evidence'] is False and
                    saved['physical_acceptance_claimed'] is False and
                    saved['legal_acceptance_claimed'] is False,
                    'Current saved processing incomplete')
        require(len(construction_hashes)==4 and len(trigger_sources)==3 and len(set(changed_knobs))==3,
                'Fallback constructions or triggers not distinct')
    require(limits==[450,500,550],'Statutory boundary sweep changed')
    require(len(road_hashes)==len(trace_hashes)==len(evidence_hashes)==1,
            'Controlled context changed across visibility sweep')
    return {'exact_attempts':count,'compatibility_passed':count,'process_saved_passed':count,
            'raw_frame_joins_checked':count*480,'authored_center_reference_limits_ft':limits,
            'fixed_road_trace_evidence':True,'selected':False,'physical_visibility_proven':False}


if __name__=='__main__':
    positive=audit()
    source=json.loads((HERE/'update015-proof-index-v2.json').read_text())
    negatives=0
    for change in ('missing_candidate','wrong_case','false_acceptance'):
        damaged=copy.deepcopy(source)
        if change=='missing_candidate':damaged['cases'][0]['candidates'].pop()
        elif change=='wrong_case':damaged['cases'][0]['candidates'][0]['case_id']='wrong-case'
        else:damaged['physical_acceptance_claimed']=True
        try:audit(damaged)
        except (ValueError,KeyError,AssertionError):negatives+=1
        else:raise ValueError('Independent audit accepted '+change)
    positive['isolated_negative_rejections']=negatives
    print(json.dumps(positive,sort_keys=True))
