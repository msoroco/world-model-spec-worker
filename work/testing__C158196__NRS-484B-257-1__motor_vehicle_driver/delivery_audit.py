"""Independent original-source audit for one exact C158196 signal case.

The diagnostic flag proves software joins with a synthetic fixture only. Without
it, full Native provenance, original-camera review and physical completion are
required. Neither path decides legal control, right of way or hazard.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / 'runtime/scenario_pipeline'))
from worker_exchange.media import audit as audit_video, check_four_view_sources

PREFIX = ROOT.name + '__'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHANNELS = ('operative_signal_control', 'signal_state', 'ego_crossing_body',
            'through_highway_sight_clear', 'ego_distance_to_junction_m',
            'through_vehicle_position', 'through_vehicle_speed', 'ego_approach_speed')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing original source: ' + path.name)
    result = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not result:
        raise ValueError('Empty original source: ' + path.name)
    return result


def audit(attempt, case_id, *, diagnostic_fixture=False):
    attempt = Path(attempt)
    if not case_id.startswith(PREFIX):
        raise ValueError('Wrong exact C158196 case')
    config = json.loads((attempt/'config.json').read_text())
    if (config.get('selected_case_id') != case_id or config.get('cell_id') != 'C158196'
            or config.get('law_id') != 'NRS-484B-257-1' or config.get('rate_hz') != 20
            or config.get('duration_s') != 30):
        raise ValueError('Exact case or capture profile changed')
    result_path = attempt/'result.json'
    result = json.loads(result_path.read_text())
    if result.get('case_id') != case_id:
        raise ValueError('Sealed result case differs')
    if not diagnostic_fixture:
        if result.get('provenance_kind') != 'native' or result.get('diagnostic_fixture') is True:
            raise ValueError('Native source provenance required')
        maneuver = result.get('physical_checks', {}).get('maneuver', {})
        if result.get('maneuver_completed') is not True or maneuver.get('status') != 'met':
            raise ValueError('Original physical completion proof required')
    elif result.get('provenance_kind') != 'synthetic_fixture':
        raise ValueError('Diagnostic flag requires a declared synthetic fixture')
    frame_map = rows(attempt/'video_frames.jsonl')
    expected_frames = 3 if diagnostic_fixture else config['rate_hz']*config['duration_s']
    if len(frame_map) != expected_frames:
        raise ValueError('Full original frame map required')
    histories = {name: rows(attempt/name) for name in
                 ('signal_history.jsonl', 'interaction_history.jsonl', 'trace.jsonl',
                  'capture/evidence.jsonl')}
    if any(len(values) != expected_frames for values in histories.values()):
        raise ValueError('Original source histories differ in length')
    channels = {name: rows(attempt/'channels'/(name+'.jsonl')) for name in CHANNELS}
    if any(len(values) != expected_frames for values in channels.values()):
        raise ValueError('Recorded channel history differs in length')
    previous = None
    for index, frame in enumerate(frame_map):
        fid, time = frame.get('carla_frame'), frame.get('time_s')
        if (frame.get('video_frame') != index or type(fid) is not int or
                type(time) not in (int, float) or not math.isfinite(time) or
                frame.get('camera_frames') != {name: fid for name in CAMERAS}):
            raise ValueError('Original four-camera frame join invalid')
        if previous and (fid != previous[0]+1 or abs(time-previous[1]-.05) > 1e-3):
            raise ValueError('Original 20 Hz frame/time sequence invalid')
        previous = (fid,time)
        signal, interaction, trace, event = (histories[name][index] for name in histories)
        if (signal.get('frame') != fid or interaction.get('frame') != fid or
                trace.get('frame') != fid or event.get('original_frame') != fid or
                abs(signal.get('time_s', -math.inf)-time) > 1e-6 or
                abs(interaction.get('time_s', -math.inf)-time) > 1e-6):
            raise ValueError('Original source frame/time join invalid')
        ray = interaction.get('through_sight', {})
        if (ray.get('method') != 'native_collision_ray_to_through_actor_center' or
                ray.get('sampled_only') is not True or
                type(ray.get('clear')) is not bool or
                not isinstance(ray.get('blockers'), list) or
                ray['clear'] != (len(ray['blockers']) == 0)):
            raise ValueError('Original through-highway sight ray invalid')
        values = {name: channel[index] for name,channel in channels.items()}
        if any(row.get('original_frame') != fid or abs(row.get('time_s', -math.inf)-time) > 1e-6
               for row in values.values()):
            raise ValueError('Recorded channel frame/time join invalid')
        if (values['through_highway_sight_clear']['value'] != int(ray['clear']) or
                values['signal_state']['value'] != signal['signal_state'] or
                values['ego_approach_speed']['value'] != signal['ego_speed_mps'] or
                values['through_vehicle_speed']['value']['speed_mps'] != interaction['through']['speed_mps']):
            raise ValueError('Recorded channel differs from original source')
    source_hashes = result.get('source_evidence_hashes', {})
    for name in ('config.json','road.xodr','trace.jsonl','capture/evidence.jsonl',
                 'signal_context.json','signal_history.jsonl','interaction_history.jsonl',
                 'control_context.json','video_frames.jsonl','signal_head_review.json',
                 *(camera+'.mkv' for camera in CAMERAS)):
        if source_hashes.get(name) != sha(attempt/name):
            raise ValueError('Sealed original source hash differs: '+name)
    review = json.loads((attempt/'signal_head_review.json').read_text())
    if review.get('case_id') != case_id or review.get('reviewed_carla_frames') != [
            frame['carla_frame'] for frame in frame_map]:
        raise ValueError('Original camera review frame set differs')
    if not diagnostic_fixture and (not review.get('reviewer') or
                                   str(review['reviewer']).startswith(('diagnostic-', 'synthetic-'))):
        raise ValueError('Independent original-camera pixel reviewer required')
    sources = {name: attempt/(name+'.mkv') for name in CAMERAS}
    check_four_view_sources(sources)
    decoded = {}
    for name, path in sources.items():
        if review.get('camera_sha256', {}).get(name) != sha(path):
            raise ValueError('Original camera review hash differs: '+name)
        decoded[name] = audit_video(path, expected_frames,
                                    mapping_sha256=sha(attempt/'video_frames.jsonl'))['video_sha256']
    return {'format':'worker-c158196-independent-source-audit','case_id':case_id,
            'original_frames':expected_frames,'frame_map_sha256':sha(attempt/'video_frames.jsonl'),
            'interaction_sha256':sha(attempt/'interaction_history.jsonl'),
            'sealed_result_sha256':sha(result_path),'decoded_cameras':decoded,
            'software_audit_passed':True,'diagnostic_fixture':diagnostic_fixture,
            'physical_acceptance_claimed':False,'legal_conclusion':'unresolved'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt,args.case,
                           diagnostic_fixture=args.diagnostic_fixture),indent=2))
