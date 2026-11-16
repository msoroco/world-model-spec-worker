"""Source-bound CPU physical and lifecycle protocol fixtures for six overtaking cases."""
import argparse
import hashlib
import json
from pathlib import Path
from overtake_geometry import measure

HERE = Path(__file__).resolve().parent
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']
CAMERAS = {'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rows(text):
    return [json.loads(line) for line in text.splitlines() if line]


def fixture(case, diagnostic_path, kind):
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown physical fixture kind')
    path = HERE / diagnostic_path
    data = json.loads(path.read_text())
    files = data['files']
    receipt = json.loads(files['overtake_source_receipt.json'])
    if receipt['case_id'] != case:
        raise ValueError('Physical fixture exact case identity differs')
    if {v['path'] for v in data['videos']} != CAMERAS:
        raise ValueError('Physical fixture four-camera inventory differs')
    for name in ('overtake_site_original.json', 'overtake_bodies_original.jsonl',
                 'trace.jsonl', 'video_frames.jsonl'):
        if sha(files[name].encode()) != receipt['source_sha256'][name]:
            raise ValueError('Physical fixture original source hash differs: ' + name)
    bodies = rows(files['overtake_bodies_original.jsonl'])
    trace = rows(files['trace.jsonl'])
    frame_map = rows(files['video_frames.jsonl'])
    if not 3 <= len(bodies) == len(trace) == len(frame_map):
        raise ValueError('Physical fixture original frame count differs')
    for index, (body, motion, mapping) in enumerate(zip(bodies, trace, frame_map)):
        if (body['frame'] != motion['frame'] or body['time_s'] != motion['time_s'] or
                mapping['native_frame'] != body['frame'] or mapping['time_s'] != body['time_s'] or
                mapping['video_frame'] != index):
            raise ValueError('Physical fixture original frame join differs')
    measured = measure(bodies, receipt['ego_actor_id'], receipt['overtaker_actor_id'])
    if measured['first_complete_frame'] is None or measured['post_completion_overlap_recurrence']:
        raise ValueError('Physical fixture complete diagnostic path absent')
    first = next(i for i, sample in enumerate(measured['samples']) if sample['full_body_passed_at_sample'])
    if kind == 'complete_motion':
        status = 'met'
        realized = {'first_complete_frame': measured['first_complete_frame'],
                    'completion_interval_s': measured['completion_interval_s'],
                    'passing_side_at_first_frame': measured['passing_side_at_first_frame'],
                    'original_frames': len(bodies)}
    elif kind == 'incomplete_motion':
        # Explicit CPU mutation: stop the diagnostic at its last not-complete frame.
        shortened = measure(bodies[:first], receipt['ego_actor_id'], receipt['overtaker_actor_id'])
        if shortened['first_complete_frame'] is not None:
            raise ValueError('Truncated physical fixture unexpectedly completed')
        status, realized = 'not_met', {}
    else:
        # Explicit CPU mutation: omit the required original body stream.
        missing = dict(files)
        missing.pop('overtake_bodies_original.jsonl')
        if 'overtake_bodies_original.jsonl' in missing:
            raise ValueError('Missing-evidence mutation failed')
        status, realized = 'unverified', {}
    return {'case_id': case, 'fixture_kind': kind, 'diagnostic_fixture': True,
            'actual_native_capture': False, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False, 'provenance_kind': 'native',
            'provenance_note': 'Native-shaped textual CPU diagnostic only; no CARLA execution or physical result',
            'physical_checks': {'maneuver': {'status': status,
                'method': 'source-hashed original body/trace/video-map join with explicit CPU outcome mutation',
                'sources': {'diagnostic': diagnostic_path, 'diagnostic_sha256': sha(path.read_bytes()),
                            'source_receipt_sha256': sha(files['overtake_source_receipt.json'].encode()),
                            'mutation': kind}}},
            'maneuver_completed': status == 'met', 'realized_observables': realized}


def lifecycle(events):
    if events != EVENTS:
        raise ValueError('Saved processing precedes Native ownership closure')
    return {'events': events, 'diagnostic_fixture': True, 'actual_native_capture': False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--all',action='store_true');args=parser.parse_args()
    if not args.all:
        parser.error('--all required')
    manifest=json.loads((HERE/'provisional-manifest.json').read_text())
    output=HERE/'physical';output.mkdir(exist_ok=True)
    completed=[]
    for entry in manifest['cases']:
        case=entry['case_id'];suffix=case.split('__')[-1]
        recipe=json.loads((HERE/Path(entry['fixture_recipe']).name).read_text())
        diagnostic=Path(recipe['generator']['source']).name
        for kind in ('complete_motion','incomplete_motion','missing_evidence'):
            result=fixture(case,diagnostic,kind)
            (output/(suffix+'-'+kind+'.json')).write_text(json.dumps(result,indent=2)+'\n')
            completed.append((suffix,kind,result['physical_checks']['maneuver']['status']))
    lifecycle(EVENTS)
    try:
        lifecycle(EVENTS[:-2]+EVENTS[-2:][::-1])
    except ValueError as error:
        if 'precedes Native ownership closure' not in str(error):
            raise
    else:
        raise ValueError('Out-of-order lifecycle was accepted')
    print(json.dumps({'fixtures':completed,'lifecycle_positive':True,'lifecycle_negative_rejected':True}))


if __name__=='__main__':main()
