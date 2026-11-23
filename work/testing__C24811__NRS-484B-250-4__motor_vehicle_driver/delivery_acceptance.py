"""Independent C24811 source, motion, and pixel audit; CPU mode is diagnostic only."""
import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange import media  # noqa: E402

CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')
ROLES = ('ego', 'earlier', 'occupant')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing original source: ' + path.name)
    return json.loads(path.read_text())


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing original source: ' + path.name)
    result = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not result:
        raise ValueError('Empty original source: ' + path.name)
    return result


def bind_sources(attempt, sources):
    attempt = Path(attempt).resolve()
    if not isinstance(sources, dict) or not sources:
        raise ValueError('Physical completion sources absent')
    for name, digest in sources.items():
        path = (attempt / name).resolve()
        if attempt not in path.parents or not path.is_file() or sha(path) != digest:
            raise ValueError('Physical completion source changed: ' + name)


def verify_physical(attempt, result):
    if result.get('physical_acceptance_claimed') is not False:
        raise ValueError('Result prematurely claims physical acceptance')
    if not all(result.get(key) is True for key in ('setup_confirmed', 'behavior_attempted', 'maneuver_completed')):
        raise ValueError('Physical setup, behavior, or maneuver unconfirmed')
    for name in ('setup', 'target', 'maneuver'):
        check = result.get('physical_checks', {}).get(name, {})
        if check.get('status') != 'met' or not check.get('method'):
            raise ValueError('Physical completion not source-bound: ' + name)
        bind_sources(attempt, check.get('sources'))


def verify_join(attempt):
    frame_map = rows(attempt / 'video_frames.jsonl')
    history = rows(attempt / 'vehicle_signal_history.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    if len(frame_map) != len(history) or len(history) != len(trace):
        raise ValueError('Original participant/time source lengths differ')
    for index, (frame, vehicle, ego) in enumerate(zip(frame_map, history, trace)):
        original = frame.get('carla_frame')
        if frame.get('video_frame') != index or vehicle.get('frame') != original or ego.get('frame') != original:
            raise ValueError('Original frame identity differs')
        if any(row.get('time_s') != frame.get('time_s') for row in (vehicle, ego)):
            raise ValueError('Original time join differs')
        if any(not isinstance(vehicle.get(role), dict) for role in ROLES):
            raise ValueError('Original three-participant history incomplete')
    return len(frame_map), history


def pixel_checker(samples, width, height):
    pending = {}
    for sample in samples:
        pending.setdefault(sample['video_frame'], []).append(sample)
    seen = set()

    def check(frame):
        if (frame.width, frame.height) != (width, height):
            raise ValueError('Reviewed camera dimensions differ')
        for item in pending.get(frame.index, []):
            box = item.get('bbox_xyxy')
            if not isinstance(box, list) or len(box) != 4 or any(type(v) is not int for v in box):
                raise ValueError('Reviewed actor pixel box missing')
            x0, y0, x1, y1 = box
            if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height and (x1-x0)*(y1-y0) >= 16):
                raise ValueError('Reviewed actor pixel box invalid')
            colors = set()
            for y in range(y0, y1):
                for x in range(x0, x1):
                    offset = 3 * (y*width+x)
                    colors.add(frame.pixels[offset:offset+3])
                    if len(colors) > 1:
                        break
                if len(colors) > 1:
                    break
            if len(colors) < 2:
                raise ValueError('Reviewed actor ROI lacks visible pixel detail')
            seen.add((frame.index, item['role']))

    def finish():
        if seen != {(item['video_frame'], item['role']) for item in samples}:
            raise ValueError('Reviewed actor pixels not decoded')
    return check, finish


