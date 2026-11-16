"""Prove a 900-frame synthetic yield-then-turn source path for the 5 s draft.

The four cameras are diagnostic patterns without actor depiction. The proof
exercises source joins, finalization, decode and negatives, never Native motion.
"""
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))

from approaching_delivery_audit import CAMERAS, validate_originals
from approaching_yield_observation import observe
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


if __name__ == '__main__':
    print(json.dumps(prove(), indent=2))
