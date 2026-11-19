"""Independent signed body-gap audit over retained original pass sources."""
from __future__ import annotations
import hashlib
import json
import shutil
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
        exit_path = root / 'native-process-exit.json'
        exit_proof = json.loads(exit_path.read_text()) if exit_path.is_file() else {}
        lifecycle = ['capture_finished', 'encoders_closed', 'restoration_verified',
                     'native_exit', 'owner_released']
        native = (provenance.get('diagnostic_fixture') is not True and
                  receipt.get('actual_native_capture') is True and
                  receipt.get('source_sha256') == sources and
                  receipt.get('events') == lifecycle and
                  exit_proof.get('event') == 'native_process_exit_observed' and
                  exit_proof.get('native_exit_code') == 0 and
                  exit_proof.get('owner_lock_released') is True and
                  exit_proof.get('case_id') == receipt.get('case_id') and
                  exit_proof.get('native_capture_receipt_sha256') ==
                  (hashlib.sha256(receipt_path.read_bytes()).hexdigest() if receipt_path.is_file() else None))
        status = geometry_status if native else 'unverified'
        return {'physical_checks': {'maneuver': {'status': status, 'method': method,
                'sources': sources, 'notice_frame': notice,
                'first_positive_gap_frame': gap['first_positive_gap_frame'],
                'completion_frame_after_notice': completion,
                'diagnostic_geometry_status': geometry_status,
                'missing_evidence': [] if native else ['source-hashed actual Native capture and independent process-exit receipt']}},
                'maneuver_completed': status == 'met',
                'provenance_kind': 'native' if native else 'diagnostic_fixture' if provenance.get('diagnostic_fixture') else 'unverified',
                'diagnostic_fixture_only': provenance.get('diagnostic_fixture') is True,
                'physical_acceptance_claimed': False}
    except (ValueError, KeyError, TypeError) as error:
        return {'physical_checks': {'maneuver': {'status': 'unverified', 'method': method,
                'sources': sources, 'missing_evidence': [str(error)]}},
                'maneuver_completed': False, 'provenance_kind': 'unverified',
                'diagnostic_fixture_only': False, 'physical_acceptance_claimed': False}


def diagnostic_outcomes(source_root, output_root, *, audible):
    """Exercise all outcome branches from retained sources without claiming Native capture."""
    source_root, output_root = Path(source_root), Path(output_root)
    if output_root.exists():
        raise ValueError('Diagnostic output already exists')
    names = ['overtaken_source.jsonl', 'video_frames.jsonl', 'trace.jsonl']
    if audible:
        names += ['signal_command_original.jsonl', 'signal_audio_envelope_original.jsonl']
    if any(not (source_root / name).is_file() for name in names):
        raise ValueError('Original diagnostic source missing')
    original_marker = source_root / 'fixture-provenance.json'
    if not original_marker.is_file() or json.loads(original_marker.read_text()).get('diagnostic_fixture') is not True:
        raise ValueError('Only explicitly diagnostic sources may seed diagnostic outcomes')
    original_hashes = {name: hashlib.sha256((source_root / name).read_bytes()).hexdigest() for name in names}
    original = assess(source_root, audible=audible)
    if original['physical_checks']['maneuver'].get('diagnostic_geometry_status') != 'met':
        raise ValueError('Original diagnostic geometry does not complete after notice')
    output_root.mkdir(parents=True)
    reports = {}
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        target = output_root / kind
        target.mkdir()
        for name in names:
            if kind == 'missing_evidence' and name == 'trace.jsonl':
                continue
            shutil.copyfile(source_root / name, target / name)
        shutil.copyfile(original_marker, target / original_marker.name)
        if kind == 'incomplete_motion':
            completion = original['physical_checks']['maneuver']['completion_frame_after_notice']
            bodies = [json.loads(row) for row in (target / names[0]).read_text().splitlines() if row.strip()]
            keep = sum(row['frame'] < completion for row in bodies)
            if keep < 2 or keep >= len(bodies):
                raise ValueError('Cannot construct a precompletion diagnostic interval')
            for name in names:
                rows = [json.loads(row) for row in (target / name).read_text().splitlines() if row.strip()]
                rows = rows[:keep]
                if name == 'video_frames.jsonl':
                    for index, row in enumerate(rows):
                        row['video_frame'] = index
                (target / name).write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
        result = assess(target, audible=audible)
        measured = result['physical_checks']['maneuver']
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met'}.get(kind)
        if measured['status'] != 'unverified' or result['maneuver_completed']:
            raise ValueError('Diagnostic fixture was promoted to Native completion')
        if expected and measured.get('diagnostic_geometry_status') != expected:
            raise ValueError('Diagnostic fixture did not exercise requested geometry branch')
        if kind == 'missing_evidence' and 'trace.jsonl' not in measured.get('missing_evidence', []):
            raise ValueError('Missing-source fixture was accepted')
        reports[kind] = {'source_sha256': measured['sources'], 'result': result}
    return {'format': 'worker-overtaken-physical-diagnostic-outcomes',
            'source_root_sha256': original_hashes, 'fixtures': reports,
            'diagnostic_fixture_only': True, 'physical_acceptance_claimed': False}


