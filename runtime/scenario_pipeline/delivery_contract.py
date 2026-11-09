"""Read-only acceptance of current labels and full video/Lean trace pairs."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from authored_context import assumptions
from expected_labels import expectation, first_scene, rows, sha


def load(path):
    return json.loads(Path(path).read_text())


def full_video(case, attempt, frames, window):
    candidates=[]
    for key in ('primary_review','event_review'):
        receipt=case.get(key)
        if receipt and receipt.get('trace_sha256') and receipt.get('source_video_sha256') and receipt.get('frames')==frames and receipt.get('source_frame_interval')==[0,frames-1]:
            if receipt.get('source_simulation_window_s')!=window:
                continue
            candidates.append((receipt['video'],receipt['video_sha256'],receipt, 'review'))
    playback=case.get('playback_videos',[])
    playback=sorted(playback,key=lambda r: (Path(r['video']).stem!='chase',Path(r['video']).stem!='review'))
    for receipt in playback:
        if receipt.get('trace_coverage')=='Full delivered trace' and receipt.get('frames')==frames:
            candidates.append((receipt['video'],receipt['sha256'],receipt,'playback'))
    if not candidates:
        raise ValueError('Missing a primary video covering every delivered trace frame')
    video,digest,receipt,kind=candidates[0];video=Path(video)
    if sha(video)!=digest:
        raise ValueError('Primary video receipt is stale')
    if int(receipt['ffprobe']['streams'][0]['nb_read_frames'])!=frames:
        raise ValueError('Primary video frame count differs from the delivered trace')
    if kind=='review':
        if receipt['source_video_sha256']!=sha(Path(receipt['source_video'])):
            raise ValueError('Primary review source changed after validation')
        if receipt.get('trace_sha256') and receipt['trace_sha256']!=sha(attempt/'traffic_spec/trace.json'):
            raise ValueError('Primary review is bound to an outdated trace')
        if receipt['scenario_overlay_sha256']!=sha(attempt/'review_scenario.ass'):
            raise ValueError('Primary review has stale expected-label or scene annotations')
        mapping=rows(receipt['frame_map'])
        source=rows(attempt/'video_frames.jsonl')
        if len(mapping)!=frames or any(a['carla_frame']!=b['carla_frame'] or a['time_s']!=b['time_s'] for a,b in zip(mapping,source)):
            raise ValueError('Primary review reordered or omitted source frames')
        if receipt['frame_map_sha256']!=sha(Path(receipt['frame_map'])):
            raise ValueError('Primary review frame-map receipt is stale')
    else:
        if receipt['source_sha256']!=sha(Path(receipt['source'])):
            raise ValueError('Primary playback source changed after validation')
        if receipt.get('scenario_overlay_sha256')!=sha(video.with_suffix('.scenario.ass')):
            raise ValueError('Primary playback has stale expected-label or scene annotations')
        if receipt.get('speed_overlay_sha256')!=sha(video.with_suffix('.measured-speed.ass')):
            raise ValueError('Primary playback has a stale measured-speed overlay')
    return video,digest,receipt


def inspect_case(cell, case):
    if case.get('status')!='validated' or not case.get('decoder_passed'):
        raise ValueError('Case still needs evidence or a diagnosed repair')
    if case.get('dependency_repair_reason') or case.get('expected_label_status') not in ('accepted','judgment_sweep','evidence_accepted'):
        raise ValueError('Current case still requires repair or label resolution')
    attempt=Path(case['execution']);record=load(attempt/'expected_label.json')
    definition=load(case['definition_file']);trace_path=attempt/'traffic_spec/trace.json'
    if record['trace_sha256']!=sha(trace_path) or record['definition_sha256']!=sha(Path(case['definition_file'])):
        raise ValueError('Expected label is bound to stale evidence or targets')
    source=rows(attempt/'trace.jsonl');mapping=rows(attempt/'video_frames.jsonl')
    if not source or len(source)!=len(mapping) or len(source)!=case['frames']:
        raise ValueError('Incomplete source/trace/video frame membership')
    if any(m['video_frame']!=i or m['carla_frame']!=r['frame'] or abs(m['time_s']-r['time_s'])>1e-6 for i,(r,m) in enumerate(zip(source,mapping))):
        raise ValueError('Source video/trace frame correspondence is invalid')
    scope=load(attempt/'trace_scope_audit.json')
    identity={'trace_sha256':record['trace_sha256'],'source_sha256':sha(attempt/'trace.jsonl'),
              'frame_map_sha256':sha(attempt/'video_frames.jsonl'),
              'adapter_report_sha256':sha(attempt/'traffic_spec/adapter_report.json')}
    if not scope.get('passed') or any(scope.get(k)!=v for k,v in identity.items()) or scope['frames']!=len(source):
        raise ValueError('Full-trace capture/decoder receipt is missing or stale')
    adapter=load(attempt/'traffic_spec/adapter_report.json')
    if adapter.get('required_measurements_complete') is False:
        raise ValueError('Required captured observations are incomplete')
    if not adapter.get('decoder_validation',{}).get('passed') or adapter['frames']!=len(source):
        raise ValueError('Current full trace has no successful Lean decoder receipt')
    context=record['scene_assumptions']
    if first_scene(trace_path).get('assumptions',[])!=assumptions(context):
        raise ValueError('Declared label assumptions disagree with delivered Core context')
    review=deepcopy(load(attempt/'measured_review.json'))
    if record['target_law_id']=='NRS-484B-600-1c' and record.get('format')!='production-verdict-v1':
        from control_evidence import posted_sign_evidence
        speed=review['speed_evaluation']
        speed['physical_control_evidence']=posted_sign_evidence(attempt,source,scope,speed['limit']['m/s'])
    if record.get('format')=='production-verdict-v1':
        from production_verdicts import expectation as measured_expectation,validate
        recomputed=validate(measured_expectation(definition,attempt,review,context))
        if recomputed['evidence_status']!='accepted' or recomputed['expected_label']!=record['expected_label'] or record['expected_label']!=case['expected_label']:
            raise ValueError('Production evidence/verdict is missing, unintended, or stale')
        for key in ('inconclusive_reasons','reference_check','evaluation_status'):
            if recomputed.get(key)!=record.get(key):raise ValueError('Stale production verdict provenance: '+key)
    else:
        recomputed=expectation(definition,attempt,review,context)
        if recomputed['judgment_sweep']:
            if record['expected_label'] is not None or case['expected_label'] is not None:
                raise ValueError('Actual judgment sweep must remain unlabeled')
        elif not recomputed['intention_matched'] or recomputed['missing_evidence'] or recomputed['expected_label']!=record['expected_label'] or record['expected_label']!=case['expected_label']:
            raise ValueError('Deterministic recorded outcome is missing, unintended, or stale; repair the cause')
    window=[source[0]['time_s'],source[-1]['time_s']]
    if record['full_recording_window_s']!=window:
        raise ValueError('Label window does not cover the entire delivered trace')
    video,digest,receipt=full_video(case,attempt,len(source),window)
    result_path=attempt/'result.json'
    result=load(result_path) if result_path.exists() else {}
    completion=result.get('completion',{})
    if completion:
        from batch_pipeline.completion import verify
        verify(attempt,completion['binding'])
        binding=completion['binding']
        identity={'cell_id':cell['cell_id'],'actor':cell.get('actor','motor_vehicle_driver'),'case_id':case['case_id']}
        if any(binding.get(k)!=v for k,v in identity.items()):
            raise ValueError('Completion identity does not match the delivered case')
        from batch_pipeline.store import digest as specification_digest
        if binding.get('specification_hash')!=specification_digest(definition):
            raise ValueError('Delivered definition differs from the frozen executed specification')
    provenance={'attempt_id':attempt.name, 'source_run_id':case.get('source_run_id') or completion.get('binding',{}).get('run_id') or cell.get('run_id'),
                'definition_sha256':record['definition_sha256'],
                'completion_binding':{k:v for k,v in completion.get('binding',{}).items() if k!='runtime_dependency_hashes'},
                'runtime_dependency_version':hashlib.sha256(json.dumps(completion.get('binding',{}).get('runtime_dependency_hashes',{}),sort_keys=True).encode()).hexdigest(),
                'result_sha256':sha(result_path) if result_path.exists() else None}
    if result.get('input_revision'):
        provenance['input_revision'] = result['input_revision']
    if result.get('offline_reporting_projection'):
        projection_path = attempt/result['offline_reporting_projection']
        provenance['reporting_projection'] = {'receipt':str(projection_path), 'sha256':sha(projection_path)}
    return {'cell_id':cell['cell_id'],'actor':cell.get('actor','motor_vehicle_driver'),'case_id':case['case_id'],'law_id':record['target_law_id'],
            'attempt_id':attempt.name,'provenance':provenance,
            'expected_label':record['expected_label'],'judgment_sweep':record['judgment_sweep'],
            'video_source':video,'video_sha256':digest,'trace_source':trace_path,
            'trace_sha256':record['trace_sha256'],'frames':len(source),'trace_window_s':window,
            'frame_rate':receipt['ffprobe']['streams'][0].get('avg_frame_rate','20/1'),
            'definition':definition,'scene_assumptions':context,'recomputed_expectation':recomputed}


def inspect_delivery(output, *, partial=False):
    index=load(Path(output)/'delivery_index.json');accepted=[];errors=[]
    identities=[(c['cell_id'],c.get('actor','motor_vehicle_driver')) for c in index['cells']]
    actual={c['cell_id'] for c in index['cells']}
    if len(set(identities))!=len(identities):
        raise ValueError('Duplicate cell/actor membership')
    if set(index.get('expected_cells',actual))!=actual:
        errors.append('Selected cell membership is incomplete')
    expected_actors={(c['cell_id'],c['actor']) for c in index.get('expected_cell_actors',[])}
    if expected_actors-set(identities):
        errors.append('Selected cell/actor membership is incomplete')
    ids=set();states=[]
    for cell in index['cells']:
        actor=cell.get('actor','motor_vehicle_driver')
        if cell.get('planned_cases') is not None and cell['planned_cases']!=len(cell['cases']):
            errors.append(cell['cell_id']+': planned case membership is incomplete')
        for case in cell['cases']:
            key=(cell['cell_id'],actor,case['case_id'])
            if key in ids:
                raise ValueError('Duplicate case: '+str(key))
            ids.add(key)
            state={'cell_id':key[0],'actor':actor,'case_id':key[2],
                   'group_id':case.get('paired_probe_id') or case.get('sweep_id') or case.get('group_id'),
                   'status':case.get('status','pending')}
            try:
                record=inspect_case(cell,case)
                record.setdefault('actor',actor)
                accepted.append(record);state['status']='accepted'
                definition=record['definition']
                state['group_id']=definition.get('paired_probe_id') or definition.get('sweep_id') or record['law_id']
            except Exception as exc:
                state['reason']=str(exc)
                if state['status'] not in ('pending','unselected','running'):
                    state['status']='needs_repair'
                errors.append(str(key)+': '+str(exc))
            states.append(state)
    if not ids:errors.append('No accepted cases to publish')
    if errors and not partial:
        raise ValueError('Delivery acceptance failed:\n'+'\n'.join(errors))
    index=dict(index,case_states=states,publication_issues=errors)
    return index,accepted
