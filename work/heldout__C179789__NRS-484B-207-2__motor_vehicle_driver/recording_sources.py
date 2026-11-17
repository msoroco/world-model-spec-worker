"""Saved-source recording evidence for overtaken-driver semantic requirements.

Absence of a notice modality and unknown right-pass permission remain explicit.
The derived files are recreated from retained original sources on every run.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def emit(root, verified_rows, *, audible):
    root = Path(root)
    original = [json.loads(line) for line in (root / 'overtaken_source.jsonl').read_text().splitlines()]
    if len(original) != len(verified_rows):
        raise ValueError('Original body and verified frame lengths differ')
    signals = envelopes = None
    if audible:
        signals = [json.loads(line) for line in (root / 'signal_command_original.jsonl').read_text().splitlines()]
        envelopes = [json.loads(line) for line in (root / 'signal_audio_envelope_original.jsonl').read_text().splitlines()]
        if len(signals) != len(original) or len(envelopes) != len(original):
            raise ValueError('Original signal/frame lengths differ')
    evidence = []

    def write_stream(name, values, unit):
        path = root / (name + '.jsonl')
        with path.open('x') as stream:
            for row, value in zip(verified_rows, values):
                stream.write(json.dumps({'frame': row['frame'], 'time_s': row['time_s'],
                                         'value': value}, allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': unit, 'reference': path.name,
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})

    observed_values = []
    audible_values = []
    gaps = []
    for index, (body, row) in enumerate(zip(original, verified_rows)):
        if body['frame'] != row['frame'] or body['time_s'] != row['time_s']:
            raise ValueError('Original semantic source/frame join differs')
        tangent = body['road_tangent_xy']
        project = lambda corner: corner[0]*tangent[0] + corner[1]*tangent[1]
        gap = min(map(project, body['overtaker_corners'])) - max(map(project, body['subject_corners']))
        gaps.append(gap)
        relation = body.get('visibility_relation')
        observed_values.append({'applicable': not audible,
                                'visibility_relation': relation if not audible else None,
                                'driver_observation_confirmed': None})
        if audible:
            signal, envelope = signals[index], envelopes[index]
            if any(item.get('frame') != row['frame'] or item.get('time_s') != row['time_s']
                   for item in (signal, envelope)):
                raise ValueError('Original signal/frame join differs')
            audible_values.append({'applicable': True, 'signal_command': signal,
                                   'generated_envelope': envelope,
                                   'acoustic_propagation_confirmed': None,
                                   'subjective_hearing_confirmed': None})
        else:
            audible_values.append({'applicable': False, 'signal_command': None,
                                   'generated_envelope': None,
                                   'subjective_hearing_confirmed': None})
    write_stream('observed_notice_source_context', observed_values, 'structured')
    write_stream('audible_signal_source_context', audible_values, 'structured')
    write_stream('full_body_pass_gap_m', gaps, 'm')

    rule = root / 'right-pass-governing-rule-source.json'
    survey = root / 'right_pass_road_survey.json'
    context = {'right_pass_permission_context': {
        'governing_rule_reference_sha256': hashlib.sha256(rule.read_bytes()).hexdigest() if rule.is_file() else None,
        'original_road_survey_sha256': hashlib.sha256(survey.read_bytes()).hexdigest() if survey.is_file() else None,
        'permission_state': None, 'safety_condition_verified': None,
        'legal_conclusion': None,
        'source_status': 'source review incomplete'}}
    path = root / 'right_pass_permission_context.json'
    with path.open('x') as stream:
        json.dump(context, stream, indent=2, allow_nan=False)
        stream.write('\n')
    evidence.append({'name': 'right_pass_permission_context', 'unit': 'structured',
                     'reference': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return evidence
