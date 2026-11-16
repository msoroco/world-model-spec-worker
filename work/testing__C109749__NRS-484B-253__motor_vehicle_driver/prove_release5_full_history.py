"""Prove a 900-frame synthetic yield-then-turn source path for the 5 s draft.

The four cameras are diagnostic patterns without actor depiction. The proof
exercises source joins, finalization, decode and negatives, never Native motion.
"""
import hashlib
import json
import math
import shutil
import sys
import tempfile
import io
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))

from approaching_delivery_audit import CAMERAS, validate_originals
from approaching_yield_observation import observe
from far_approach_observation import observe as observe_far
from hazard_sweep_policy import HazardSweepPolicy
from far_delivery_audit import far_sequence
from approaching_delivery_audit import validate_approaching_sequence
from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release
from worker_exchange.physical_preparation import validate as validate_physical
from worker_exchange.delivery_handoff import validate_case as validate_delivery_case
from worker_exchange.media import compose_four_views
from release_grid_delivery_audit import audit_attempt as audit_release
from prove_far_approach_history import actor, make_sources, source_rows, write_jsonl
from worker_exchange.media import audit as decode

CASE = ROOT.name + '__approaching_release_5s'
SOURCE = REPO / '.runtime-work/c109749-far-delivery-v2/attempt'
OUTPUT = REPO / '.runtime-work/c109749-release5-full-history-v1'
INDEX = ROOT / 'hazard-release-draft-proof-index.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def bundle():
    index = json.loads(INDEX.read_text())
    row = next(x for x in index['cases'] if x['case_id'] == CASE and x['candidate'] == 'primary')
    path = ROOT / 'cases/approaching_release_5s/construction.json'
    require(sha(path) == row['construction_sha256'], 'Exact 5 s draft construction changed')
    data = json.loads(path.read_text())
    return index, {item['path']: item['content'] for item in data['files']}


def history():
    rows = source_rows()
    for index, row in enumerate(rows):
        if 41 <= index <= 165:
            row['ego'] = actor(205, -2, 0, 0, 0)
            row['ego_heading_deg'] = 0
            row['ego_left_indicator'] = True
        elif index > 165:
            row['ego'] = actor(205, -2, -.25 * (index - 165), 0, -5)
            row['ego_heading_deg'] = -20 if index == 166 else -90
            row['ego_left_indicator'] = index <= 210
    return rows


def prepare(files):
    require(not OUTPUT.exists(), 'Use a fresh ignored full-history output root')
    attempt = OUTPUT / 'attempt'
    rows = history()
    make_sources(attempt, rows)
    (attempt / 'config.json').write_text(files['config.json'])
    for camera in CAMERAS:
        shutil.copy2(SOURCE / (camera + '.mkv'), attempt / (camera + '.mkv'))
    write_jsonl(attempt / 'trace.jsonl', [
        {'frame': row['frame'], 'time_s': row['time_s'],
         'position_m': [*row['ego']['position_xy_m'], 0],
         'heading_deg': row['ego_heading_deg'],
         'speed_mps': math.hypot(*row['ego']['velocity_xy_mps'])}
        for row in rows])
    (attempt / 'capture').mkdir()
    write_jsonl(attempt / 'capture/evidence.jsonl', [
        {'original_frame': row['frame'], 'recording_time_s': row['time_s'],
         'fixture_only': True} for row in rows])
    return attempt


def finalized(attempt, files):
    namespace = {'__name__': 'release5_draft_finalizer',
                 '__file__': str(ROOT / 'cases/approaching_release_5s/finalizer.py')}
    exec(compile(files['finalizer.py'], namespace['__file__'], 'exec'), namespace)
    namespace['finalize'](attempt, attempt / 'analysis-report.json')
    result = json.loads((attempt / 'result.json').read_text())
    require(result['case_id'] == CASE and result.get('physical_acceptance_claimed') is False,
            'Diagnostic finalizer claimed another case or physical acceptance')
    return result


def audit_sources(attempt, expected):
    seal = json.loads((attempt / 'capture-seal.json').read_text())
    require(seal['format'] == 'worker-sealed-capture' and
            seal['diagnostic_fixture'] is True and seal['frames'] == 900 and
            seal['sources'] == expected and seal['physical_acceptance_claimed'] is False,
            'Full diagnostic source seal changed')
    for name, digest in expected.items():
        path = attempt / name
        require(path.is_file() and sha(path) == digest,
                'Sealed original source changed: ' + name)
    joined = validate_originals(attempt, CASE)
    observation = observe(attempt)
    result = json.loads((attempt / 'result.json').read_text())
    measured = result['measured_values']
    require(measured['ego_turn_start_frame'] == observation['ego_turn_start_frame'] and
            measured['initial_oncoming_clearance_frame'] == observation['opposing_clearance_frame'] and
            observation['opposing_entry_frame'] < observation['opposing_clearance_frame'] <
            observation['ego_turn_start_frame'],
            'Finalizer and independent yielding observation differ')
    return joined, observation


