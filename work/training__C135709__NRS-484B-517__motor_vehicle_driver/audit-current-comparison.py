"""Audit selected saved reference/contrast stand pairs and a changed-speed negative."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def compare(candidate, change=None):
    folders = {w: REPO/'.runtime-work/update054-c135709-saved-all-v4'/w/
               candidate/'processed/v0001/analysis' for w in ('reference', 'contrast')}
    configs = {w: json.loads((folder/'config.json').read_text())
               for w, folder in folders.items()}
    observations = {w: read_rows(folder/'native-raw-actors.jsonl')
                    for w, folder in folders.items()}
    reviews = {w: read_rows(folder/'stand-review.jsonl')
               for w, folder in folders.items()}
    frames = {w: read_rows(folder/'video_frames.jsonl')
              for w, folder in folders.items()}
    a, b = configs['reference'], configs['contrast']
    for key in ('cell_id', 'law_id', 'actor', 'candidate_id', 'road_sha256',
                'rate_hz', 'frames', 'duration_s', 'camera_policy', 'motion_policy',
                'approach_frames', 'target_x_m', 'cameras'):
        if a[key] != b[key]:
            raise ValueError('Selected comparison changed fixed config: '+key)
    if (a['requested_stand_occupancy'] is not False or
        b['requested_stand_occupancy'] is not True or
        a['case_id'].removesuffix('__reference') !=
            b['case_id'].removesuffix('__contrast')):
        raise ValueError('Selected comparison variable differs')
    if change is not None:
        observations['contrast'] = copy.deepcopy(observations['contrast'])
        observations['contrast'][220]['ego']['speed_mps'] = change
    stationary = 0
    reference_occupied = contrast_occupied = 0
    for i in range(210, 240):
        ref, con = observations['reference'][i], observations['contrast'][i]
        r_ego, c_ego = ref['ego'], con['ego']
        if (ref['frame'] != con['frame'] or
            ref['native_frame'] != con['native_frame'] or
            ref['time_s'] != con['time_s'] or
            r_ego['center_native_xyz_m'][0] != c_ego['center_native_xyz_m'][0] or
            r_ego['speed_mps'] != c_ego['speed_mps'] or
            r_ego['speed_mps'] > .1 or
            r_ego['blueprint'] != c_ego['blueprint'] or
            reviews['reference'][i]['stand_sign_visible'] !=
                reviews['contrast'][i]['stand_sign_visible'] or
            reviews['reference'][i]['stand_polygon_visible'] !=
                reviews['contrast'][i]['stand_polygon_visible'] or
            frames['reference'][i]['carla_frame'] !=
                frames['contrast'][i]['carla_frame']):
            raise ValueError('Selected stationary fixed condition differs at '+str(i))
        stationary += 1
        reference_occupied += all(50 <= p[0] <= 75 and -8.25 <= p[1] <= -3.5
                                  for p in r_ego['body_native_xyz_m'])
        contrast_occupied += all(50 <= p[0] <= 75 and -8.25 <= p[1] <= -3.5
                                 for p in c_ego['body_native_xyz_m'])
    if stationary != 30 or reference_occupied != 0 or contrast_occupied != 30:
        raise ValueError('Selected stationary stand occupancy differs')
    return {'candidate_id': candidate, 'paired_stationary_frames': stationary,
        'reference_occupied_frames': reference_occupied,
        'contrast_occupied_frames': contrast_occupied,
        'source_hashes': {w: {name: sha(folder/name) for name in
            ('native-raw-actors.jsonl', 'stand-review.jsonl', 'video_frames.jsonl',
             'config.json')} for w, folder in folders.items()},
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


def audit():
    positives = []
    negatives = []
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        positives.append(compare(candidate))
        try:
            compare(candidate, change=1.0)
        except ValueError as error:
            if 'fixed condition differs' not in str(error):
                raise
        else:
            raise AssertionError('Changed saved speed was accepted')
        negatives.append({'candidate_id': candidate,
                          'mutation': 'contrast_stationary_speed_mps',
                          'rejected': True})
    result = {'format': 'c135709-current-selected-comparison-audit-v1',
        'pairs': positives, 'negatives': negatives,
        'original_native_observed': False, 'delivery_ready': False}
    path = ROOT/'update051-current-comparison-audit.json'
    path.write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    print(json.dumps({'pairs': len(audit()['pairs']), 'negatives': 4}))
