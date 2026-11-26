"""Build two exact selected source-gated constructions from reviewed drafts."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
ASSIGNMENT=ROOT.name
CASES=(('condition_a',-1),('condition_b',-2))
CAMERAS=[{'name':name,'width':width,'height':height,
          'pose_strategy':'fixed original Native world view of actor and signal',
          'fov_deg':85} for name,width,height in (
    ('overview',1920,1080),('approach',1280,720),
    ('reference_corner',1280,720),('driver_reference',1280,720))]
CHANNELS=[{'name':name,'unit':'structured','method':'original Native 600-frame signal, map and actor source join',
           'sampling_rate_hz':20,'time_window':'30 s / 600 original frames',
           'reference_frame':'original Native map and frame',
           'uncertainty':'official authority and actual pixels pending independent local review'}
          for name in ('dev.lane_control_signal','dev.governs','st.lane','rel.occupies','dev.position')]
RECORDING={'channels':CHANNELS,'context_inputs':[],
           'limitations':['source-shaped CPU fixtures do not prove real arrow pixels or official authority']}
SOURCE_FILES=('selected_runner.py','capture.py','draft_runner.py','signal_source.py',
              'lane_arrow_meter.py','finalize.py','road.xodr')


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def build():
    constructions=[]
    dispositions=json.loads((ROOT/'case-plan.json').read_text())['requirement_dispositions']
    for tag,lane in CASES:
        case_id=ASSIGNMENT+'__selected_378a10ff__'+tag
        cfg={'case_id':case_id,'selected_case_id':case_id,
             'supported_case_ids':[ASSIGNMENT+'__selected_378a10ff__'+t for t,_ in CASES],
             'law_id':'NRS-484B-307-12a','cell_id':'C230247',
             'actor':'motor_vehicle_driver','rate_hz':20,'duration_s':30,
             'cameras':CAMERAS,'required_atoms':[],'source_packets':[],
             'case':{'case_id':case_id,'target_lane_id':lane},
             'recording_description':RECORDING,
             'physical_completion':{'criterion':'travel_progress',
                'motion_source':'trace.jsonl','position_key':'position_m',
                'minimum_progress_m':40.0,'minimum_samples':600,
                'engineering_tolerances_not_legal':True}}
        files=[{'path':'runner.py','content':(HERE/'selected_runner.py').read_text()},
               {'path':'config.json','content':json.dumps(cfg,indent=2)+'\n'},
               {'path':'tests/test_selected.py','content':(HERE/'selected_test.py').read_text()}]
        for name in SOURCE_FILES:
            if name=='selected_runner.py': continue
            files.append({'path':name,'content':(HERE/name).read_text()})
        construction={'case_id':case_id,'law_id':cfg['law_id'],
            'cell_id':cfg['cell_id'],'actor':cfg['actor'],'entrypoint':'runner.py',
            'files':files,'recording_description':RECORDING,
            'status':'selected_cpu_construction_partial',
            'measurement_plan':'Original Native signal inventory, live arrow state, actor body lane and four camera frames; official authority and pixels require independent review.',
            'static_checks':['two authored 3.5 m driving lanes','overhead dynamic signal id 100 valid for lane -1',
                             '30-second route remains within road and traverses signal station',
                             'four synchronized cameras and exact Native arrow actor required'],
            'termination_rules':['600 original frames at 20 Hz','reject missing signal/camera/source and restore owned world'],
            'mechanisms':['two-lane OpenDRIVE road with overhead signal proposal',
                          'source-gated Native lane-control actor readback',
                          'moving motor vehicle actor and saved-only source measurement'],
            'supported_case_ids':cfg['supported_case_ids']}
        dest=ROOT if tag=='condition_a' else ROOT/'cases'/tag
        write(dest/'config.json',cfg)
        write(dest/'construction.json',construction)
        measurement_rows=[]
        for index,key,method,value_type,inputs in (
            (0,'overhead_lane_mapping','overhead_lane_mapping','object',
             ['native-signal-rows.jsonl','native-map-readback.xodr']),
            (1,'facing_downward_arrow_frames','facing_downward_arrow','number',
             ['native-signal-rows.jsonl','video_frames.jsonl']),
            (2,'proposed_lane_witness','proposed_lane_witness','object',
             ['native-signal-rows.jsonl','trace.jsonl','capture/evidence.jsonl'])):
            disposition=dispositions[index]
            measurement_rows.append({'disposition_index':index,
                'requirement':disposition['requirement'],'source':disposition['source'],
                'output_key':key,'method':method,'value_type':value_type,
                'kind':'measured','inputs':inputs})
        write(dest/'measurement.json',{'format':'worker-measurement-contract',
            'requirements':measurement_rows,
            'negative':{'remove':['native-signal-rows.jsonl'],
                        'error_contains':'Missing required source: native-signal-rows.jsonl'}})
        if tag=='condition_a':
            (ROOT/'runner.py').write_text((HERE/'selected_runner.py').read_text())
            for name in SOURCE_FILES:
                if name!='selected_runner.py':
                    (ROOT/name).write_text((HERE/name).read_text())
        entry={'case_id':case_id,
            'construction':str((dest/'construction.json').relative_to(ROOT)),
            'construction_sha256':hashlib.sha256((dest/'construction.json').read_bytes()).hexdigest(),
            'kind':'delivery','id':'primary',
            'measurement_contract':str((dest/'measurement.json').relative_to(ROOT)),
            'measurement_procedure':{'entrypoint':'finalize.py',
                'output_schema':'c230247-lane-arrow-saved-analysis-v1'},
            'fixture_recipe':f'work/{ASSIGNMENT}/diagnostic-{tag}-recipe.json',
            'acquisition':{channel['name']:{'entrypoint':'capture.py',
                'method':'original Native post-tick actor, lane signal and four camera join',
                'evidence':'Source-gated prospective capture; physical proof pending'}
                for channel in CHANNELS},
            'candidate_risk':{'status':'none',
                'reason':'No supported alternate arrow asset; a generic light would change the statutory condition.'},
            'candidates':[]}
        offline_log=ROOT/f'selected-{tag}-offline.log'
        if offline_log.is_file() and json.loads(offline_log.read_text()).get('offline_passed') is True:
            entry['offline']={'command':f'TMPDIR=$PWD/.runtime-work PYTHONDONTWRITEBYTECODE=1 SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c230247 .venv-cpu/bin/python -B runtime.py offline --manifest work/{ASSIGNMENT}/execution-manifest.json --case {case_id} --output .runtime-work/c230247-selected-{tag}-20261126e',
                'exit_code':0,'construction_sha256':entry['construction_sha256'],
                'log':offline_log.name,
                'log_sha256':hashlib.sha256(offline_log.read_bytes()).hexdigest()}
        constructions.append(entry)
    manifest={'format':'worker-execution-manifest','assignment_id':ASSIGNMENT,
        'runtime_manifest_sha256':hashlib.sha256((HERE.parents[2]/'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest(),
        'status':'selected_cpu_construction_partial','cases':constructions}
    write(ROOT/'execution-manifest.json',manifest)
    print(json.dumps({'cases':constructions},sort_keys=True))


if __name__=='__main__':
    build()
