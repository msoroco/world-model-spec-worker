"""Bind the selected first-case entrypoint and common four-view plan."""

import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    source = json.loads((HERE / 'vehicle-indicator-construction.json').read_text())
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    config_item = next(item for item in source['files'] if item['path'] == 'config.json')
    config = json.loads(config_item['content'])
    config['supported_case_ids'] = [entry['case_id'] for entry in manifest['cases']]
    (HERE / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    root = deepcopy(source)
    next(item for item in root['files'] if item['path'] == 'config.json')['content'] = (HERE / 'config.json').read_text()
    root['measurement_plan'] = {
        'finalizer': 'turn_finalizer.py',
        'retained_sources': ['ego_turn_motion.jsonl', 'ego_signal_audio.jsonl',
                             'affected_participants.json', 'participant_bodies.jsonl',
                             'video_frames.jsonl', 'trace.jsonl'],
        'reported_boundary': 'Original turn, body clearance and conditional signal observations; no legal safety or audibility threshold'}
    root['static_checks'] = ['runner --check', 'source-shaped original turn/frame/signal tests',
                             'exact offline and missing-original compatibility for every manifest case']
    root['termination_rules'] = ['160 original 20 Hz frames',
                                 'reject missing turn, participant, signal or frame source']
    root['mechanisms'] = ['Native connected left-turn route and affected participants',
                          'indicator, horn relay or attached avatar pose as selected',
                          'four original RGB source cameras', 'saved-only finalizer']
    (HERE / 'construction.json').write_text(json.dumps(root, indent=2) + '\n')
    coverage = [
        ('overview', 'turning ego, pedestrian and affected vehicle', 'startup through final observation'),
        ('approach', 'approach path, governing turn region and signal', 'approach through turn'),
        ('reference_corner', 'pedestrian and affected vehicle body clearance', 'all original frames'),
        ('driver_reference', 'driver-side signal and turn path', 'approach through clearance'),
    ]
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'fps': 20,
        'duration_s': config['duration_s'], 'composition': 'synchronized_four_view_primary',
        'sources': [{'name': item['name'], 'size': [item['width'], item['height']],
                     'purpose': item['pose_strategy']} for item in config['cameras']],
        'coverage': [{'view': view, 'subject': subject, 'interval': interval}
                     for view, subject, interval in coverage],
        'implementation': 'turn_camera_capture.py',
        'limitation': 'Native pixels, horn audibility and physical turn/participant completion require local review.'}
    evidence = {
        'drv.turning': ('Original ego turn motion, yaw and frame joins', ['ego_turn_motion.jsonl', 'turn_originals.jsonl']),
        'drv.lane_change': ('Original direct-course departure trajectory; no separate lane-change claim', ['ego_turn_motion.jsonl', 'turn_scene_context.json']),
        'drv.time_to_conflict': ('Original body clearance and relative motion proxy; no legal safety cutoff', ['ego_turn_motion.jsonl', 'participant_bodies.jsonl']),
        'ru.pedestrian': ('Original affected pedestrian route/body context', ['affected_participants.json', 'participant_bodies.jsonl']),
        'sig.horn': ('Identified relay request and independently captured listener PCM in selected horn cases; actual sound unverified', ['horn_actuation.jsonl', 'listener_audio_original.jsonl']),
        'sig.turn_indicator': ('Native original indicator readback and four camera streams', ['ego_signal_audio.jsonl', 'overview.mkv']),
        'sig.hand_signal': ('Attached driver-avatar original hand-bone readback in hand alternative; visible pose unverified', ['hand_signal_original.jsonl', 'reference_corner.mkv']),
        'drv.following': ('Original affected vehicle body path and turn-relative context', ['affected_participants.json', 'participant_bodies.jsonl']),
        'rel.surface_gap': ('Original ego/participant body radii and sampled gap', ['ego_turn_motion.jsonl', 'participant_bodies.jsonl']),
    }
    for term, (description, sources) in evidence.items():
        if term not in plan['source_observation_mapping']:
            raise ValueError('Unexpected source observation inventory')
        plan['source_observation_mapping'][term] = {
            'evidence': description, 'channels': ['turn_signal_observation'],
            'source_refs': sources}
    plan_path.write_text(json.dumps(plan, indent=2) + '\n')


if __name__ == '__main__':
    main()
