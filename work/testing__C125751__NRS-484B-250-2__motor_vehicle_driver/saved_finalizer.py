"""Finalize original crossing measurements after all source/video decoding."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from saved_delivery import audit
from native_capture import _source_path


def build_result(attempt, survey_path, video_relative):
    attempt = Path(attempt).resolve()
    packet = audit(attempt, survey_path, decode_media=True)
    video = _source_path(attempt, video_relative)
    from scenario_pipeline.worker_exchange.media import audit as decode_video
    decoded = decode_video(video, 900, mapping_sha256=packet['frame_map_sha256'])
    if decoded.get('frames') != 900 or not decoded.get('passed'):
        raise ValueError('full original primary video decode required')
    observation = packet['entry_measurement']
    case_id = packet['case_id']
    plan = json.loads((Path(__file__).resolve().parent/'case-plan.json').read_text())
    selected = [row for row in plan['cases'] if row['case_id'] == case_id]
    if len(selected) != 1:
        raise ValueError('exact crossing case plan missing')
    selected = selected[0]
    measured_difference = observation['ego_minus_other_upper_entry_s']
    requested_difference = selected['requested_entry_difference_s']
    measured_response = observation['observed_ego_response']
    targets = [
        {'target':'ego_minus_other_entry_s', 'requested':requested_difference,
         'measured':measured_difference, 'method':'source-bound original upper entry timestamps',
         'tolerance':.05, 'matched':abs(measured_difference-requested_difference)<=.05,
         'physical_cause_confirmed':False, 'cause_evidence':{'status':'physical_review_pending'}},
        {'target':'ego_response', 'requested':selected['requested_ego_response'],
         'measured':measured_response, 'method':'original ego entry versus other full-body exit',
         'tolerance':0, 'matched':measured_response == selected['requested_ego_response'],
         'physical_cause_confirmed':False, 'cause_evidence':{'status':'physical_review_pending'}}]
    manifest = json.loads((attempt/'source-manifest.json').read_text())
    return {'case_id':case_id, 'measured_values':observation,
            'target_checks':targets, 'setup_confirmed':False,
            'behavior_attempted':False, 'maneuver_completed':False,
            'termination_reason':'Saved measurement complete; physical and legal review pending',
            'physical_failure_flags':{'physical_review_pending':True},
            'trace_reference':manifest['trace']['path'],
            'video_references':[video_relative],
            'video_frame_map_reference':manifest['frame_map']['path'],
            'recording_description':'C125751 median-opening crossing entry timing',
            'recording_evidence':[{'name':'original_trace','reference':manifest['trace']['path']},
                                  {'name':'original_camera_index','reference':manifest['camera_index']['path']},
                                  {'name':'original_primary_video','reference':video_relative}],
            'realized_observables':observation,
            'source_sha256':{'source_manifest':hashlib.sha256((attempt/'source-manifest.json').read_bytes()).hexdigest(),
                             'primary_video':decoded['video_sha256'],
                             'frame_map':packet['frame_map_sha256']},
            'legal_judgment':'unresolved', 'physical_acceptance':'not_assessed'}


def finalize(attempt, survey_path, video_relative):
    from scenario_pipeline.worker_exchange.native_output import write_result
    return write_result(attempt, build_result(attempt,survey_path,video_relative))
