"""Independent source-bound audit for an original signed U-turn delivery.

CPU selftests exercise joins, hashes, decode and rejection only. They never
establish a real official device, visible sign or completed Native maneuver.
"""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

ASSIGNMENT = 'training__C104538__NRS-484B-403-2__motor_vehicle_driver'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, name):
    root = Path(root).resolve()
    path = (root/name).resolve()
    require(root in path.parents and path.is_file(), 'Missing delivery source: '+name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def decode(video, expected=600):
    process = subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
                              '-show_entries','stream=nb_read_frames','-of','json',str(video)],
                             text=True,capture_output=True)
    require(process.returncode == 0, 'Full video decode failed')
    streams = json.loads(process.stdout).get('streams', [])
    require(len(streams) == 1 and int(streams[0].get('nb_read_frames',0)) == expected,
            'Full video frame count differs')
    return {'path':str(video),'sha256':sha(video),'frames':expected}


def check_sources(attempt, case, diagnostic=False):
    require(case in (ASSIGNMENT+'__witness_1',ASSIGNMENT+'__witness_2'), 'Wrong delivery case')
    attempt = Path(attempt)
    trace = source(attempt,'trace.jsonl')
    mapping = source(attempt,'video_frames.jsonl')
    native = source(attempt,'native_samples.jsonl')
    review = source(attempt,'sign-review.json')
    pixel_marks = source(attempt,'pixel_review.jsonl')
    trace_rows, map_rows, native_rows, marks = map(rows,(trace,mapping,native,pixel_marks))
    require(len(trace_rows)==len(map_rows)==len(native_rows)==600, 'Native/time join incomplete')
    for index,(t,m,n) in enumerate(zip(trace_rows,map_rows,native_rows)):
        require(m.get('video_frame')==index and m.get('carla_frame')==t.get('frame')==n.get('native_frame')
                and abs(t['time_s']-m['time_s'])<1e-6 and abs(n['time_s']-m['time_s'])<1e-6,
                'Native/time join differs')
    packet=json.loads(review.read_text())
    require(packet.get('native_samples_sha256')==sha(native) and
            packet.get('frame_map_sha256')==sha(mapping) and
            packet.get('pixel_review_sha256')==sha(pixel_marks), 'Original review source hash differs')
    require(packet.get('sign_code')=='no_u_turn' and packet.get('governs_approach') is True,
            'Applicable prohibition device unverified')
    require(marks and all(type(m.get('sign_visible')) is bool and
                          type(m.get('full_body_visible')) is bool for m in marks),
            'Original pixel marks incomplete')
    if diagnostic:
        return {'case_id':case,'diagnostic_fixture':True,'native_join_frames':600,
                'pixel_mark_count':len(marks),'original_native_observed':False,
                'physical_acceptance_claimed':False}
    require(packet.get('source_kind')=='original_camera_sign_review' and
            packet.get('reviewed_from_original_pixels') is True and
            packet.get('official_device_verified') is True,
            'Original official-device pixel/designation review missing')
    cameras={name:decode(source(attempt,name+'.mkv')) for name in VIEWS}
    require(packet.get('video_sha256')==cameras['approach']['sha256'],
            'Original approach pixels differ from review')
    primary=decode(source(attempt,'raw.mkv'))
    result=json.loads(source(attempt,'result.json').read_text())
    require(result.get('case_id')==case and result.get('provenance_kind')!='synthetic_fixture'
            and result.get('maneuver_completed') is True,
            'Original Native physical completion unverified')
    return {'format':'worker-delivery-audit','case_id':case,'passed':True,
            'checks':['native_source','all_participants','time_join','full_video_decode',
                      'actual_pixels','physical_completion'],
            'sources':{name:sha(source(attempt,name)) for name in
                       ('trace.jsonl','video_frames.jsonl','native_samples.jsonl',
                        'sign-review.json','pixel_review.jsonl','result.json')},
            'source_decode_receipts':cameras,'primary_decode_receipt':primary,
            'legal_verdict_claimed':False}


def selftest(case, negative):
    here=Path(__file__).resolve().parents[1]
    suffix=case.rsplit('__',1)[-1]
    package=here/'v2-source'/suffix
    repo=here.parents[1]
    with tempfile.TemporaryDirectory(dir=repo/'.runtime-work',prefix='c104538-audit-') as tmp:
        stage=Path(tmp)
        for name in ('trace.jsonl','video_frames.jsonl','native_samples.jsonl',
                     'sign-review.json','pixel_review.jsonl'):
            (stage/name).write_bytes((package/name).read_bytes())
        if negative:
            (stage/'native_samples.jsonl').unlink()
        result=check_sources(stage,case,diagnostic=True)
        if not negative:
            video=stage/'decode-test.mkv'
            subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','lavfi',
                            '-i','color=c=black:s=64x36:r=20','-frames:v','600','-an',
                            '-c:v','ffv1','-threads','1',str(video)],check=True)
            result['decode']=decode(video)
        return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--attempt')
    parser.add_argument('--selftest',action='store_true')
    parser.add_argument('--negative-selftest',action='store_true')
    args=parser.parse_args()
    if args.selftest or args.negative_selftest:
        result=selftest(args.case,args.negative_selftest)
    else:
        require(args.attempt, 'Original attempt required')
        result=check_sources(args.attempt,args.case)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    main()