def fixed_trajectory_comparison(yield_attempt, yield_observation):
    far_seal = json.loads((SOURCE / 'capture-seal.json').read_text())
    far_audit = json.loads((SOURCE / 'far-diagnostic-audit.json').read_text())
    require(far_seal['sources']['interaction_history.jsonl'] == sha(SOURCE / 'interaction_history.jsonl') and
            far_audit['software_checks_passed'] is True and far_audit['passed'] is False,
            'Selected 4 s diagnostic source or audit changed')
    far = [json.loads(line) for line in (SOURCE / 'interaction_history.jsonl').read_text().splitlines()]
    held = [json.loads(line) for line in (yield_attempt / 'interaction_history.jsonl').read_text().splitlines()]

    def compare(left, right):
        require(len(left) == len(right) == 900, 'Full matched trajectories required')
        for index, (before, after) in enumerate(zip(left, right)):
            require(before['frame'] == after['frame'] and before['time_s'] == after['time_s'] and
                    before['oncoming'] == after['oncoming'] and
                    before['reciprocal'] == after['reciprocal'],
                    'Fixed opposing or time source changed')
            if index <= 40:
                require(before['ego'] == after['ego'] and
                        before['ego_heading_deg'] == after['ego_heading_deg'] and
                        before['ego_left_indicator'] == after['ego_left_indicator'],
                        'Predifference subject source changed')

    compare(far, held)
    far_turn = next(row['frame'] for row in far if row['ego_heading_deg'] <= -15)
    require(far_turn == 38074 and
            far_turn < yield_observation['opposing_entry_frame'] <
            yield_observation['opposing_clearance_frame'] <
            yield_observation['ego_turn_start_frame'],
            'Matched release actions lack intended source ordering')
    altered = [dict(row) for row in held]
    altered[0]['oncoming'] = dict(altered[0]['oncoming'])
    altered[0]['oncoming']['position_xy_m'] = list(altered[0]['oncoming']['position_xy_m'])
    altered[0]['oncoming']['position_xy_m'][0] += 1.0
    try:
        compare(far, altered)
    except ValueError as exc:
        require('Fixed opposing or time source changed' in str(exc),
                'Changed opposing comparison failed elsewhere')
    else:
        raise ValueError('Changed opposing position passed fixed-condition comparison')
    return {'selected_4s_source_sha256': sha(SOURCE / 'interaction_history.jsonl'),
            'selected_4s_audit_sha256': sha(SOURCE / 'far-diagnostic-audit.json'),
            'five_second_source_sha256': sha(yield_attempt / 'interaction_history.jsonl'),
            'shared_opposing_and_reciprocal_frames': 900,
            'identical_predifference_subject_frames': 41,
            'selected_4s_turn_frame': far_turn,
            'five_second_turn_frame': yield_observation['ego_turn_start_frame'],
            'changed_opposing_position_rejected': True,
            'scope': 'matched synthetic source trajectories; no Native or legal acceptance'}


def prove():
    index, files = bundle()
    attempt = prepare(files)
    result = finalized(attempt, files)
    sources = ('config.json', 'intersection_geometry.json', 'interaction_history.jsonl',
               'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl',
               *(name + '.mkv' for name in CAMERAS))
    sealed = {name: sha(attempt / name) for name in sources}
    (attempt / 'capture-seal.json').write_text(json.dumps({
        'format': 'worker-sealed-capture', 'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True, 'frames': 900, 'sources': sealed,
        'physical_acceptance_claimed': False}, indent=2) + '\n')
    joined, observation = audit_sources(attempt, sealed)
    comparison = fixed_trajectory_comparison(attempt, observation)
    decoded = {}
    for name in CAMERAS:
        decoded[name] = decode(attempt / (name + '.mkv'), 900,
                               mapping_sha256=joined['frame_map_sha256'],
                               receipt=OUTPUT / (name + '-decode.json'))
        require(decoded[name]['passed'], 'Four-camera source decode failed: ' + name)
    # Both negatives use the same source audit, and the positive is restored.
    camera = attempt / 'overview.mkv'
    hidden = attempt / 'overview.mkv.negative-hidden'
    camera.rename(hidden)
    try:
        try:
            audit_sources(attempt, sealed)
        except ValueError as exc:
            require('Sealed original source changed: overview.mkv' in str(exc),
                    'Missing-camera negative failed elsewhere')
        else:
            raise ValueError('Missing sealed overview camera was accepted')
    finally:
        hidden.rename(camera)
    motion = attempt / 'interaction_history.jsonl'
    original = motion.read_bytes()
    changed = [json.loads(line) for line in original.splitlines()]
    changed[0]['oncoming']['position_xy_m'][0] += 1.0
    motion.write_text(''.join(json.dumps(row) + '\n' for row in changed))
    try:
        try:
            audit_sources(attempt, sealed)
        except ValueError as exc:
            require('Sealed original source changed: interaction_history.jsonl' in str(exc),
                    'Changed-history negative failed elsewhere')
        else:
            raise ValueError('Changed sealed opposing history was accepted')
    finally:
        motion.write_bytes(original)
    audit_sources(attempt, sealed)
    proof = {'format': 'worker-release5-full-duration-diagnostic', 'case_id': CASE,
             'construction_sha256': next(x['construction_sha256'] for x in index['cases']
                                         if x['case_id'] == CASE and x['candidate'] == 'primary'),
             'source_frames': joined['frames'], 'source_hashes': sealed,
             'capture_seal_sha256': sha(attempt / 'capture-seal.json'),
             'opposing_entry_frame': observation['opposing_entry_frame'],
             'opposing_clearance_frame': observation['opposing_clearance_frame'],
             'ego_turn_start_frame': observation['ego_turn_start_frame'],
             'four_camera_decode_passed': True,
             'missing_camera_rejected': True, 'changed_history_rejected': True,
             'fixture_kind': 'synthetic 900-frame source and reused static diagnostic cameras',
             'actor_pixel_visibility_verified': False,
             'native_or_legal_acceptance_claimed': False}
    index['release5_full_history_diagnostic'] = proof
    index['release4_5_fixed_trajectory_comparison'] = comparison
    INDEX.write_text(json.dumps(index, indent=2) + '\n')
    return proof


