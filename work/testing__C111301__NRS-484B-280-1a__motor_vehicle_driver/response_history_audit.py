"""Source-bound engineering response bracket for wheelchair encounter histories.

The bracket tests the authored controller on measured Native input samples. It
does not turn the engineering response time into a legal due-care cutoff.
"""
import hashlib
import json
from pathlib import Path

from runner import control, encounter


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def samples(attempt,receipt,expected_suffix):
    attempt=Path(attempt)
    if receipt.get('format')!='worker-delivery-audit' or receipt.get('passed') is not True or \
       not receipt.get('case_id','').endswith(expected_suffix) or \
       receipt.get('controller_audit',{}).get('passed') is not True:
        raise ValueError('source-audited exact delivery receipt missing')
    name='encounter-history.jsonl';context_name='intersection-context.json'
    acquisition=read(attempt/'acquisition.json');seal=read(attempt/'capture-seal.json')
    for source in (name,context_name):
        digest=sha(attempt/source)
        if acquisition.get(source,{}).get('kind')!='original_native' or \
           acquisition[source].get('sha256')!=digest or seal.get('sources',{}).get(source)!=digest or \
           receipt.get('measurement',{}).get('sources',{}).get(source)!=digest:
            raise ValueError('response original source or receipt stale: '+source)
    if receipt['controller_audit'].get('source_sha256')!=sha(attempt/name):
        raise ValueError('controller audit source differs from response history')
    context=read(attempt/context_name)
    scene={'engineering_ttc_brake_s':context['engineering_ttc_brake_s'],
           'ego_lane_bounds_y_m':context['ego_lane_bounds_y_m']}
    rows=[json.loads(line) for line in (attempt/name).read_text().splitlines() if line.strip()]
    if len(rows)!=receipt.get('frame_count'):
        raise ValueError('response history frame count differs from delivery receipt')
    measured=[]
    for row in rows:
        values=row['control_inputs']
        observation=encounter(scene,values['ego_body_vertices_m'],values['person'],
                              values['manual_wheelchair'],values['ego_speed_mps'],
                              values['pedestrian_speed_mps'])
        command=control(scene,observation)
        if row.get('control_command')!=command:
            raise ValueError('response command differs from original inputs')
        measured.append({'frame':row['frame'],'time_to_path_s':observation['time_to_path_s'],
                         'approaching_lane':observation['pedestrian_in_or_approaching_lane'],
                         'brake':command['brake']})
    return scene,measured


def bracket(crossing,clear,threshold):
    above=[row for row in crossing if row['approaching_lane'] and
           row['time_to_path_s'] is not None and row['time_to_path_s']>threshold and row['brake']==0]
    below=[row for row in crossing if row['approaching_lane'] and
           row['time_to_path_s'] is not None and row['time_to_path_s']<threshold and row['brake']==1]
    clear_unbraked=[row for row in clear if not row['approaching_lane'] and row['brake']==0]
    if not above or not below or not clear_unbraked:
        raise ValueError('original response history lacks above/below and clear-path bracket')
    return {'above_engineering_boundary_frames':[row['frame'] for row in above],
            'below_engineering_boundary_frames':[row['frame'] for row in below],
            'clear_path_unbraked_frames':[row['frame'] for row in clear_unbraked],
            'observed_crossing_time_to_path_range_s':[
                min(row['time_to_path_s'] for row in crossing if row['time_to_path_s'] is not None),
                max(row['time_to_path_s'] for row in crossing if row['time_to_path_s'] is not None)]}


def audit(clear_attempt,crossing_attempt,clear_receipt,crossing_receipt):
    from comparison_audit import audit as compare
    compared=compare(clear_receipt,crossing_receipt)
    clear_scene,clear=samples(clear_attempt,clear_receipt,'__wheelchair_clear_path')
    crossing_scene,crossing=samples(crossing_attempt,crossing_receipt,'__wheelchair_crossing')
    if clear_scene!=crossing_scene:
        raise ValueError('engineering response policy differs across exact cases')
    result=bracket(crossing,clear,crossing_scene['engineering_ttc_brake_s'])
    return {'format':'c111301-original-response-bracket-v1','passed':True,
            'comparison_id':compared['comparison_id'],
            'engineering_ttc_brake_s':crossing_scene['engineering_ttc_brake_s'],
            'source_sha256':{'clear':sha(Path(clear_attempt)/'encounter-history.jsonl'),
                             'crossing':sha(Path(crossing_attempt)/'encounter-history.jsonl')},
            **result,'legal_due_care_verdict':None}
