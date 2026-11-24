"""Source-bound C125714 exception and yielding observations without legal verdicts.

This helper consumes retained original context and controller history. It records
which statutory fact pattern a reviewed source supports, but never decides
whether the legal exceptions apply or whether a driver yielded adequately.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

BASE = 'testing__C125714__NRS-484B-250-2__motor_vehicle_driver'
KINDS = ('different_highways_left_right', 'official_device_controlled',
         'opposite_straight', 'opposite_intends_left', 'opposite_makes_left',
         'subsection_4_context')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()
            if line.strip()]


def observe_context(site_path, map_path, reviewed_path):
    site_path, map_path, reviewed_path = map(Path,(site_path,map_path,reviewed_path))
    site = json.loads(site_path.read_text(encoding='utf-8'))
    reviewed = json.loads(reviewed_path.read_text(encoding='utf-8'))
    if site.get('map_sha256') != sha(map_path) or reviewed.get('map_sha256') != sha(map_path):
        raise ValueError('original map differs from independently reviewed source')
    if reviewed.get('case_id') != site.get('case_id') or not reviewed.get('reviewer'):
        raise ValueError('reviewed exception context lacks exact case and reviewer')
    for key in ('ego_highway','other_highway','approach_relation',
                'official_device_controls_intersection','other_left_turn_intent',
                'other_left_turn_making','subsection_4_context_reviewed'):
        if site.get(key) != reviewed.get(key):
            raise ValueError('exception context differs from reviewed source: '+key)
    relation = site['approach_relation']
    if relation not in ('crossing','opposite'):
        raise ValueError('reviewed approach relation required')
    for key in ('official_device_controls_intersection','other_left_turn_intent',
                'other_left_turn_making','subsection_4_context_reviewed'):
        if type(site[key]) is not bool:
            raise ValueError('reviewed boolean required: '+key)
    if relation == 'crossing' and site['ego_highway'] == site['other_highway']:
        raise ValueError('different-highway crossing claim unsupported')
    if site['other_left_turn_making'] and not site['other_left_turn_intent']:
        raise ValueError('left-turn making requires original intent context')
    facts = {
        'different_highways_left_right': relation == 'crossing' and
            site.get('ego_side') == 'left' and site.get('other_side') == 'right',
        'official_device_controlled': site['official_device_controls_intersection'],
        'opposite_straight': relation == 'opposite' and
            not site['other_left_turn_intent'],
        'opposite_intends_left': relation == 'opposite' and
            site['other_left_turn_intent'],
        'opposite_makes_left': relation == 'opposite' and
            site['other_left_turn_making'],
        'subsection_4_context': site['subsection_4_context_reviewed']}
    return {'format':'worker-c125714-reviewed-branch-observations-v1',
            'case_id':site['case_id'],'facts':facts,
            'source_sha256':{'road.xodr':sha(map_path),
                             'site-context.json':sha(site_path),
                             'reviewed-context.json':sha(reviewed_path)},
            'legal_exception_applies':'unresolved',
            'legal_verdict_claimed':False}


def observe_brake(controller_path, frame_map_path, other_entry_upper_s):
    """A synchronized control observation; braking alone is not statutory yielding."""
    rows, mapping = load_rows(controller_path), load_rows(frame_map_path)
    if (not rows or len(rows) != len(mapping) or
            type(other_entry_upper_s) not in (int,float) or
            not math.isfinite(other_entry_upper_s)):
        raise ValueError('complete original control/frame join required')
    samples = []
    for index, (control, frame) in enumerate(zip(rows,mapping)):
        if (frame.get('video_frame') != index or
                (control.get('frame'),control.get('time_s')) !=
                (frame.get('carla_frame'),frame.get('time_s'))):
            raise ValueError('original controller/frame identity changed')
        brake = control.get('ego_brake')
        if type(brake) not in (int,float) or not math.isfinite(brake) or not 0 <= brake <= 1:
            raise ValueError('original ego brake sample absent')
        if frame['time_s'] <= other_entry_upper_s:
            samples.append(brake)
    if not samples:
        raise ValueError('no original ego control before other entry')
    return {'format':'worker-c125714-brake-observation-v1',
            'ego_brake_observed_before_other_entry':any(x > 0 for x in samples),
            'max_ego_brake_before_other_entry':max(samples),
            'source_sha256':{'controller-history.jsonl':sha(controller_path),
                             'video_frames.jsonl':sha(frame_map_path)},
            'right_of_way_yielding':'unresolved',
            'legal_verdict_claimed':False}
