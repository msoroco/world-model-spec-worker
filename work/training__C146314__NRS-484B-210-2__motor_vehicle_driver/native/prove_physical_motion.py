"""Diagnostic geometry and provenance negatives for the independent motion audit."""
import copy
import json
import tempfile
from pathlib import Path

from audit_physical_motion import audit, geometry, require
from measure_raw import read_jsonl
from prove_capture_measure import fixture

ROOT = Path(__file__).resolve().parent


def rejected(fn, label):
    try:
        fn()
    except (ValueError, KeyError, IndexError):
        return label
    raise AssertionError('Physical motion negative accepted: '+label)


def prove():
    track = read_jsonl(ROOT/'drafts/reference/primary/requested-tracks.jsonl')
    rows, frames = fixture(track)
    positive = geometry(rows, frames)
    require(positive['complete_motion_observed'] and positive['right_overlap_frames'] > 0,
            'Diagnostic fixture does not exercise complete motion geometry')
    with tempfile.TemporaryDirectory() as temp:
        source = Path(temp)
        (source/'capture').mkdir()
        (source/'native-raw-actors.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
        (source/'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in frames))
        (source/'native-map-readback.json').write_text(json.dumps({'source_kind':'synthetic_native_sample'}))
        (source/'capture/evidence.jsonl').write_text('{}\n')
        diagnostic = audit(source)
        (source/'capture/evidence.jsonl').unlink()
        missing = audit(source)
        require(missing['status'] == 'unverified' and
                missing['missing_evidence'] == ['capture/evidence.jsonl'],
                'Missing source was accepted')
    require(diagnostic['status'] == 'unverified' and not diagnostic['maneuver_completed'] and
            diagnostic['source_kind'] == 'synthetic_native_sample' and
            diagnostic['legal_safety_verdict'] is None,
            'Synthetic motion was promoted to physical acceptance')
    negatives = []
    negatives.append('missing-capture-evidence')
    altered = copy.deepcopy(frames); altered[100]['views'] = ['overview']
    negatives.append(rejected(lambda: geometry(rows, altered), 'missing-three-views'))
    altered = copy.deepcopy(rows); altered[100]['lead']['actor_id'] = altered[100]['ego']['actor_id']
    negatives.append(rejected(lambda: geometry(altered, frames), 'same-actor-identity'))
    altered = copy.deepcopy(rows); altered[-1]['lead']['center_native_xyz_m'][0] = 1000
    require(not geometry(altered, frames)['complete_motion_observed'], 'Incomplete pass accepted')
    negatives.append('incomplete-longitudinal-pass')
    altered = copy.deepcopy(rows)
    for row in altered:
        row['ego']['center_native_xyz_m'][1] = row['lead']['center_native_xyz_m'][1] + 1
    require(not geometry(altered, frames)['complete_motion_observed'], 'Wrong-side pass accepted')
    negatives.append('wrong-side-pass')
    return {'format': 'c146314-physical-motion-diagnostic-v1', 'passed': True,
            'diagnostic_geometry': positive, 'synthetic_status': diagnostic['status'],
            'negative_rejections': negatives, 'original_native_observed': False,
            'physical_acceptance_claimed': False, 'legal_safety_verdict': None}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
