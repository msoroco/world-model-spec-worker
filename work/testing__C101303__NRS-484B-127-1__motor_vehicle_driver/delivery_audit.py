"""Independent source audit for C101303 Native delivery attempts.

Copy this file to state/operations/worker_exchange/<batch>/delivery_audit.py for
local execution. Diagnostic fixtures are rejected as physical delivery sources.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

REPO = next((parent for parent in Path(__file__).resolve().parents
             if (parent/'runtime/scenario_pipeline').is_dir()), None)
if REPO is None:
    raise RuntimeError('Cannot locate pinned scenario runtime')
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange import media

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def lines(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing original source: ' + path.name)
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError('Empty original source: ' + path.name)
    return rows


def validate_join(frame_map, history, trace, case_id, *, expected_frames):
    mapping, motion, captured = lines(frame_map), lines(history), lines(trace)
    if len(mapping) != expected_frames or len(motion) != expected_frames or len(captured) != expected_frames:
        raise ValueError('Original source frame count differs from planned capture')
    frames = []
    participant_ids = None
    for index, (frame, row, source) in enumerate(zip(mapping, motion, captured)):
        native = frame.get('carla_frame', frame.get('native_frame'))
        if frame.get('video_frame') != index or row.get('frame') != native or source.get('frame') != native:
            raise ValueError('Original frame/time join differs')
        time_s = frame.get('time_s')
        if not isinstance(time_s, (int, float)) or not math.isfinite(time_s) or any(
                abs(other.get('time_s', float('inf')) - time_s) > 1e-3 for other in (row, source)):
            raise ValueError('Original frame/time join differs')
        ids = row.get('traffic_actor_ids')
        if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
            raise ValueError('Missing complete participant inventory')
        participants = [row.get('ego'), row.get('lead'), *(row.get('other_participants') or [])]
        if not all(isinstance(actor, dict) and actor.get('actor_id') in ids for actor in participants):
            raise ValueError('Missing complete participant bodies')
        if {actor['actor_id'] for actor in participants} != set(ids):
            raise ValueError('Missing complete participant bodies')
        for actor in participants:
            vertices, velocity = actor.get('body_vertices_xy_m'), actor.get('velocity_mps')
            if (not isinstance(vertices, list) or len(vertices) < 4
                    or not isinstance(velocity, list) or len(velocity) != 3
                    or any(len(v) != 2 or not all(math.isfinite(float(x)) for x in v)
                           for v in vertices)
                    or not all(math.isfinite(float(x)) for x in velocity)):
                raise ValueError('Missing complete participant bodies')
        if participant_ids is None:
            participant_ids = set(ids)
        elif set(ids) != participant_ids:
            raise ValueError('Participant inventory changed during capture')
        frames.append(native)
    if frames != sorted(set(frames)):
        raise ValueError('Original frames are repeated or unordered')
    if case_id and any(row.get('case_id', case_id) != case_id for row in captured):
        raise ValueError('Trace case differs from exact delivery case')
    return {'frames': len(frames), 'participant_ids': sorted(participant_ids),
            'frame_map_sha256': sha(frame_map), 'history_sha256': sha(history),
            'native_trace_sha256': sha(trace)}


def pixel_checker(samples, *, width, height):
    """Check reviewed actor ROIs against decoded RGB bytes at sampled frames.

    A review row identifies an actor and camera; contrast is a pixel sanity check,
    while the named actor remains a human review claim for local acceptance.
    """
    pending = {}
    for row in samples:
        pending.setdefault(int(row['video_frame']), []).append(row)
    if not pending:
        raise ValueError('Missing actual-pixel review samples')
    seen = set()

    def inspect(frame):
        if frame.width != width or frame.height != height:
            raise ValueError('Reviewed camera dimensions differ')
        rows = pending.get(frame.index)
        if rows is None:
            return
        for row in rows:
            box = row.get('bbox_xyxy')
            if (not isinstance(box, list) or len(box) != 4 or
                    not all(type(n) is int for n in box)):
                raise ValueError('Missing reviewed actor pixel box')
            x0, y0, x1, y1 = box
            if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height and
                    (x1-x0)*(y1-y0) >= 16):
                raise ValueError('Reviewed actor pixel box outside source')
            values = set()
            for y in range(y0, y1):
                for x in range(x0, x1):
                    offset = 3*(y*width+x)
                    values.add(frame.pixels[offset:offset+3])
                    if len(values) > 2:
                        break
                if len(values) > 2:
                    break
            if len(values) < 2 or values == {b'\x00\x00\x00'}:
                raise ValueError('Reviewed actor ROI has no visible pixel detail')
        seen.add(frame.index)

    def finish():
        if seen != set(pending):
            raise ValueError('Reviewed actor pixel frame was not decoded')
    return inspect, finish


def audit_attempt(attempt, case_id, job_id, attempt_number, recording_id, review_path,
                  output, decode_receipt):
    attempt, output, decode_receipt = Path(attempt).resolve(), Path(output).resolve(), Path(decode_receipt).resolve()
    if output.name == 'result.json' or attempt in output.parents or attempt in decode_receipt.parents:
        raise ValueError('Keep independent audit outputs outside original attempt')
    result = read(attempt/'result.json')
    if result.get('case_id') != case_id or result.get('provenance_kind') != 'native' or result.get('diagnostic_fixture') is not False:
        raise ValueError('Native non-diagnostic result required')
    if result.get('physical_acceptance_claimed') is not False:
        raise ValueError('Native result asserted premature physical acceptance')
    seal = read(attempt/'capture-seal.json')
    if seal.get('format') != 'worker-sealed-capture' or seal.get('provenance_kind') != 'native' or seal.get('diagnostic_fixture'):
        raise ValueError('Native capture seal required')
    for name, digest in seal.get('sources', {}).items():
        source = (attempt/name).resolve()
        if attempt not in source.parents or not source.is_file() or sha(source) != digest:
            raise ValueError('Sealed original source changed: '+name)
    if read(attempt/'native-exit.json').get('capture_seal_sha256') != sha(attempt/'capture-seal.json'):
        raise ValueError('Native exit does not bind capture seal')
    owner = read(attempt/'owner-release.json')
    if owner.get('operator_attested') is not True or owner.get('native_exit_sha256') != sha(attempt/'native-exit.json'):
        raise ValueError('Owner release does not bind Native exit')
    joined = validate_join(attempt/'video_frames.jsonl', attempt/'vehicle_history.jsonl',
                           attempt/'trace.jsonl', case_id, expected_frames=seal['frames'])
    config = read(attempt/'config.json')
    if joined['frames'] != config['rate_hz']*config['duration_s']:
        raise ValueError('Original sources do not cover full planned duration')
    physical = result.get('physical_checks', {})
    if physical.get('setup', {}).get('status') != 'met' or physical.get('maneuver', {}).get('status') != 'met':
        raise ValueError('Physical completion absent from Native source assessment')
    if not result.get('realized_observables'):
        raise ValueError('Physical completion lacks realized source observations')
    sources = {name: attempt/(name+'.mkv') for name in CAMERAS}
    media.check_four_view_sources(sources)
    review = read(review_path)
    if not review.get('reviewer') or not review.get('method') or review.get('case_id') != case_id:
        raise ValueError('Independent pixel review missing')
    if review.get('frame_map_sha256') != joined['frame_map_sha256'] or review.get('source_sha256') != {name:sha(path) for name,path in sources.items()}:
        raise ValueError('Independent pixel review source binding changed')
    observations = review.get('observations', [])
    if (not observations or not {'ego','lead'} <= {x.get('actor') for x in observations}
            or not set(joined['participant_ids']) <= {x.get('actor_id') for x in observations}):
        raise ValueError('Independent pixel review omits a participant')
    from worker_exchange.capture import PROFILE
    dimensions = {'overview': PROFILE['overview'], **{name:size for name,size in zip(CAMERAS[1:],PROFILE['detail_views'])}}
    for name, path in sources.items():
        sample = [x for x in observations if x.get('camera') == name]
        if not sample:
            raise ValueError('Independent pixel review omits camera: '+name)
        inspect, finish = pixel_checker(sample,width=dimensions[name][0],height=dimensions[name][1])
        media.audit(path, joined['frames'], checkers={'reviewed_actor_pixels':(sha(Path(__file__)),inspect)},
                    mapping_sha256=joined['frame_map_sha256'])
        finish()
    video = attempt/'raw.mkv'
    decoded = media.audit(video, joined['frames'],mapping_sha256=joined['frame_map_sha256'],receipt=decode_receipt)
    trace = attempt/'converted/trace.json'
    scenes = read(trace)['scenes']
    if len(scenes) != joined['frames'] or any(scene['t'] != round(frame['time_s']*1000)
            for scene,frame in zip(scenes,lines(attempt/'video_frames.jsonl'))):
        raise ValueError('Core trace/original frame time join differs')
    audit = {'format':'worker-delivery-audit','passed':True,'case_id':case_id,
             'job_id':job_id,'attempt':attempt_number,'recording_id':recording_id,
             'checks':{key:True for key in CHECKS},'frames':joined['frames'],
             'source_result_sha256':sha(attempt/'result.json'),
             'video':'raw.mkv','video_sha256':sha(video),'trace':'converted/trace.json',
             'trace_sha256':sha(trace),'auditor_path':str(Path(__file__).resolve()),
             'auditor_sha256':sha(Path(__file__)),
             'source_decode_receipt_path':str(decode_receipt),
             'source_decode_receipt_sha256':sha(decode_receipt),
             'source_decode_auditor_sha256':decoded['auditor_sha256'],
             'original_sources':joined,'pixel_review_sha256':sha(review_path)}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(audit,indent=2)+'\n')
    return audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--job-id',required=True)
    parser.add_argument('--attempt-number',type=int,required=True)
    parser.add_argument('--recording-id',required=True)
    parser.add_argument('--pixel-review',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--decode-receipt',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(audit_attempt(args.attempt,args.case,args.job_id,args.attempt_number,
          args.recording_id,args.pixel_review,args.output,args.decode_receipt),sort_keys=True))


if __name__ == '__main__':
    main()