def prove_three(output_root=None):
    """Exercise the exact 3 s finalizer on a full, separately sealed source."""
    case = ROOT.name + '__approaching_release_3s'
    index = json.loads(INDEX.read_text())
    row = next(x for x in index['cases'] if x['case_id'] == case and x['candidate'] == 'primary')
    construction = ROOT / 'cases/approaching_release_3s/construction.json'
    require(sha(construction) == row['construction_sha256'], 'Exact 3 s draft construction changed')
    files = {item['path']: item['content'] for item in json.loads(construction.read_text())['files']}
    output_root = Path(output_root or REPO / '.runtime-work/c109749-release3-full-history-v2').resolve()
    require((REPO / '.runtime-work').resolve() in output_root.parents,
            'Diagnostic output must stay under ignored .runtime-work')
    attempt = output_root / 'attempt'
    require(not attempt.exists(), 'Use a fresh ignored 3 s full-history output root')
    rows = source_rows()
    for source_row in rows:
        opposing = source_row['oncoming']
        opposing['position_xy_m'][0] -= 5
        for vertex in opposing['body_vertices_xy_m']:
            vertex[0] -= 5
    make_sources(attempt, rows)
    (attempt / 'config.json').write_text(files['config.json'])
    for camera in CAMERAS:
        shutil.copy2(SOURCE / (camera + '.mkv'), attempt / (camera + '.mkv'))
    write_jsonl(attempt / 'trace.jsonl', [
        {'frame': source_row['frame'], 'time_s': source_row['time_s'],
         'position_m': [*source_row['ego']['position_xy_m'], 0],
         'heading_deg': source_row['ego_heading_deg'],
         'speed_mps': math.hypot(*source_row['ego']['velocity_xy_mps'])}
        for source_row in rows])
    (attempt / 'capture').mkdir()
    write_jsonl(attempt / 'capture/evidence.jsonl', [
        {'original_frame': source_row['frame'], 'recording_time_s': source_row['time_s'],
         'fixture_only': True} for source_row in rows])
    namespace = {'__name__': 'release3_draft_finalizer',
                 '__file__': str(ROOT / 'cases/approaching_release_3s/finalizer.py')}
    exec(compile(files['finalizer.py'], namespace['__file__'], 'exec'), namespace)
    namespace['finalize'](attempt, attempt / 'analysis-report.json')
    result = json.loads((attempt / 'result.json').read_text())
    require(result['case_id'] == case and result.get('physical_acceptance_claimed') is False,
            'Diagnostic finalizer claimed another case or physical acceptance')
    sources = ('config.json', 'intersection_geometry.json', 'interaction_history.jsonl',
               'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl',
               *(name + '.mkv' for name in CAMERAS))
    sealed = {name: sha(attempt / name) for name in sources}
    (attempt / 'capture-seal.json').write_text(json.dumps({
        'format': 'worker-sealed-capture', 'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True, 'frames': 900, 'sources': sealed,
        'physical_acceptance_claimed': False}, indent=2) + '\n')

    def audit():
        for name, digest in sealed.items():
            require((attempt / name).is_file() and sha(attempt / name) == digest,
                    'Sealed original source changed: ' + name)
        joined = validate_originals(attempt, case)
        observation = observe_far(attempt)
        measured = json.loads((attempt / 'result.json').read_text())['measured_values']
        require(measured['ego_turn_start_frame'] == observation['ego_turn_start_frame'] and
                measured['opposing_entry_frame'] == observation['opposing_entry_frame'],
                'Finalizer and independent far-approach observation differ')
        return joined, observation

    joined, observation = audit()
    require(3.9 < observation['turn_sample']['kinematic_time_to_conflict_s'] < 4.0,
            'Full 3 s source does not separate 3 s and 4 s releases')
    remaining = observation['turn_sample']['remaining_distance_m']
    closing = observation['turn_sample']['closing_speed_mps']
    actions = {}
    for release in (3.0, 4.0):
        actions[str(release)] = HazardSweepPolicy(release_ttc_s=release,
            approach_speed_mps=5.0).step(distance_to_hold_m=0.0, ego_speed_mps=0.0,
            oncoming_distance_to_conflict_m=remaining,
            oncoming_closing_speed_mps=closing, oncoming_in_intersection=False,
            oncoming_cleared=False, turn_complete=False)['state']
    require(actions == {'3.0': 'turn', '4.0': 'yield'},
            'Same-source 3 s/4 s release actions did not separate')
    decoded = {}
    for camera in CAMERAS:
        decoded[camera] = decode(attempt / (camera + '.mkv'), 900,
                                 mapping_sha256=joined['frame_map_sha256'],
                                 receipt=attempt.parent / (camera + '-decode.json'))
        require(decoded[camera]['passed'], 'Four-camera source decode failed: ' + camera)
    camera = attempt / 'overview.mkv'
    hidden = attempt / 'overview.mkv.negative-hidden'
    camera.rename(hidden)
    try:
        try:
            audit()
        except ValueError as exc:
            require('Sealed original source changed: overview.mkv' in str(exc),
                    'Missing-camera negative failed elsewhere')
        else:
            raise ValueError('Missing sealed overview camera was accepted')
    finally:
        hidden.rename(camera)
    motion = attempt / 'interaction_history.jsonl'
    original = motion.read_bytes()
    changed = [json.loads(line) for line in original.splitlines()]
    changed[0]['oncoming']['position_xy_m'][0] += 1
    motion.write_text(''.join(json.dumps(item) + '\n' for item in changed))
    try:
        try:
            audit()
        except ValueError as exc:
            require('Sealed original source changed: interaction_history.jsonl' in str(exc),
                    'Changed-history negative failed elsewhere')
        else:
            raise ValueError('Changed sealed opposing history was accepted')
    finally:
        motion.write_bytes(original)
    audit()
    proof = {'format': 'worker-release3-full-duration-diagnostic', 'case_id': case,
             'construction_sha256': row['construction_sha256'],
             'source_frames': joined['frames'], 'source_hashes': sealed,
             'capture_seal_sha256': sha(attempt / 'capture-seal.json'),
             'ego_turn_start_frame': observation['ego_turn_start_frame'],
             'opposing_entry_frame': observation['opposing_entry_frame'],
             'measured_time_to_conflict_s': observation['turn_sample']['kinematic_time_to_conflict_s'],
             'same_source_release_actions': actions, 'four_camera_decode_passed': True,
             'missing_camera_rejected': True, 'changed_history_rejected': True,
             'fixture_kind': 'synthetic 900-frame source and reused static diagnostic cameras',
             'actor_pixel_visibility_verified': False,
             'native_or_legal_acceptance_claimed': False}
    index['release3_full_history_diagnostic'] = proof
    INDEX.write_text(json.dumps(index, indent=2) + '\n')
    return proof