def audit_native(attempt, case, pixel_review, output):
    """Prospective local audit. Diagnostic captures cannot pass this function."""
    attempt = Path(attempt).resolve()
    manifest = read(HERE / 'execution-manifest.json')
    entry = next((e for e in manifest['cases'] if e['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unknown exact case')
    seal = read(attempt / 'capture-seal.json')
    if seal.get('provenance_kind') != 'native' or seal.get('diagnostic_fixture') is not False:
        raise ValueError('Native source required')
    if seal.get('restoration', {}).get('restored') is not True or any(v != 0 for v in seal.get('encoder_exit_codes', {}).values()):
        raise ValueError('Capture closure not verified')
    required = {'config.json', 'junction_context.json', 'vehicle_signal_history.jsonl',
                'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl',
                *(name+'.mkv' for name in CAMERAS)}
    sources = seal.get('sources', {})
    if not required <= set(sources):
        raise ValueError('Native capture seal omits original source')
    bind_sources(attempt, sources)
    native_exit = read(attempt / 'native-exit.json')
    owner = read(attempt / 'owner-release.json')
    if native_exit.get('capture_seal_sha256') != sha(attempt/'capture-seal.json') or owner.get('native_exit_sha256') != sha(attempt/'native-exit.json') or owner.get('operator_attested') is not True:
        raise ValueError('Native exit/owner release chain differs')
    result = read(attempt / 'result.json')
    if result.get('case_id') != case or result.get('provenance_kind') != 'native' or result.get('diagnostic_fixture') is not False:
        raise ValueError('Native result identity differs')
    verify_physical(attempt, result)
    frames, history = verify_join(attempt)
    review = read(pixel_review)
    if review.get('case_id') != case or not review.get('reviewer') or review.get('frame_map_sha256') != sha(attempt/'video_frames.jsonl'):
        raise ValueError('Independent pixel review missing or stale')
    observations = review.get('observations', [])
    if {r.get('role') for r in observations} != set(ROLES) or {r.get('camera') for r in observations} != set(CAMERAS):
        raise ValueError('Independent pixel review omits participant or camera')
    config = read(attempt/'config.json')
    cameras = {c['name']:(c['width'],c['height']) for c in config['cameras']}
    for item in observations:
        index = item.get('video_frame')
        if type(index) is not int or not 0 <= index < frames or item.get('actor_id') != history[index][item['role']].get('actor_id'):
            raise ValueError('Independent pixel review actor identity differs')
    for name in CAMERAS:
        subset = [r for r in observations if r['camera'] == name]
        check, finish = pixel_checker(subset, *cameras[name])
        media.audit(attempt/(name+'.mkv'), frames, checkers={'reviewed_actor_pixels':(sha(__file__),check)}, mapping_sha256=sha(attempt/'video_frames.jsonl'))
        finish()
    media.audit(attempt/'raw.mkv', frames, mapping_sha256=sha(attempt/'video_frames.jsonl'))
    receipt = {'format':'worker-c24811-independent-delivery-audit','case_id':case,
               'passed':True,'physical_acceptance_claimed':False,'checks':list(CHECKS),
               'frame_count':frames,'capture_seal_sha256':sha(attempt/'capture-seal.json'),
               'pixel_review_sha256':sha(pixel_review),'auditor_sha256':sha(__file__)}
    output = Path(output).resolve()
    if attempt not in output.parents or output.exists() or output.name == 'result.json':
        raise ValueError('Independent audit receipt must be a new attempt file')
    output.write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def cpu_sweep(case, negative):
    manifest = read(HERE/'execution-manifest.json')
    ids = [e['case_id'] for e in manifest['cases']]
    if case not in ids:
        raise ValueError('Unknown exact case')
    tested = []
    for entry in manifest['cases']:
        construction = HERE/entry['construction']
        physical = HERE/entry['physical_preparation']['receipt']
        compatibility = HERE/entry['compatibility']['receipt']
        if sha(construction) != entry['construction_sha256'] or sha(physical) != entry['physical_preparation']['sha256'] or sha(compatibility) != entry['compatibility']['sha256']:
            raise ValueError('Current exact proof source changed')
        with tempfile.TemporaryDirectory(prefix='c24811-delivery-audit-') as tmp:
            attempt = Path(tmp)
            source = attempt/'vehicle_signal_history.jsonl'
            source.write_text('{"diagnostic_fixture":true}\n')
            check = {'status':'met','method':'source-bound diagnostic boundary test',
                     'sources':{'vehicle_signal_history.jsonl':sha(source)}}
            result = {'physical_acceptance_claimed':False,'setup_confirmed':True,
                      'behavior_attempted':True,'maneuver_completed':True,
                      'physical_checks':{name:check for name in ('setup','target','maneuver')}}
            verify_physical(attempt,result)
            if negative and entry['case_id'] == case:
                source.write_text('{"tampered":true}\n')
                verify_physical(attempt,result)
                raise AssertionError('Changed physical source accepted')
        tested.append(entry['case_id'])
    return {'diagnostic_only':True,'physical_acceptance_claimed':False,
            'cases_checked':tested,'checks':list(CHECKS)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--mode',choices=('positive','negative'),required=True)
    parser.add_argument('--all',action='store_true')
    parser.add_argument('--attempt',type=Path)
    parser.add_argument('--pixel-review',type=Path)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    if args.attempt:
        if args.mode != 'positive' or not args.pixel_review or not args.output:
            raise ValueError('Native audit requires positive mode, pixel review, and output')
        print(json.dumps(audit_native(args.attempt,args.case,args.pixel_review,args.output),sort_keys=True))
    elif args.all:
        print(json.dumps(cpu_sweep(args.case,args.mode=='negative'),sort_keys=True))
    else:
        raise ValueError('Use --all for CPU diagnostic sweep or --attempt for Native audit')
