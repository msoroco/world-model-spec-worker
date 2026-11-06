"""Draft saved-source measurements; no physical or legal acceptance verdict."""
import hashlib
import json
from pathlib import Path

from measure_after_turn import measure


def _required(folder, name):
    path=Path(folder)/name
    if not path.is_file(): raise ValueError('Missing required source: '+name)
    return path


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def activation_context(folder):
    geometry=json.loads(_required(folder,'road_geometry.json').read_text())
    return {'authored_center_lane_bounds_m':geometry['center_turn_lane_native_xy_bounds_m'],
            'native_center_lane_design_verified':geometry.get('native_center_lane_design_verified') is True,
            'authored_map_sha256':geometry['authored_map_sha256']}


def distance_after_turn(folder):
    samples=_required(folder,'native_samples.jsonl')
    geometry=_required(folder,'road_geometry.json')
    return measure(samples,geometry)


def turn_merge_scope(folder):
    measured=distance_after_turn(folder)
    return {'turn_completion_frame_bracket':measured['turn_completion_frame_bracket'],
            'merge_onset_frame_bracket':measured['merge_onset_frame_bracket'],
            'full_merge_native_frame':measured['full_merge_native_frame']}


def analysis_report(folder,contract):
    folder=Path(folder)
    methods={'activation_context':activation_context,
             'distance_after_turn':distance_after_turn,
             'turn_merge_scope':turn_merge_scope}
    values={}
    for row in contract['requirements']:
        inputs={name:_sha(_required(folder,name)) for name in row['inputs']}
        values[row['output_key']]={'method':row['method'],
                                   'value':methods[row['method']](folder),
                                   'sources':inputs}
    return {'format':'draft-saved-analysis-v1','case_id':contract['case_id'],
            'draft_only':True,'selected':False,'measurements':values}
