"""Independent raw-source audit of current C10316 diagnostic saved attempts.

This does not import the Native measurement/finalizer implementation. It checks
the serialized sources and measurements, and never certifies physical or legal
acceptance from synthetic fixtures.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
SOURCES = ('trace.jsonl', 'capture/evidence.jsonl', 'video_frames.jsonl',
           'native_samples.jsonl', 'capture/native/frames.jsonl')


class AuditFailure(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AuditFailure(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def output(suffix, candidate):
    if suffix == 'reference' and candidate == 'primary':
        return ROOT/'.runtime-work/c10316-v15-reference-compat-primary-final'
    return ROOT/'.runtime-work'/f'c10316-v15-{suffix}-compat-{candidate}'


def audit_attempt(folder, data=None):
    data = data or {name: lines(folder/name) for name in SOURCES}
    sample = data['native_samples.jsonl']
    frame_map = data['video_frames.jsonl']
    trace = data['trace.jsonl']
    evidence = data['capture/evidence.jsonl']
    native = data['capture/native/frames.jsonl']
    require(all(len(data[name]) == 240 for name in SOURCES), '240 original rows required')
    context = read(folder/'crosswalk-context.json')
    require(context['source_kind'] == 'synthetic_scene_request', 'diagnostic source mislabeled')
    require(all(f.get('observed') is None for f in context['practicability_facts']),
            'synthetic practicability fact claimed observed')
    cx, cy = context['crosswalk_center_xy_m']
    fx, fy = context['crosswalk_passage_forward_xy']
    rx, ry = fy, -fx
    half_length = context['crosswalk_length_m']/2
    half_width = context['crosswalk_width_m']/2
    counts = {'right': 0, 'left': 0, 'center_or_straddling': 0}
    inside_frames = []
    first_frame = frame_map[0]['native_frame']
    for index, (s, m, t, e, n) in enumerate(zip(sample, frame_map, trace, evidence, native)):
        frame = first_frame+index
        time = index/20
        require(s['native_frame'] == m['native_frame'] == m['carla_frame'] ==
                t['frame'] == e['original_frame'] == n['frame'] == frame,
                f'original frame join failed at {index}')
        require(m['video_frame'] == index and all(abs(value-time) < 1e-4 for value in
                (s['time_s'], m['time_s'], t['time_s'], e['recording_time_s'])),
                f'original time/video join failed at {index}')
        require(s['crosswalk_id'] == context['crosswalk_id'], 'crosswalk identity changed')
        require(e['ego']['speed_provenance'] == 'synthetic_native_sample' and
                e['synthetic_diagnostic'] is True and t['synthetic_diagnostic'] is True,
                'synthetic speed provenance omitted')
        px, py = s['pedestrian_xy_m']
        require(math.dist((px, py), tuple(e['ego']['position_m'][:2])) < 1e-6 and
                math.dist((px, py), tuple(t['position_m'][:2])) < 1e-6,
                'pedestrian pose differs from original trace/evidence')
        require(len(s['pedestrian_footprint_xy_m']) == 4, 'four footprint corners required')
        original_corners = {(round(v[0], 3), round(v[1], 3))
                            for v in e['ego']['body_vertices_m']}
        sample_corners = {(round(v[0], 3), round(v[1], 3))
                          for v in s['pedestrian_footprint_xy_m']}
        require(len(sample_corners) == 4 and original_corners == sample_corners,
                'pedestrian footprint differs from original evidence')
        projected = [((x-cx)*fx+(y-cy)*fy, (x-cx)*rx+(y-cy)*ry)
                     for x, y in s['pedestrian_footprint_xy_m']]
        if all(abs(u) <= half_length+1e-6 and abs(v) <= half_width+1e-6
               for u, v in projected):
            inside_frames.append(frame)
            lateral = [v for _, v in projected]
            label = ('right' if all(v > .01 for v in lateral) else
                     'left' if all(v < -.01 for v in lateral) else
                     'center_or_straddling')
            counts[label] += 1
    require(len(inside_frames) >= 60, 'insufficient crosswalk passage')
    report = read(folder/'analysis-report.json')
    result = read(folder/'result.json')
    require(result['accepted'] is False and result['legal_verdict_claimed'] is False and
            result['maneuver_completed'] is False and
            result['provenance_kind'] == 'synthetic_local_diagnostic',
            'diagnostic result claimed physical or legal acceptance')
    expected = 'right' if 'reference' in result['case_id'] else 'left'
    require(counts[expected] == len(inside_frames), 'controlled half failed')
    require(result['measured_values']['observed_crosswalk_half'] == expected and
            result['measured_values']['crosswalk_frames'] == len(inside_frames),
            'reported result differs from independent footprint count')
    require(report['case_id'] == result['case_id'], 'analysis case differs')
    for item in report['measurements'].values():
        value = item['value']
        require(value['crosswalk_half_counts'] == counts and
                value['crosswalk_frames'] == len(inside_frames) and
                value['crosswalk_first_frame'] == inside_frames[0] and
                value['crosswalk_last_frame'] == inside_frames[-1] and
                value['observed_half'] == expected and
                value['practicability_verified'] is False and
                value['legal_verdict_claimed'] is False,
                'analysis differs from independent footprint count')
        require(all(sha(folder/name) == digest for name, digest in item['sources'].items()),
                'analysis source digest differs')
    require(all(sha(folder/name) == digest for name, digest in
                report['original_joins']['source_hashes'].items()),
            'original join source digest differs')
    return {'case_id': result['case_id'], 'candidate_id': report['candidate_id'],
            'crosswalk_frames': len(inside_frames), 'half_counts': counts,
            'first_frame': first_frame, 'last_frame': frame_map[-1]['native_frame'],
            'source_sha256': {name: sha(folder/name) for name in SOURCES},
            'analysis_sha256': sha(folder/'analysis-report.json'),
            'result_sha256': sha(folder/'result.json')}


def main():
    audited = []
    for candidate in CANDIDATES:
        pair = []
        for suffix in ('reference', 'contrast'):
            folder = output(suffix, candidate)
            audit = audit_attempt(folder)
            require(audit['candidate_id'] == candidate, 'candidate identity differs')
            audited.append(audit)
            pair.append((folder, lines(folder/'native_samples.jsonl'),
                         read(folder/'crosswalk-context.json')))
        reference, contrast = pair
        require(reference[2] == contrast[2], 'paired crosswalk context differs')
        for a, b in zip(reference[1], contrast[1]):
            require(abs(a['pedestrian_xy_m'][0]-b['pedestrian_xy_m'][0]) < 1e-9 and
                    abs(b['pedestrian_xy_m'][1]-a['pedestrian_xy_m'][1]-1.3) < 1e-9 and
                    a['pedestrian_forward_xy'] == b['pedestrian_forward_xy'],
                    'paired pedestrian motion differs beyond lateral shift')
    folder = output('reference', 'primary')
    base = {name: lines(folder/name) for name in SOURCES}
    negatives = []
    for name, mutate in (
        ('frame_join', lambda data: data['video_frames.jsonl'][5].update(native_frame=900)),
        ('footprint', lambda data: data['native_samples.jsonl'][100]['pedestrian_footprint_xy_m'][0].__setitem__(1, 9.0)),
        ('speed_provenance', lambda data: data['capture/evidence.jsonl'][0]['ego'].update(speed_provenance='native')),
    ):
        changed = copy.deepcopy(base)
        mutate(changed)
        try:
            audit_attempt(folder, changed)
        except AuditFailure:
            negatives.append(name)
        else:
            raise AuditFailure('negative was accepted: '+name)
    report = {'format': 'c10316-update015-independent-saved-audit',
              'draft_manifest_sha256': sha(HERE/'draft-execution-manifest.json'),
              'audited': audited, 'controlled_pairs': len(CANDIDATES),
              'rejected_mutations': negatives,
              'scope': 'synthetic source and measurement consistency; no Native or legal acceptance'}
    target = HERE/'update015-saved-evidence-audit.json'
    target.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'passed': True, 'attempts': len(audited),
                      'controlled_pairs': len(CANDIDATES), 'rejected_mutations': negatives}))


if __name__ == '__main__':
    main()
