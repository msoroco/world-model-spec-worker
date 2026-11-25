"""Saved-only qualifier finalizer proof using explicit synthetic sources."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
BASE = ROOT / '.runtime-work/c229397-saved-attempt-controlled_2-v2'
SOURCES = ('diagnostic-input.json', 'acquisition-provenance.json',
           'synthetic-original-review-source.txt', 'crosswalk-inventory.json',
           'crosswalk-source-review.json', 'road.xodr', 'trace.jsonl',
           'video_frames.jsonl', 'vehicle-poses.jsonl', 'control-intent.jsonl',
           'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(suffix, name):
    stem = ('traffic' if suffix == 'traffic_conflict_near' else
            'device' if suffix == 'device_direction_near' else
            'law' if suffix == 'law_compliance_near' else 'officer')
    offline = ROOT / ('.runtime-work/c229397-qualifier-' + stem + '-offline-v5')
    attempt = ROOT / ('.runtime-work/c229397-qualifier-' + stem + '-' + name + '-v7')
    if attempt.exists():
        raise ValueError('Retain existing qualifier finalizer proof')
    shutil.copytree(offline, attempt)
    for source in SOURCES:
        shutil.copyfile(BASE / source, attempt / source)
    shutil.copytree(BASE / 'capture', attempt / 'capture')
    frames = [json.loads(row) for row in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    qualifier = suffix.removesuffix('_near')
    context = {'format': 'c229397-native-qualifier-context-v1',
               'qualifier': qualifier, 'case_suffix': suffix,
               'traffic_actor_requested': stem == 'traffic',
               'device_requested': stem == 'device', 'device_actor_found': False,
               'authority_and_necessity_unresolved': True,
               'diagnostic_fixture': True}
    (attempt / 'qualifier-context.json').write_text(json.dumps(context, indent=2) + '\n')
    role_paths = {}
    if stem == 'traffic':
        path = attempt / 'traffic-actors.jsonl'
        path.write_text(''.join(json.dumps({'video_frame': index,
            'native_frame': frame['native_frame'], 'actor_id': 22,
            'vehicle_xy_m': [-16 + index * .02, -1.75], 'speed_mps': .4}) + '\n'
            for index, frame in enumerate(frames)))
        role_paths['participant_motion'] = path.name
        review_roles = ('traffic_context_review',)
    elif stem == 'device':
        path = attempt / 'device-states.jsonl'
        path.write_text(''.join(json.dumps({'video_frame': index,
            'native_frame': frame['native_frame'], 'device_present': False,
            'device_id': None, 'state': None}) + '\n'
            for index, frame in enumerate(frames)))
        role_paths.update(device_identity='qualifier-context.json', device_state=path.name)
        review_roles = ('direction_context_review',)
    else:
        path = attempt / 'authority-events.jsonl'
        path.write_text(''.join(json.dumps({'video_frame': index,
            'native_frame': frame['native_frame'], 'qualifier': qualifier,
            'candidate_participant_id': 31 if stem == 'officer' else None,
            'authority_status': 'unverified'}) + '\n'
            for index, frame in enumerate(frames)))
        role_paths['authority_timeline'] = path.name
        review_roles = (('applicable_law_text', 'law_context_review') if stem == 'law'
                        else ('officer_identity', 'officer_direction',
                              'direction_context_review'))
    for role in review_roles:
        source = attempt / (role + '.txt')
        source.write_text('Synthetic unresolved diagnostic review: ' + qualifier + '\n')
        role_paths[role] = source.name
    role_paths.update(vehicle_poses='vehicle-poses.jsonl',
                      frame_map='video_frames.jsonl', overview_video='overview.mkv')
    packet = {'format': 'c229397-qualifier-source-packet-v1',
              'case_suffix': suffix, 'qualifier': qualifier,
              'finding': 'unresolved', 'diagnostic_fixture': True,
              'source_kind': 'synthetic_fixture',
              'reviewed_video_frames': [200, 300],
              'sources': {role: {'path': rel, 'sha256': sha(attempt / rel)}
                          for role, rel in role_paths.items()}}
    (attempt / 'qualifier-source-packet.json').write_text(json.dumps(packet, indent=2) + '\n')
    return attempt


def run(attempt, log):
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join((str(ROOT / 'runtime/scenario_pipeline'),
        str(ROOT / 'runtime/python'), env.get('PYTHONPATH', '')))
    result = subprocess.run([sys.executable, str(attempt / 'finalize_delivery.py'),
        '--attempt', str(attempt), '--output', str(attempt / 'analysis-report.json')],
        cwd=attempt, env=env, capture_output=True, text=True)
    log.write_text(result.stdout + result.stderr)
    return result


def main():
    proof = {}
    for suffix, stem in (('traffic_conflict_near', 'traffic'),
                         ('law_compliance_near', 'law'),
                         ('police_direction_near', 'officer'),
                         ('device_direction_near', 'device')):
        positive = prepare(suffix, 'finalizer-positive')
        log = HERE / ('qualifier-' + stem + '-finalizer-positive.log')
        outcome = run(positive, log)
        if outcome.returncode:
            raise ValueError('Positive qualifier finalizer failed: ' + outcome.stderr[-500:])
        report = json.loads((positive / 'analysis-report.json').read_text())
        result = json.loads((positive / 'result.json').read_text())
        if (report['qualifier_source_review']['finding'] != 'unresolved' or
                result['accepted'] is not False or result['legal_verdict_claimed'] is not False):
            raise ValueError('Qualifier finalizer asserted unsupported conclusion')
        negative = prepare(suffix, 'finalizer-negative')
        source = ('traffic-actors.jsonl' if stem == 'traffic' else
                  'device-states.jsonl' if stem == 'device' else
                  'authority-events.jsonl')
        (negative / source).unlink()
        negative_log = HERE / ('qualifier-' + stem + '-finalizer-negative.log')
        rejected = run(negative, negative_log)
        if rejected.returncode == 0 or not any(message in rejected.stderr for message in (
                'Qualifier source missing or stale', 'Missing required source: ' + source)):
            raise ValueError('Missing Native qualifier source accepted')
        proof[suffix] = {'positive_log_sha256': sha(log),
                         'negative_log_sha256': sha(negative_log),
                         'unresolved': True, 'missing_source_rejected': True}
    print(json.dumps({'passed': True, 'diagnostic_fixture': True,
                      'cases': proof, 'legal_verdict_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