def prove_independent_delivery_sequences():
    """Bind existing independent delivery sequence checks to both sealed drafts."""
    index = json.loads(INDEX.read_text())
    cases = (
        ('release3_full_history_diagnostic',
         REPO / '.runtime-work/c109749-release3-full-history-v2/attempt',
         ROOT / 'far_delivery_audit.py',
         lambda attempt, result: far_sequence(attempt, result),
         'turn_sample'),
        ('release5_full_history_diagnostic',
         REPO / '.runtime-work/c109749-release5-full-history-v1/attempt',
         ROOT / 'approaching_delivery_audit.py',
         lambda attempt, result: validate_approaching_sequence(attempt, 'yield', result),
         'approaching_yield_samples'),
    )
    bound = {}
    for name, attempt, auditor, check, key in cases:
        prior = index[name]
        require(prior['source_frames'] == 900 and prior['construction_sha256'] and
                prior['case_id'].endswith('__approaching_release_3s' if key == 'turn_sample'
                                          else '__approaching_release_5s'),
                'Full-duration draft proof changed')
        for source, digest in prior['source_hashes'].items():
            require((attempt / source).is_file() and sha(attempt / source) == digest,
                    'Sealed original source changed: ' + source)
        require(sha(attempt / 'capture-seal.json') == prior['capture_seal_sha256'],
                'Source capture seal changed')
        result = json.loads((attempt / 'result.json').read_text())
        require(result['case_id'] == prior['case_id'] and
                result.get('physical_acceptance_claimed') is False,
                'Exact diagnostic result or physical claim changed')
        observed = check(attempt, result)
        require(observed.get('legal_verdict_asserted') is False,
                'Independent sequence asserted a legal verdict')
        altered = json.loads(json.dumps(result))
        if key == 'turn_sample':
            altered['measured_values'][key]['remaining_distance_m'] += 1
        else:
            altered['measured_values'][key][0]['distance_to_conflict_m'] += 1
        try:
            check(attempt, altered)
        except ValueError:
            pass
        else:
            raise ValueError('Independent delivery sequence accepted changed saved measurement')
        bound[name] = {
            'case_id': prior['case_id'],
            'source_history_sha256': prior['source_hashes']['interaction_history.jsonl'],
            'source_geometry_sha256': prior['source_hashes']['intersection_geometry.json'],
            'source_result_sha256': sha(attempt / 'result.json'),
            'auditor_sha256': sha(auditor),
            'sequence': {k: v for k, v in observed.items() if k != 'approaching_yield_samples'},
            'yield_sample_count': len(observed.get('approaching_yield_samples', [])),
            'changed_saved_measurement_rejected': True,
        }
    proof = {'format': 'worker-release-grid-independent-sequence-diagnostic',
             'cases': bound, 'source_kind': 'sealed synthetic diagnostic',
             'physical_or_legal_acceptance_claimed': False}
    index['independent_delivery_sequence_diagnostic'] = proof
    INDEX.write_text(json.dumps(index, indent=2) + '\n')
    return proof


