"""Independent saved-source delivery audit; diagnostic fixtures never count as acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
REQUIRED = ('original-lamp-source/source-packet.json',
            'original-lamp-source/context.json',
            'original-lamp-source/lamp-trace.jsonl',
            'original-lamp-source/source-receipt.json',
            'trace.jsonl', 'video_frames.jsonl')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def audit(case, attempt, processed):
    attempt, processed = Path(attempt), Path(processed)
    for name in REQUIRED:
        if not (attempt / name).is_file():
            raise ValueError('sealed original missing or changed: ' + name)
    packet = json.loads((attempt / REQUIRED[0]).read_text())
    if packet.get('case_id') != case:
        raise ValueError('original case identity differs')
    context = json.loads((attempt / REQUIRED[1]).read_text())
    receipt = json.loads((attempt / REQUIRED[3]).read_text())
    if context.get('case_id') != case or receipt.get('case_id') != case:
        raise ValueError('source context or receipt case differs')
    if receipt.get('context_sha256') != sha(attempt / REQUIRED[1]) or receipt.get('trace_sha256') != sha(attempt / REQUIRED[2]):
        raise ValueError('sealed original missing or changed: lamp source receipt')
    trace, lamps, frame_map = rows(attempt / 'trace.jsonl'), rows(attempt / REQUIRED[2]), rows(attempt / 'video_frames.jsonl')
    if not trace or len(trace) != len(lamps) or len(trace) != len(frame_map):
        raise ValueError('all participants and complete frame time join absent')
    for i, (vehicle, lamp, frame) in enumerate(zip(trace, lamps, frame_map)):
        if lamp.get('carla_frame') != vehicle.get('frame') or frame.get('carla_frame') != vehicle.get('frame') or frame.get('video_frame') != i:
            raise ValueError('original frame identity or video time join differs')
    for view in VIEWS:
        source = attempt / (view + '.mkv')
        if not source.is_file():
            raise ValueError('original camera pixels missing: ' + view)
        probe = subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
            '-show_entries','stream=width,height,nb_read_frames','-of','json',str(source)],
            capture_output=True,text=True,check=True)
        stream = json.loads(probe.stdout)['streams'][0]
        if int(stream['nb_read_frames']) != len(trace) or int(stream['width']) < 1 or int(stream['height']) < 1:
            raise ValueError('full original video decode or pixels incomplete: ' + view)
    processing = json.loads((processed / 'processing.json').read_text())
    if processing.get('case_id') != case or not processing.get('passed') or processing.get('recorded_only') is not True:
        raise ValueError('saved processing is missing or selected another case')
    for name in REQUIRED:
        if processing.get('original_source_hashes', {}).get(name) != sha(attempt / name):
            raise ValueError('sealed original missing or changed: ' + name)
    native = not (attempt / 'fixture-provenance.json').exists()
    if native and not (attempt / 'capture-seal.json').is_file():
        raise ValueError('Native capture seal required')
    return {'format':'worker-delivery-audit','case_id':case,'checks':['native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion'],
        'source_hashes':{name:sha(attempt/name) for name in REQUIRED},'decoded_frames':len(trace),
        'processed_sha256':sha(processed/'processing.json'),'diagnostic_fixture':not native,
        'physical_completion':'requires independent original capture review' if native else 'unverified_synthetic',
        'accepted':False,'legal_verdict_claimed':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',required=True)
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--processed',required=True)
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    result = audit(args.case,args.attempt,args.processed)
    Path(args.output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'case_id':args.case,'decoded_frames':result['decoded_frames'],'diagnostic_fixture':result['diagnostic_fixture'],'accepted':False},sort_keys=True))

if __name__ == '__main__':
    main()