def physical_fixture_result(report, kind, case_id):
    """Report one synthetic branch for CPU preparation without Native promotion."""
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}
    if kind not in expected or report.get('format') != 'worker-overtaken-physical-diagnostic-outcomes':
        raise ValueError('Unknown source-bound diagnostic outcome')
    if report.get('diagnostic_fixture_only') is not True or report.get('physical_acceptance_claimed'):
        raise ValueError('Physical fixture requires explicit diagnostic provenance')
    item = report.get('fixtures', {}).get(kind)
    if not isinstance(item, dict):
        raise ValueError('Diagnostic outcome branch missing')
    original = item.get('result', {})
    measured = original.get('physical_checks', {}).get('maneuver', {})
    sources = item.get('source_sha256')
    if (not isinstance(sources, dict) or not sources or
            measured.get('sources') != sources or
            measured.get('status') != 'unverified' or
            original.get('maneuver_completed') is not False):
        raise ValueError('Diagnostic source branch was altered or promoted')
    geometry = measured.get('diagnostic_geometry_status')
    if kind == 'missing_evidence':
        if 'trace.jsonl' not in measured.get('missing_evidence', []):
            raise ValueError('Missing trace diagnostic was accepted')
    elif geometry != expected[kind]:
        raise ValueError('Diagnostic geometry branch differs')
    check = {'status': expected[kind],
             'method': 'synthetic original-shaped signed-body-gap branch after joined notice; fixture only',
             'sources': sources,
             'diagnostic_geometry_status': geometry,
             'actual_native_maneuver_status': 'unverified',
             'missing_evidence': measured.get('missing_evidence', [])}
    if kind == 'complete_motion':
        check['notice_frame'] = measured.get('notice_frame')
        check['completion_frame_after_notice'] = measured.get('completion_frame_after_notice')
        if check['completion_frame_after_notice'] is None:
            raise ValueError('Synthetic completion has no measured source frame')
    return {'case_id': case_id, 'fixture_kind': kind,
            'physical_checks': {'maneuver': check},
            'maneuver_completed': kind == 'complete_motion',
            'realized_observables': {'first_positive_gap_frame': check['completion_frame_after_notice'],
                                     'notice_frame': check['notice_frame']} if kind == 'complete_motion' else {},
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'actual_native_capture': False, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--audible', action='store_true')
    args = parser.parse_args()
    report = diagnostic_outcomes(args.source, args.output, audible=args.audible)
    (Path(args.output) / 'diagnostic-outcomes.json').write_text(json.dumps(report, indent=2) + '\n')