def compare_three_four_full_history():
    """Audit all 900 rows of the controlled 5 m opposing-approach shift."""
    near = REPO / '.runtime-work/c109749-release3-full-history-v2/attempt'
    index = json.loads(INDEX.read_text())
    proof = index['release3_full_history_diagnostic']
    require(proof['source_frames'] == 900 and
            proof['case_id'] == ROOT.name + '__approaching_release_3s',
            'Exact 3 s full-history proof changed')
    for source, digest in proof['source_hashes'].items():
        require(sha(near / source) == digest,
                'Sealed 3 s comparison source changed: ' + source)
    require(sha(near / 'capture-seal.json') == proof['capture_seal_sha256'],
            '3 s comparison source seal changed')
    far_seal = json.loads((SOURCE / 'capture-seal.json').read_text())
    for source, digest in far_seal['sources'].items():
        require(sha(SOURCE / source) == digest,
                'Sealed 4 s comparison source changed: ' + source)
    far_audit = json.loads((SOURCE / 'far-diagnostic-audit.json').read_text())
    require(far_audit['software_checks_passed'] is True and
            far_audit['passed'] is False,
            'Selected 4 s diagnostic audit changed')
    for source in ('intersection_geometry.json', 'video_frames.jsonl',
                   'capture/evidence.jsonl'):
        require(sha(near / source) == sha(SOURCE / source),
                'Fixed geometry or frame evidence changed: ' + source)
    far = [json.loads(line) for line in (SOURCE / 'interaction_history.jsonl').read_text().splitlines()]
    closer = [json.loads(line) for line in (near / 'interaction_history.jsonl').read_text().splitlines()]

    def compare(left, right):
        require(len(left) == len(right) == 900, 'Full matched 3 s/4 s histories required')
        for original, shifted in zip(left, right):
            require(set(original) == set(shifted), 'Top-level source fields changed')
            for key in ('frame', 'time_s', 'ego', 'ego_heading_deg',
                        'ego_left_indicator', 'reciprocal'):
                require(original[key] == shifted[key],
                        'Fixed 3 s/4 s source changed: ' + key)
            for key in set(original) - {'frame', 'time_s', 'ego', 'ego_heading_deg',
                                        'ego_left_indicator', 'reciprocal', 'oncoming'}:
                require(original[key] == shifted[key],
                        'Additional fixed 3 s/4 s source changed: ' + key)
            base = original['oncoming']
            changed = shifted['oncoming']
            require(set(base) == set(changed), 'Opposing source fields changed')
            for key in base:
                if key not in ('position_xy_m', 'body_vertices_xy_m'):
                    require(base[key] == changed[key],
                            'Opposing condition changed beyond position: ' + key)
            points = [(base['position_xy_m'], changed['position_xy_m'])]
            require(len(base['body_vertices_xy_m']) == len(changed['body_vertices_xy_m']),
                    'Opposing body geometry changed')
            points.extend(zip(base['body_vertices_xy_m'], changed['body_vertices_xy_m']))
            for first, second in points:
                require(math.isclose(second[0] - first[0], -5.0, abs_tol=1e-9) and
                        math.isclose(second[1] - first[1], 0.0, abs_tol=1e-9),
                        'Opposing approach shift is not constant 5 m')

    compare(far, closer)
    changed = json.loads(json.dumps(closer))
    changed[0]['oncoming']['position_xy_m'][0] += 1
    try:
        compare(far, changed)
    except ValueError as exc:
        require('Opposing approach shift is not constant 5 m' in str(exc),
                'Tampered opposing negative failed elsewhere')
    else:
        raise ValueError('Changed opposing position passed 3 s/4 s comparison')
    require(proof['ego_turn_start_frame'] == 38074 and
            proof['opposing_entry_frame'] == 38129 and
            3.9 < proof['measured_time_to_conflict_s'] < 4.0,
            '3 s full-history release observation changed')
    receipt = {
        'selected_4s_case_id': ROOT.name + '__approaching_far',
        'draft_3s_case_id': proof['case_id'],
        'selected_4s_source_sha256': sha(SOURCE / 'interaction_history.jsonl'),
        'selected_4s_audit_sha256': sha(SOURCE / 'far-diagnostic-audit.json'),
        'draft_3s_source_sha256': sha(near / 'interaction_history.jsonl'),
        'proof_script_sha256': sha(Path(__file__)),
        'matched_frames': 900,
        'declared_opposing_shift_m': -5.0,
        'fixed_ego_reciprocal_geometry_and_frame_evidence': True,
        'changed_opposing_position_rejected': True,
        'native_or_legal_acceptance_claimed': False,
    }
    index['release3_4_fixed_trajectory_comparison'] = receipt
    INDEX.write_text(json.dumps(index, indent=2) + '\n')
    return receipt


