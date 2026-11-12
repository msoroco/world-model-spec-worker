"""Independent C104538 source, frame, four-camera and Native review audit."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in (HERE, *HERE.parents) if (p/'runtime.py').is_file())
sys.path.insert(0, str(ROOT/'runtime/scenario_pipeline'))
from worker_exchange import media

PREFIX = 'heldout__C104538__LVMC-11-12-060__motor_vehicle_driver__'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('station_context.json', 'participant_state.jsonl', 'video_frames.jsonl', 'trace.jsonl')

def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()

def rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]

def audit(case, attempt, processing=None, *, diagnostic_fixture=False, tamper=False):
    root = Path(attempt)
    analyzed = Path(processing) if processing else root
    config = json.loads((root/'config.json').read_text())
    report = json.loads((analyzed/'analysis-report.json').read_text())
    result = json.loads((analyzed/'result.json').read_text())
    if (not case.startswith(PREFIX) or config.get('selected_case_id') != case or
            report.get('case_id') != case or result.get('case_id') != case or
            report.get('physical_acceptance_claimed') is not False or
            result.get('physical_acceptance_claimed') is not False or
            result.get('legal_acceptance_claimed') is not False):
        raise ValueError('Exact station delivery identity or status differs')
    measurement = report['measurements']['station_reversal']
    original_hashes = measurement['sources']
    if set(original_hashes) != set(SOURCES):
        raise ValueError('Station measurement omits original source')
    if tamper:
        original_hashes = dict(original_hashes, **{'participant_state.jsonl': '0'*64})
    if any(digest(root/name) != original_hashes[name] for name in SOURCES):
        raise ValueError('Original station source hash differs')
    if result['measured_values']['station_reversal'] != measurement['value']:
        raise ValueError('Station result and analysis differ')
    mapping, participants, trace = (rows(root/name) for name in
                                     ('video_frames.jsonl','participant_state.jsonl','trace.jsonl'))
    if len(mapping) < 3 or len(mapping) != len(participants) or len(mapping) != len(trace):
        raise ValueError('Original station frame/participant span incomplete')
    actor_ids = set()
    for i, (m, p, t) in enumerate(zip(mapping, participants, trace)):
        frame_time = (m.get('carla_frame'), m.get('time_s'))
        if (m.get('video_frame') != i or frame_time != (p.get('frame'),p.get('time_s')) or
                frame_time != (t.get('frame'),t.get('time_s'))):
            raise ValueError('Original station frame/time join differs')
        ego = p.get('ego', {})
        if (type(ego.get('actor_id')) is not int or not isinstance(ego.get('center_xy'),list) or
                len(ego.get('center_xy')) != 2 or not isinstance(ego.get('body_vertices_xy'),list) or
                len(ego.get('body_vertices_xy')) < 4 or not isinstance(ego.get('lane_id'),list)):
            raise ValueError('Original station subject body or map lane incomplete')
        actor_ids.add(ego['actor_id'])
    if len(actor_ids) != 1:
        raise ValueError('Original station subject identity changed')
    map_sha = digest(root/'video_frames.jsonl')
    decoded = {}
    for camera in CAMERAS:
        def pixel(frame):
            if len(frame.pixels) != frame.width*frame.height*3:
                raise ValueError('Original station RGB buffer incomplete')
        decoded[camera] = media.audit(root/(camera+'.mkv'), len(mapping),
                                      mapping_sha256=map_sha,
                                      checkers={'actual_pixels': ('1'*64,pixel)}, threads=2)
    native_review = None
    if diagnostic_fixture:
        if not (root/'fixture-provenance.json').is_file() or (root/'capture-seal.json').exists():
            raise ValueError('Synthetic station diagnostic must be marked and unsealed')
    else:
        if (root/'fixture-provenance.json').exists():
            raise ValueError('Native station audit rejects diagnostic fixture')
        acquisition = json.loads((root/'acquisition-provenance.json').read_text())
        if acquisition.get('provenance_kind') != 'native' or acquisition.get('diagnostic_fixture') is not False:
            raise ValueError('Native station acquisition provenance missing')
        station_source = config.get('station_survey',{}).get('station_source',{})
        context = json.loads((root/'station_context.json').read_text())
        if station_source.get('kind') == 'authored_diagnostic' or station_source != context.get('source'):
            raise ValueError('Native station source binding differs')
        survey = json.loads((root/'station-survey-verification.json').read_text())
        original_manifest = (root/'station-survey-original.json').read_bytes()
        operator_manifest = json.loads(original_manifest)
        if (survey.get('station_source') != station_source or
                survey.get('map_name') != config['station_survey'].get('map_name') or
                survey.get('verified') is not True or
                survey.get('operator_manifest_sha256') != sha256(original_manifest).hexdigest() or
                station_source.get('source_sha256') != survey['operator_manifest_sha256'] or
                operator_manifest.get('map_name') != survey['map_name'] or
                operator_manifest.get('opendrive_sha256') != survey.get('opendrive_sha256') or
                operator_manifest.get('station_object') != {
                    key: value for key, value in survey.get('station_object',{}).items()
                    if key != 'actual_transform'}):
            raise ValueError('Native station survey verification absent')
        seal = json.loads((root/'capture-seal.json').read_text())
        owner = json.loads((root/'native-exit.json').read_text())
        if (seal.get('provenance_kind') != 'native' or
                seal.get('restoration',{}).get('restored') is not True or
                owner.get('capture_seal_sha256') != digest(root/'capture-seal.json') or
                any(seal.get('sources',{}).get(name) != digest(root/name) for name in
                    (*SOURCES,'station-survey-original.json','station-survey-verification.json'))):
            raise ValueError('Native station owner closure differs')
        review = json.loads((root/'station-physical-pixel-review.json').read_text())
        if review.get('case_id') != case or not review.get('reviewer'):
            raise ValueError('Native station reviewer identity missing')
        if any(review.get('original_sha256',{}).get(name) != digest(root/name) for name in SOURCES):
            raise ValueError('Native station review source binding differs')
        for label in ('subject_body','station_entrance','turn_area'):
            item = review.get('visible',{}).get(label,{})
            camera = item.get('camera')
            if (camera not in decoded or item.get('camera_sha256') != decoded[camera]['video_sha256'] or
                    type(item.get('video_frame')) is not int or not 0 <= item['video_frame'] < len(mapping) or
                    item.get('observed') is not True):
                raise ValueError('Native station pixel review missing '+label)
        physical = review.get('physical',{})
        if (physical.get('station_asset_reviewed') is not True or
                physical.get('opposite_direction_turn_observed') is not True or
                physical.get('no_contact_observed') is not True):
            raise ValueError('Native station physical review incomplete')
        native_review = {'path': 'station-physical-pixel-review.json',
                         'sha256': digest(root/'station-physical-pixel-review.json')}
    return {'format':'worker-delivery-audit','case_id':case,
            'scope':'synthetic station software diagnostic' if diagnostic_fixture else 'source-bound Native station review',
            'original_sha256':{name:digest(root/name) for name in SOURCES},
            'participant_ids':list(actor_ids),'frames':len(mapping),
            'cameras':{name:decoded[name]['rgb_sequence_sha256'] for name in CAMERAS},
            'native_review':native_review,
            'checks':{'native_source':not diagnostic_fixture,'all_participants':True,
                      'time_join':True,'full_video_decode':True,
                      'actual_pixels':native_review is not None,
                      'physical_completion':native_review is not None},
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--case',required=True); p.add_argument('--attempt',required=True)
    p.add_argument('--processing')
    p.add_argument('--diagnostic-fixture',action='store_true')
    p.add_argument('--tamper-source-hash',action='store_true')
    p.add_argument('--output')
    a=p.parse_args()
    result=audit(a.case,a.attempt,a.processing,diagnostic_fixture=a.diagnostic_fixture,
                 tamper=a.tamper_source_hash)
    if a.output: Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'case_id':result['case_id'],'frames':result['frames'],
                      'checks':result['checks']}))

if __name__=='__main__': main()
