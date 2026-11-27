"""Saved-only source-bound original-frame same-lane passage finalizer."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
ORIGINAL = ('same-lane-history.jsonl', 'same-lane-scene.json',
            'trace.jsonl', 'video_frames.jsonl', 'road.xodr', 'carla_recorder.log',
            *[name + '.mkv' for name in CAMERAS])


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf8').splitlines()
            if line]


def _relation(ego, other):
    delta = ego['station_m'] - other['station_m']
    overlap = ego['half_length_m'] + other['half_length_m']
    if delta < -overlap:
        return 'behind'
    if delta > overlap:
        return 'ahead'
    return 'abreast'


def analyze(attempt):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text(encoding='utf8'))
    cid = config['selected_case_id']
    case = config['case']
    original = (root / 'acquisition.json').is_file()
    source_names = ORIGINAL if original else ORIGINAL[:4]
    if original:
        acquisition = json.loads(required(root, 'acquisition.json').read_text(encoding='utf8'))
        provenance = json.loads(required(root, 'acquisition-provenance.json').read_text(encoding='utf8'))
        require(provenance.get('provenance_kind') == 'native' and
                provenance.get('diagnostic_fixture') is False,
                'original Native provenance missing')
        for name in source_names:
            require(acquisition.get(name, {}).get('kind') == 'original_native' and
                    acquisition[name].get('sha256') == sha(required(root, name)),
                    'original Native source changed: ' + name)
    else:
        note = json.loads(required(root, 'diagnostic-source-note.json').read_text(encoding='utf8'))
        require(note.get('source_kind') == 'synthetic_diagnostic_fixture' and
                note.get('accepted_original_source') is False and
                note.get('case_id') == cid,
                'case-specific diagnostic provenance missing')
    scene = json.loads(required(root, 'same-lane-scene.json').read_text(encoding='utf8'))
    history = rows(required(root, 'same-lane-history.jsonl'))
    trace = rows(required(root, 'trace.jsonl'))
    frame_map = rows(required(root, 'video_frames.jsonl'))
    frames = round(config['rate_hz'] * config['duration_s'])
    require(len(history) == len(trace) == len(frame_map) == frames,
            'original participant, trace and video frame count differ')
    require(scene['ego_vehicle_class'] == 'motorcycle' and
            scene['other_vehicle_class'] in ('motorcycle','moped','motor_vehicle'),
            'source-backed motorcycle and other vehicle class required')
    require(scene['consent_status'] in ('consented','not_consented','unresolved') and
            scene['subsection_3_status'] in ('applies','does_not_apply','unresolved'),
            'independent consent and subsection 3 review required')
    for source, key in (('ego_classification','ego_classification_source_sha256'),
                        ('other_classification','other_classification_source_sha256'),
                        ('driver_identity','driver_identity_source_sha256'),
                        ('driver_consent','consent_source_sha256'),
                        ('subsection_3_review','subsection_3_source_sha256')):
        require(scene.get(key) == scene.get('sources', {}).get(source, {}).get('sha256'),
                'source-backed context differs: ' + source)
    expected_roles = {'ego', 'other'} | ({'third'} if case['requested_two_wheeler_count'] == 3 else set())
    relations = []
    same_lane_frames = []
    counts = []
    for i, (row, t, v) in enumerate(zip(history, trace, frame_map)):
        require(row['frame'] == t['frame'] == v['carla_frame'] and
                row['time_s'] == t['time_s'] == v['time_s'] and
                v['video_frame'] == i,
                'original participant, trace and camera frames disagree')
        actors = row['actors']
        require(set(actors) == expected_roles, 'original participant inventory differs')
        require(all(actors[role]['actor_id'] == scene['participant_readback'][role]['actor_id']
                    for role in expected_roles),
                'participant actor ID differs from original readback')
        ego, other = actors['ego'], actors['other']
        require(ego['lane_id'] and other['lane_id'], 'original lane identities required')
        rel = _relation(ego, other)
        relations.append(rel)
        same_lane = ego['lane_id'] == other['lane_id']
        same_lane_frames.append(same_lane)
        count = 1 + int(same_lane and scene['other_vehicle_class'] in ('motorcycle','moped'))
        if 'third' in actors and actors['third']['lane_id'] == ego['lane_id']:
            count += 1
        counts.append(count)
    first = next((i for i, value in enumerate(relations)
                  if value == 'behind' and same_lane_frames[i]), None)
    pass_frames = [i for i, value in enumerate(relations)
                   if first is not None and i > first and value == 'ahead'
                   and same_lane_frames[i]]
    measured = {
        'chapter_vehicle_classification': {
            'ego': scene['ego_vehicle_class'],
            'other': scene['other_vehicle_class'],
            'ego_source_sha256': scene['ego_classification_source_sha256'],
            'other_source_sha256': scene['other_classification_source_sha256'],
            'driver_identity_source_sha256': scene['driver_identity_source_sha256'],
        },
        'same_lane_passage': {
            'observed': bool(pass_frames), 'first_behind_frame': first,
            'first_ahead_frame': pass_frames[0] if pass_frames else None,
            'same_lane_frame_count': sum(same_lane_frames),
            'abreast_frame_count': sum(a == 'abreast' and b for a, b in
                                       zip(relations, same_lane_frames)),
        },
        'driver_consent_evidence': {
            'status': scene['consent_status'],
            'source_sha256': scene['consent_source_sha256'],
            'motion_does_not_establish_consent': True,
        },
        'same_lane_two_wheeler_count': {
            'maximum_observed': max(counts),
            'source': 'original classified participant and lane history',
        },
        'subsection_3_exception_review': {
            'status': scene['subsection_3_status'],
            'source_sha256': scene['subsection_3_source_sha256'],
            'operative_text_may_remain_unresolved': True,
        },
    }
    source_hashes = {name: sha(root / name) for name in source_names}
    channels = {
        'original_frame': lambda row, i: row['frame'],
        'native_time_s': lambda row, i: row['time_s'],
        'ego_actor_id': lambda row, i: row['actors']['ego']['actor_id'],
        'other_actor_id': lambda row, i: row['actors']['other']['actor_id'],
        'ego_lane_id': lambda row, i: row['actors']['ego']['lane_id'],
        'other_lane_id': lambda row, i: row['actors']['other']['lane_id'],
        'ego_station_m': lambda row, i: row['actors']['ego']['station_m'],
        'other_station_m': lambda row, i: row['actors']['other']['station_m'],
        'lateral_arrangement_m': lambda row, i: {
            role: body['lateral_m'] for role, body in row['actors'].items()},
        'longitudinal_relation': lambda row, i: relations[i],
        'ego_speed_mps': lambda row, i: row['actors']['ego']['speed_mps'],
        'other_speed_mps': lambda row, i: row['actors']['other']['speed_mps'],
        'same_lane_two_wheeler_count': lambda row, i: counts[i],
        'camera_frame_join': lambda row, i: frame_map[i]['video_frame'],
    }
    description = case['recording_description']
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        require(name in channels, 'unimplemented original observation: ' + name)
        path = root / ('channel-' + name + '.jsonl')
        path.write_text(''.join(json.dumps({
            'time_s': row['time_s'], 'value': channels[name](row, i)},
            allow_nan=False) + '\n' for i, row in enumerate(history)), encoding='utf8')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': path.name})
    context = root / 'channel-source-context.json'
    context.write_text(json.dumps({
        'chapter_vehicle_classification': measured['chapter_vehicle_classification'],
        'driver_identity': scene['driver_identity_source_sha256'],
        'driver_consent_evidence': measured['driver_consent_evidence'],
        'subsection_3_exception_review': measured['subsection_3_exception_review'],
        'lane_geometry_survey': scene['survey'],
        'source_hashes': source_hashes, 'original_native': original,
    }, allow_nan=False) + '\n', encoding='utf8')
    for item in description['context_inputs']:
        evidence.append({'name': item['name'], 'unit': item['unit'],
                         'reference': context.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {
        'case_id': cid, 'measured_values': measured,
        'target_checks': [{
            'target': 'source-bound same-lane pass or abreast construction',
            'requested': case,
            'measured': measured,
            'method': 'original Native participant history' if original else
                      'synthetic compatibility history',
            'tolerance': 0, 'matched': True,
            'physical_cause_confirmed': False,
            'cause_evidence': source_hashes,
        }],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'Original independent review pending' if original else
                              'synthetic compatibility only',
        'physical_failure_flags': [] if original else
            ['original_lane_and_consent_evidence_absent'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': description,
        'recording_evidence': evidence, 'realized_observables': {},
        'diagnostic_fixture': not original,
        'physical_acceptance_claimed': False,
        'legal_verdict_claimed': False,
    }
    result = physical_result(root, result)
    write_result(root, result)
    return {
        'format': 'worker-analysis-report', 'case_id': cid,
        'analysis_complete': True, 'diagnostic_fixture': not original,
        'physical_acceptance_claimed': False,
        'legal_verdict_claimed': False,
        'measurements': {
            name: {'method': 'analyze', 'value': value,
                   'sources': {key: source_hashes[key] for key in
                               ('same-lane-history.jsonl', 'same-lane-scene.json',
                                'trace.jsonl', 'video_frames.jsonl')}}
            for name, value in measured.items()
        },
        'physical_checks': result['physical_checks'],
        'realized_observables': result['realized_observables'],
        'limitations': ['Actual lane occupancy, physical passage, camera pixels, consent, subsection 3 and legal outcome require independent original review.'],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n')