def prove_physical_lifecycle_diagnostics():
    """Exercise source-bound classifier negatives and ordered capture lifecycle."""
    index = json.loads(INDEX.read_text())
    cases = (
        ('release3_full_history_diagnostic',
         REPO / '.runtime-work/c109749-release3-full-history-v2/attempt',
         'approaching_release_3s'),
        ('release5_full_history_diagnostic',
         REPO / '.runtime-work/c109749-release5-full-history-v1/attempt',
         'approaching_release_5s'),
    )
    output = {}
    for key, source, suffix in cases:
        prior = index[key]
        for name, digest in prior['source_hashes'].items():
            require((source / name).is_file() and sha(source / name) == digest,
                    'Sealed physical fixture source changed: ' + name)
        bundle = ROOT / 'cases' / suffix / 'construction.json'
        require(sha(bundle) == prior['construction_sha256'],
                'Physical fixture construction changed')
        saved = ROOT / 'cases' / suffix / 'draft-proofs/primary/processing.json'
        candidate = next(row for row in index['cases'] if row['case_id'] == prior['case_id']
                         and row['candidate'] == 'primary')
        require(sha(saved) == candidate['saved_receipt_sha256'],
                'Current recorded-only saved-processing receipt changed')
        processing = json.loads(saved.read_text())
        require(processing['passed'] is True and processing['recorded_only'] is True and
                processing['analysis_revision']['construction_sha256'] == sha(bundle),
                'Saved processing does not bind exact construction')
        statuses = {}
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            with tempfile.TemporaryDirectory(prefix='c109749-release-physical-',
                                             dir=REPO / '.runtime-work') as temporary:
                attempt = Path(temporary)
                for name in ('config.json', 'interaction_history.jsonl',
                             'intersection_geometry.json', 'video_frames.jsonl', 'trace.jsonl'):
                    shutil.copy2(source / name, attempt / name)
                (attempt / 'acquisition-provenance.json').write_text(json.dumps({
                    'provenance_kind': 'native', 'diagnostic_fixture': True,
                    'scope': 'synthetic CPU classifier fixture only'}) + '\n')
                if kind == 'incomplete_motion':
                    motion = attempt / 'interaction_history.jsonl'
                    rows = [json.loads(line) for line in motion.read_text().splitlines()]
                    for row in rows:
                        row['ego_heading_deg'] = rows[0]['ego_heading_deg']
                    motion.write_text(''.join(json.dumps(row) + '\n' for row in rows))
                elif kind == 'missing_evidence':
                    (attempt / 'interaction_history.jsonl').unlink()
                physical = physical_result(attempt, {
                    'target_checks': [], 'realized_observables': {},
                    'setup_confirmed': False, 'behavior_attempted': False,
                    'maneuver_completed': False})
                status = physical['physical_checks']['maneuver']['status']
                require(status == {'complete_motion': 'met',
                                   'incomplete_motion': 'not_met',
                                   'missing_evidence': 'unverified'}[kind] and
                        physical['diagnostic_fixture'] is True and
                        physical['physical_acceptance_claimed'] is False,
                        'Physical classifier diagnostic changed: ' + kind)
                statuses[kind] = status
        with tempfile.TemporaryDirectory(prefix='c109749-release-lifecycle-',
                                         dir=REPO / '.runtime-work') as temporary:
            attempt = Path(temporary)
            construction = json.loads(bundle.read_text())
            (attempt / 'construction.json').write_bytes(bundle.read_bytes())
            (attempt / 'runner.py').write_text(next(item['content'] for item in
                construction['files'] if item['path'] == 'runner.py'))
            (attempt / 'trace.jsonl').write_text('{"frame":1,"time_s":0.05}\n')
            (attempt / 'video_frames.jsonl').write_text(
                '{"video_frame":0,"carla_frame":1,"time_s":0.05}\n')
            (attempt / 'acquisition-provenance.json').write_text(json.dumps({
                'provenance_kind': 'native', 'diagnostic_fixture': True,
                'scope': 'synthetic lifecycle fixture only'}) + '\n')
            resource = io.StringIO('fixture camera resource')
            resource.close()
            require(resource.closed, 'Fixture camera resource remains open')
            seal = seal_capture(attempt, frames=1,
                restoration={'restored': True, 'fixture_only': True}, errors=[],
                encoder_exit_codes={'fixture_encoder': 0},
                context={'diagnostic_fixture': True})
            exited = record_native_exit(attempt)
            released = acknowledge_owner_release(attempt,
                attempt / 'owner-release.json', True)
            require(exited['capture_seal_sha256'] == sha(attempt / 'capture-seal.json') and
                    released['native_exit_sha256'] == sha(attempt / 'native-exit.json'),
                    'Capture lifecycle hashes differ')
            events = seal['events'] + [exited['event'], released['event'],
                                       processing['events'][0]]
            require(events == ['capture_finished', 'encoders_closed',
                               'restoration_verified', 'native_exit',
                               'owner_released', 'saved_processing_started'],
                    'Release capture lifecycle order differs')
        output[suffix] = {'case_id': prior['case_id'],
            'construction_sha256': sha(bundle),
            'source_history_sha256': prior['source_hashes']['interaction_history.jsonl'],
            'saved_processing_sha256': sha(saved),
            'physical_classifier_statuses': statuses,
            'capture_to_saved_events': events,
            'diagnostic_fixture': True, 'physical_acceptance_claimed': False}
    proof = {'format': 'worker-release-grid-physical-lifecycle-diagnostic',
             'cases': output, 'native_or_legal_acceptance_claimed': False}
    index['physical_lifecycle_diagnostic'] = proof
    INDEX.write_text(json.dumps(index, indent=2) + '\n')
    return proof


def prove_returned_physical():
    """Return exact source-bound outcome/lifecycle receipts for both draft cases."""
    index = json.loads(INDEX.read_text())
    manifest = ROOT / 'hazard-release-draft-manifest.json'
    entries = json.loads(manifest.read_text())['cases']
    source_script = ROOT / 'inside_physical_fixture_proof.py'
    kinds = ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle')
    returned = {}
    for suffix in ('approaching_release_3s', 'approaching_release_5s'):
        entry = next(item for item in entries if item['case_id'].endswith('__' + suffix))
        primary = ROOT / entry['construction']
        require(sha(primary) == entry['construction_sha256'],
                'Draft physical construction changed: ' + suffix)
        candidate = next(item for item in index['cases'] if item['case_id'] == entry['case_id']
                         and item['candidate'] == 'primary')
        require(candidate['construction_sha256'] == sha(primary),
                'Exact draft proof differs from physical construction')
        saved = ROOT / 'cases' / suffix / 'draft-proofs/primary/processing.json'
        require(sha(saved) == candidate['saved_receipt_sha256'],
                'Current saved receipt differs from draft proof')
        folder = ROOT / 'cases' / suffix / 'physical-proofs'
        folder.mkdir(exist_ok=True)
        fixtures = []
        lifecycle = None
        for kind in kinds:
            result_path = folder / (kind + '.json')
            log_path = folder / (kind + '.log')
            command = [str(REPO / '.venv-cpu/bin/python'), str(source_script),
                       '--manifest', str(manifest), '--case', entry['case_id'],
                       '--kind', kind, '--output', str(result_path)]
            if kind == 'lifecycle':
                command.extend(['--saved-receipt', str(saved)])
            process = subprocess.run(command, cwd=REPO, capture_output=True,
                                     text=True, timeout=60)
            log_path.write_text(process.stdout + process.stderr)
            require(process.returncode == 0,
                    'Release physical fixture failed: ' + kind + ' ' + process.stderr[-1000:])
            row = {'command': ' '.join(command), 'exit_code': 0,
                   'log': str(log_path.relative_to(ROOT)), 'log_sha256': sha(log_path),
                   'result': str(result_path.relative_to(ROOT)),
                   'result_sha256': sha(result_path)}
            if kind == 'lifecycle':
                lifecycle = dict(row, events=json.loads(result_path.read_text())['events'])
            else:
                fixtures.append(dict(row, kind=kind))
        receipt = {'format': 'worker-physical-preparation', 'case_id': entry['case_id'],
                   'construction_sha256': entry['construction_sha256'],
                   'fixtures': fixtures, 'lifecycle': lifecycle,
                   'diagnostic_fixture': True, 'physical_acceptance_claimed': False}
        path = folder / 'receipt.json'
        path.write_text(json.dumps(receipt, indent=2) + '\n')
        check = dict(entry, physical_preparation={
            'receipt': str(path.relative_to(ROOT)), 'sha256': sha(path)})
        validate_physical(REPO, ROOT, check)
        returned[suffix] = {'case_id': entry['case_id'],
                            'construction_sha256': entry['construction_sha256'],
                            'receipt': str(path.relative_to(ROOT)),
                            'receipt_sha256': sha(path),
                            'validator_passed': True,
                            'diagnostic_fixture': True,
                            'physical_acceptance_claimed': False}
    index['returned_physical_preparation'] = {
        'format': 'worker-release-grid-returned-physical-preparation',
        'cases': returned, 'native_or_legal_acceptance_claimed': False}
    INDEX.write_text(json.dumps(index, indent=2) + '\n')
    return index['returned_physical_preparation']


