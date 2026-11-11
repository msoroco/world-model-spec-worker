"""Independent exact turn source, decode and Native visibility audit."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime'))
from scenario_pipeline.worker_exchange import media

PREFIX = 'heldout__C109705__NRS-484B-400-3__motor_vehicle_driver__'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('turn_road_geometry.json', 'body_footprints.jsonl',
           'video_frames.jsonl', 'trace.jsonl')


def digest(path):return sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _visibility(root, case, cameras, frames):
    path = root / 'turn-pixel-review.json'
    if not path.is_file():raise ValueError('Independent original turn pixel review missing')
    review = json.loads(path.read_text())
    if review.get('case_id') != case or not review.get('reviewer'):
        raise ValueError('Original turn pixel review identity incomplete')
    for subject in ('ego_body', 'approach_centerline', 'destination_left_curb'):
        item = review.get('visible', {}).get(subject, {})
        camera = item.get('camera'); frame = item.get('video_frame')
        if (camera not in cameras or item.get('camera_sha256') != cameras[camera]['video_sha256']
                or not isinstance(frame, int) or frame < 0 or frame >= frames
                or item.get('observed') is not True):
            raise ValueError('Original turn pixel evidence missing: ' + subject)
    return {'path': path.name, 'sha256': digest(path), 'reviewer': review['reviewer']}


def audit(case, attempt, *, report_path=None, diagnostic_fixture=False):
    root = Path(attempt)
    report_path = Path(report_path) if report_path else root / 'analysis-report.json'
    config = json.loads((root / 'config.json').read_text())
    report = json.loads(report_path.read_text())
    result = json.loads((root / 'result.json').read_text())
    if (not case.startswith(PREFIX) or config.get('selected_case_id') != case
            or report.get('case_id') != case or result.get('case_id') != case):
        raise ValueError('Exact turn audit case identity differs')
    observed = report['measurements']['turn_original_position']['value']
    if observed != result['measured_values']['turn_original_position']:
        raise ValueError('Saved turn measurement/report differs')
    for name in SOURCES[:3]:
        if observed['source_sha256'].get(name) != digest(root / name):
            raise ValueError('Original turn source hash differs: ' + name)
    frames = _rows(root / 'video_frames.jsonl')
    bodies = _rows(root / 'body_footprints.jsonl')
    trace = _rows(root / 'trace.jsonl')
    if not frames or len(frames) != len(bodies) or len(frames) != len(trace):
        raise ValueError('Original turn body/time join incomplete')
    if any(frame['carla_frame'] != body['frame'] or frame['carla_frame'] != state['frame']
           or abs(frame['time_s'] - body['time_s']) > 1e-6
           or abs(frame['time_s'] - state['time_s']) > 1e-6
           for frame, body, state in zip(frames,bodies,trace)):
        raise ValueError('Original turn body/time join differs')
    mapping_sha = digest(root / 'video_frames.jsonl')
    cameras = {name: media.audit(root / (name+'.mkv'),len(frames),
                               mapping_sha256=mapping_sha,
                               receipt=root / ('turn-source-decode-'+name+'.json'))
               for name in CAMERAS}
    composed = media.audit(root / 'raw.mkv',len(frames),mapping_sha256=mapping_sha,
                           receipt=root / 'turn-source-decode-primary.json')
    review = None
    if diagnostic_fixture:
        if not (root/'fixture-provenance.json').is_file() or (root/'capture-seal.json').exists():
            raise ValueError('Diagnostic turn audit requires marked unsealed fixture')
    else:
        seal_path=root/'capture-seal.json';exit_path=root/'native-exit.json'
        if not seal_path.is_file() or not exit_path.is_file():
            raise ValueError('Native turn closure and owner exit missing')
        seal=json.loads(seal_path.read_text());owner=json.loads(exit_path.read_text())
        if (seal.get('provenance_kind')!='native'
                or seal.get('restoration',{}).get('restored') is not True
                or owner.get('event')!='native_exit'
                or owner.get('capture_seal_sha256')!=digest(seal_path)
                or any(seal.get('sources',{}).get(name)!=digest(root/name) for name in SOURCES)):
            raise ValueError('Native turn source closure differs')
        if result.get('physical_checks',{}).get('maneuver',{}).get('status')!='met':
            raise ValueError('Native physical left turn unverified')
        review=_visibility(root,case,cameras,len(frames))
    return {'format':'worker-delivery-audit','case_id':case,
        'scope':'synthetic turn software diagnostic' if diagnostic_fixture else 'source-bound Native left turn',
        'original_sha256':{name:digest(root/name) for name in SOURCES},
        'frames':len(frames),'cameras':cameras,
        'source_decode_receipt_path':str(root/'turn-source-decode-primary.json'),
        'source_decode_receipt_sha256':digest(root/'turn-source-decode-primary.json'),
        'source_decode_auditor_sha256':composed['auditor_sha256'],
        'pixel_review':review,
        'checks':{'native_source':not diagnostic_fixture,'time_join':True,
                  'full_video_decode':True,'actual_pixels':review is not None,
                  'physical_completion':not diagnostic_fixture},
        'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True)
    parser.add_argument('--attempt',required=True);parser.add_argument('--report')
    parser.add_argument('--diagnostic-fixture',action='store_true');args=parser.parse_args()
    print(json.dumps(audit(args.case,args.attempt,report_path=args.report,
                           diagnostic_fixture=args.diagnostic_fixture),indent=2))


if __name__=='__main__':main()
