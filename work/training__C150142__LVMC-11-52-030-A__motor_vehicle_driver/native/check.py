"""Independent audit of the authored red-curb request matrix."""
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]
AID = FOLDER.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    tree = ET.parse(HERE / 'red-curb-road.xodr')
    lane = tree.find('.//laneSection/right/lane[@id="-2"]')
    require(lane is not None and lane.attrib.get('type') == 'parking',
            'Authored parking lane missing')
    marks = [(float(x.attrib['sOffset']), x.attrib['color'])
             for x in lane.findall('roadMark')]
    require(marks == [(0, 'white'), (30, 'red'), (50, 'white')],
            'Painted red curb extent differs')
    manifest = json.loads((HERE / 'manifest.json').read_text())
    require(manifest['assignment_id'] == AID and len(manifest['entries']) == 8 and
            manifest['road_sha256'] == sha(HERE / 'red-curb-road.xodr') and
            manifest['controller_sha256'] == sha(HERE / 'parking_controller.py') and
            manifest['assignment_sha256'] == sha(REPO / 'inputs' / AID / 'assignment.json') and
            manifest['case_plan_sha256'] == sha(FOLDER / 'case-plan.json') and
            manifest['delivery_ready'] is False,
            'Draft construction source binding differs')
    proof = []
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        pair = []
        for witness, target in (('reference', 40), ('contrast', 60)):
            directory = HERE / 'drafts' / witness / candidate
            cfg = json.loads((directory / 'config.json').read_text())
            track = rows(directory / 'requested-tracks.jsonl')
            entry = next(x for x in manifest['entries'] if
                         x['case_id'] == cfg['case_id'] and x['candidate_id'] == candidate)
            require(entry['config_sha256'] == sha(directory / 'config.json') and
                    entry['tracks_sha256'] == sha(directory / 'requested-tracks.jsonl') and
                    cfg['tracks_sha256'] == entry['tracks_sha256'] and
                    cfg['controller_sha256'] == manifest['controller_sha256'] and
                    cfg['case_id'] == AID + '__' + witness and
                    cfg['requested_target_x_m'] == target and
                    len(track) == 240 and
                    all(row['frame'] == i and
                        row['source_kind'] == 'authored_controller_request' and
                        row['observed_native_motion'] is False
                        for i, row in enumerate(track)),
                    'Candidate request differs: ' + witness + '/' + candidate)
            expected = 240 - cfg['requested_approach_frames']
            observed = sum(row['requested_red_curb_occupancy'] for row in track)
            require(observed == (expected if witness == 'reference' else 0) and
                    track[-1]['requested_ego_x_m'] == target and
                    all(row['requested_ego_y_m'] == -6.8 for row in track),
                    'Requested parking point or dwell differs')
            pair.append((cfg, track))
        left, right = pair
        require(left[0]['requested_approach_frames'] == right[0]['requested_approach_frames'] and
                left[0]['camera_policy'] == right[0]['camera_policy'] and
                left[0]['painted_curb'] == right[0]['painted_curb'] and
                left[0]['risk_trigger'] == right[0]['risk_trigger'],
                'Comparison changes a fixed candidate condition')
        proof.append({'candidate_id': candidate,
                      'reference_red_stopped_requested': sum(x['requested_red_curb_occupancy']
                                                             for x in left[1]),
                      'contrast_red_stopped_requested': 0,
                      'risk_trigger': left[0]['risk_trigger']})
    require(len({x['risk_trigger'] for x in proof[1:]}) == 3,
            'Fallbacks reuse a physical-risk trigger')
    return {'format': 'c150142-red-curb-construction-proof-v1',
            'passed': True, 'pairs': proof,
            'original_native_observed': False,
            'delivery_ready': False, 'legal_verdict': None}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