def release_delivery(case, output_root, negative_source_root=None):
    """Run a full-duration synthetic delivery audit or missing-camera negative."""
    suffix = case.rsplit('__', 1)[-1]
    require(suffix in ('approaching_release_3s', 'approaching_release_5s'),
            'Exact release-grid delivery case required')
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == case)
    selected_path = ROOT / entry['construction']
    require(sha(selected_path) == entry['construction_sha256'],
            'Selected release construction changed')
    selected = json.loads(selected_path.read_text())
    selected_config = json.loads(next(item['content'] for item in selected['files']
                                      if item['path'] == 'config.json'))
    index = json.loads((ROOT / 'district-integration-draft-proof.json').read_text())['release_source_fixture']
    key = 'release3_full_history_diagnostic' if suffix.endswith('3s') else 'release5_full_history_diagnostic'
    prior = index[key]
    require(prior['case_id'] == case, 'Delivery source does not match exact case')
    source = (REPO / ('.runtime-work/c109749-release3-full-history-v2/attempt'
                     if suffix.endswith('3s') else
                     '.runtime-work/c109749-release5-full-history-v1/attempt'))
    require(json.loads((source / 'config.json').read_text()) == selected_config,
            'Release source config differs from selected construction')
    root = Path(output_root).resolve()
    require((REPO / '.runtime-work').resolve() in root.parents and not root.exists(),
            'Use a fresh ignored release delivery output root')
    attempt = root / 'attempt'
    attempt.mkdir(parents=True)
    if negative_source_root:
        positive_root = Path(negative_source_root).resolve()
        require((positive_root / 'attempt/delivery-diagnostic-audit.json').is_file(),
                'Positive release delivery diagnostic required first')
        source = positive_root / 'attempt'
    for name, digest in prior['source_hashes'].items():
        if negative_source_root and name == 'overview.mkv':
            continue
        original = source / name
        require(original.is_file() and sha(original) == digest,
                'Sealed release delivery source changed: ' + name)
        target = attempt / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, target)
    for name in ('result.json', 'capture-seal.json'):
        shutil.copy2(source / name, attempt / name)
    require(sha(attempt / 'capture-seal.json') == prior['capture_seal_sha256'],
            'Release delivery capture seal changed')
    if negative_source_root:
        for name in ('native-exit.json', 'owner-release.json'):
            shutil.copy2(source / name, attempt / name)
        audit_release(attempt, case, 'diagnostic-job', 1, 'diagnostic-recording',
                      positive_root / 'pixel-review.json',
                      attempt / 'delivery-diagnostic-audit.json',
                      root / 'source-decode.json', diagnostic_selftest=True)
        raise ValueError('Missing sealed overview camera was accepted')
    mapping = [json.loads(line) for line in
               (attempt / 'video_frames.jsonl').read_text().splitlines()]
    history = [json.loads(line) for line in
               (attempt / 'interaction_history.jsonl').read_text().splitlines()]
    require(len(mapping) == len(history) == 900, 'Full release source required')
    trace = attempt / 'converted/trace.json'
    trace.parent.mkdir()
    trace.write_text(json.dumps({'scenes': [
        {'t': round(row['time_s'] * 1000)} for row in mapping]}, indent=2) + '\n')
    sources = {name: attempt / (name + '.mkv') for name in CAMERAS}
    compose_four_views(sources, attempt / 'video_frames.jsonl', attempt / 'raw.mkv')
    (attempt / 'native-exit.json').write_text(json.dumps({
        'event': 'native_exit', 'capture_seal_sha256': sha(attempt / 'capture-seal.json')},
        indent=2) + '\n')
    (attempt / 'owner-release.json').write_text(json.dumps({
        'event': 'owner_released', 'operator_attested': True,
        'native_exit_sha256': sha(attempt / 'native-exit.json'),
        'diagnostic_fixture': True}, indent=2) + '\n')
    samples = (0, 41, 116, 899)
    review = {'case_id': case, 'reviewer': 'synthetic CPU fixture generator',
              'method': 'static test-pattern ROI; no actor identity or real visibility assertion',
              'frame_map_sha256': sha(attempt / 'video_frames.jsonl'),
              'source_sha256': {name: sha(path) for name, path in sources.items()},
              'observations': [
                  {'camera': name, 'video_frame': frame, 'actor': role,
                   'actor_id': history[frame][role]['actor_id'],
                   'bbox_xyxy': [0, 0, 100, 100]}
                  for name in CAMERAS for frame in samples
                  for role in ('ego', 'oncoming', 'reciprocal')]}
    (root / 'pixel-review.json').write_text(json.dumps(review, indent=2) + '\n')
    receipt = audit_release(attempt, case, 'diagnostic-job', 1,
                            'diagnostic-recording', root / 'pixel-review.json',
                            attempt / 'delivery-diagnostic-audit.json',
                            root / 'source-decode.json', diagnostic_selftest=True)
    require(receipt['passed'] is False and receipt['software_checks_passed'] is True and
            receipt['diagnostic_fixture'] is True and receipt['frames'] == 900,
            'Release diagnostic audit claimed physical acceptance or incomplete source')
    return {'case_id': case, 'frames': 900, 'software_checks_passed': True,
            'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
            'audit_sha256': sha(attempt / 'delivery-diagnostic-audit.json')}


