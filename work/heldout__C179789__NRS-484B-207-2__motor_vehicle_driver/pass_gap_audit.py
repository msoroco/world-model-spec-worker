"""Independent signed body-gap audit over retained original pass sources."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from overtaken_response import verify_saved_sources


def audit(source_path, frame_map_path, trace_path):
    verified = verify_saved_sources(source_path, frame_map_path, trace_path)
    rows = [json.loads(line) for line in Path(source_path).read_text().splitlines() if line.strip()]
    gaps = []
    for raw, observed in zip(rows, verified['frames']):
        tx, ty = raw['road_tangent_xy']
        rear = min(x * tx + y * ty for x, y in raw['overtaker_corners'])
        front = max(x * tx + y * ty for x, y in raw['subject_corners'])
        gap = rear - front
        if (gap > 0) != observed['body_pass_complete']:
            raise ValueError('Original signed body gap and completion differ')
        gaps.append({'frame': observed['frame'], 'time_s': observed['time_s'],
                     'signed_gap_m': gap, 'body_pass_complete': observed['body_pass_complete']})
    return {'format': 'worker-signed-body-pass-gap-audit',
            'source_sha256': verified['source_sha256'], 'frames': gaps,
            'first_positive_gap_frame': next((row['frame'] for row in gaps if row['signed_gap_m'] > 0), None),
            'physical_acceptance_claimed': False, 'legal_conclusion': None}


def assess(root, *, audible):
    """Classify the original pass interval while preserving provenance uncertainty.

    A diagnostic fixture can demonstrate geometry and the branch logic, but it
    cannot produce a Native physical-completion claim.
    """
    root = Path(root)
    names = ['overtaken_source.jsonl', 'video_frames.jsonl', 'trace.jsonl']
    if audible:
        names += ['signal_command_original.jsonl', 'signal_audio_envelope_original.jsonl']
    missing = [name for name in names if not (root / name).is_file()]
    sources = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
               for name in names if name not in missing}
    method = 'original full-body signed gap after joined generated signal command' if audible else \
             'original full-body signed gap after joined visibility rays'
    if missing:
        return {'physical_checks': {'maneuver': {'status': 'unverified', 'method': method,
                'sources': sources, 'missing_evidence': missing}},
                'maneuver_completed': False, 'provenance_kind': 'unverified',
                'diagnostic_fixture_only': False, 'physical_acceptance_claimed': False}
    try:
        gap = audit(*(root / name for name in names[:3]))
        bodies = [json.loads(line) for line in (root / names[0]).read_text().splitlines() if line.strip()]
        if audible:
            commands = [json.loads(line) for line in (root / names[3]).read_text().splitlines() if line.strip()]
            envelopes = [json.loads(line) for line in (root / names[4]).read_text().splitlines() if line.strip()]
            if len(commands) != len(bodies) or len(envelopes) != len(bodies):
                raise ValueError('Original generated signal/frame count differs')
            notices = []
            for body, command, envelope in zip(bodies, commands, envelopes):
                common = (body['frame'], body['time_s'], str(body['overtaker_id']))
                if ((command.get('frame'), command.get('time_s'), command.get('overtaker_actor_id')) != common or
                    (envelope.get('frame'), envelope.get('time_s'), envelope.get('overtaker_actor_id')) != common or
                    command.get('source_kind') != 'scenario_signal_command' or
                    envelope.get('source_kind') != 'generated_signal_envelope' or
                    type(command.get('horn_command_requested')) is not bool or
                    body.get('notice_stimulus') != command['horn_command_requested'] or
                    envelope.get('generated_rms') != (0.6 if command['horn_command_requested'] else 0.0) or
                    envelope.get('acoustic_propagation_confirmed') is not None or
                    envelope.get('subjective_hearing_confirmed') is not None):
                    raise ValueError('Original generated signal/frame join differs')
                if command['horn_command_requested']:
                    notices.append(body['frame'])
        else:
            notices = [body['frame'] for body in bodies if body.get('notice_observed') is True]
        if not notices:
            raise ValueError('Original notice source has no event')
        notice = notices[0]
        completion = next((row['frame'] for row in gap['frames']
                           if row['frame'] > notice and row['signed_gap_m'] > 0), None)
        geometry_status = 'met' if completion is not None else 'not_met'
        marker = root / 'fixture-provenance.json'
        provenance = json.loads(marker.read_text()) if marker.is_file() else {}
        receipt_path = root / 'native-capture-receipt.json'
        receipt = json.loads(receipt_path.read_text()) if receipt_path.is_file() else {}
        lifecycle = ['capture_finished', 'encoders_closed', 'restoration_verified',
                     'native_exit', 'owner_released']
        native = (provenance.get('actual_native_capture') is True and
                  provenance.get('diagnostic_fixture') is False and
                  receipt.get('actual_native_capture') is True and
                  receipt.get('source_sha256') == sources and
                  receipt.get('events') == lifecycle)
        status = geometry_status if native else 'unverified'
        return {'physical_checks': {'maneuver': {'status': status, 'method': method,
                'sources': sources, 'notice_frame': notice,
                'first_positive_gap_frame': gap['first_positive_gap_frame'],
                'completion_frame_after_notice': completion,
                'diagnostic_geometry_status': geometry_status,
                'missing_evidence': [] if native else ['source-hashed, ordered actual Native capture receipt']}},
                'maneuver_completed': status == 'met',
                'provenance_kind': 'native' if native else 'diagnostic_fixture' if provenance.get('diagnostic_fixture') else 'unverified',
                'diagnostic_fixture_only': provenance.get('diagnostic_fixture') is True,
                'physical_acceptance_claimed': False}
    except (ValueError, KeyError, TypeError) as error:
        return {'physical_checks': {'maneuver': {'status': 'unverified', 'method': method,
                'sources': sources, 'missing_evidence': [str(error)]}},
                'maneuver_completed': False, 'provenance_kind': 'unverified',
                'diagnostic_fixture_only': False, 'physical_acceptance_claimed': False}