def prove_delivery_contracts(tag='v2'):
    """Return exact positive/negative logs and pinned handoff contracts."""
    require(tag.replace('-', '').isalnum() and '/' not in tag,
            'Simple ignored diagnostic output tag required')
    index = json.loads(INDEX.read_text())
    manifest = json.loads((ROOT / 'hazard-release-draft-manifest.json').read_text())
    script = ROOT / 'release_grid_delivery_audit.py'
    checked = {}
    for suffix in ('approaching_release_3s', 'approaching_release_5s'):
        entry = next(item for item in manifest['cases'] if item['case_id'].endswith('__' + suffix))
        case = entry['case_id']
        label = '3s' if suffix.endswith('3s') else '5s'
        positive_root = REPO / ('.runtime-work/c109749-release-' + label + '-delivery-' + tag)
        negative_root = REPO / ('.runtime-work/c109749-release-' + label + '-delivery-negative-' + tag)
        command = [str(REPO / '.venv-cpu/bin/python'), str(ROOT / 'prove_release5_full_history.py'),
                   '--delivery-case', case, '--delivery-output-root', str(positive_root)]
        negative = command[:]
        negative[-1] = str(negative_root)
        negative += ['--negative-source-root', str(positive_root)]
        folder = ROOT / 'cases' / suffix
        positive_log = folder / 'delivery-positive.log'
        negative_log = folder / 'delivery-negative.log'
        first = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=240)
        positive_log.write_text(first.stdout + first.stderr)
        require(first.returncode == 0, 'Release delivery positive failed: ' + first.stderr[-1200:])
        second = subprocess.run(negative, cwd=REPO, capture_output=True, text=True, timeout=60)
        negative_log.write_text(second.stdout + second.stderr)
        require(second.returncode != 0 and
                'Sealed original source changed: overview.mkv' in negative_log.read_text(),
                'Release missing-camera negative did not reject exact source')
        spec = {'case_id': case, 'sets': ['demo-test', 'full-test'],
                'checks': ['native_source', 'all_participants', 'time_join',
                           'full_video_decode', 'actual_pixels', 'physical_completion'],
                'script': str(script.relative_to(ROOT)), 'script_sha256': sha(script),
                'command': ' '.join(command), 'test_exit_code': 0,
                'test_log': str(positive_log.relative_to(ROOT)),
                'test_log_sha256': sha(positive_log),
                'negative_command': ' '.join(negative),
                'negative_exit_code': second.returncode,
                'negative_expected_error': 'Sealed original source changed: overview.mkv',
                'negative_log': str(negative_log.relative_to(ROOT)),
                'negative_log_sha256': sha(negative_log)}
        validate_delivery_case(ROOT, dict(entry, delivery_acceptance=spec),
                               ('demo-test', 'full-test'))
        checked[suffix] = {'contract': spec,
                           'base_auditor_sha256': sha(ROOT / ('far_delivery_audit.py'
                            if label == '3s' else 'approaching_delivery_audit.py')),
                           'diagnostic_audit_sha256': sha(positive_root /
                                'attempt/delivery-diagnostic-audit.json'),
                           'software_checks_passed': True,
                           'physical_acceptance_claimed': False}
    index['release_delivery_contracts'] = {
        'format': 'worker-release-grid-delivery-contracts',
        'cases': checked, 'native_or_legal_acceptance_claimed': False}
    INDEX.write_text(json.dumps(index, indent=2) + '\n')
    return index['release_delivery_contracts']


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--three-output':
        print(json.dumps(prove_three(sys.argv[2]), indent=2))
    elif len(sys.argv) == 2 and sys.argv[1] == '--compare-three-four':
        print(json.dumps(compare_three_four_full_history(), indent=2))
    elif len(sys.argv) == 2 and sys.argv[1] == '--physical':
        print(json.dumps(prove_physical_lifecycle_diagnostics(), indent=2))
    elif len(sys.argv) == 2 and sys.argv[1] == '--return-physical':
        print(json.dumps(prove_returned_physical(), indent=2))
    elif len(sys.argv) == 2 and sys.argv[1] == '--return-delivery':
        print(json.dumps(prove_delivery_contracts(), indent=2))
    elif len(sys.argv) == 4 and sys.argv[1] == '--return-delivery' and sys.argv[2] == '--delivery-tag':
        print(json.dumps(prove_delivery_contracts(sys.argv[3]), indent=2))
    elif len(sys.argv) in (5, 7) and sys.argv[1] == '--delivery-case' and sys.argv[3] == '--delivery-output-root':
        source_root = None
        if len(sys.argv) == 7:
            require(sys.argv[5] == '--negative-source-root', 'Expected negative source root')
            source_root = sys.argv[6]
        print(json.dumps(release_delivery(sys.argv[2], sys.argv[4], source_root), indent=2))
    elif len(sys.argv) == 1:
        print(json.dumps(prove_independent_delivery_sequences(), indent=2))
    else:
        raise SystemExit('Usage: prove_release5_full_history.py [--three-output .runtime-work/FRESH_ROOT | --compare-three-four | --physical | --return-physical | --return-delivery [--delivery-tag FRESH] | --delivery-case ID --delivery-output-root FRESH [--negative-source-root POSITIVE]]')
