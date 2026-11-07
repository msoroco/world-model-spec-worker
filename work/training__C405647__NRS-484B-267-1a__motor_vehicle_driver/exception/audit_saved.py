"""Independent audit of retained synthetic exception saved packets."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = ('exception_1_1', 'exception_1_2')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines()]


def audit():
    proof = json.loads((HERE / 'saved-proof.json').read_text())
    assert len(proof['receipts']) == 8 and not proof['physical_or_legal_result_claimed']
    seen = set()
    for candidate in CANDIDATES:
        pair = []
        for case in CASES:
            key = case, candidate
            assert key not in seen
            seen.add(key)
            receipt = next(r for r in proof['receipts'] if
                           (r['case_suffix'], r['candidate_id']) == key)
            folder = HERE / 'saved-fixtures' / case / candidate
            draft = HERE / 'drafts' / case / candidate
            assert receipt['saved_scope_sha256'] == sha(folder / 'source-scope.json')
            assert receipt['saved_frames_sha256'] == sha(folder / 'actor-frames.jsonl')
            assert receipt['saved_preview_sha256'] == sha(folder / 'saved-preview.json')
            assert all(receipt[name] for name in ('source_hash_negative_rejected',
                       'frame_join_negative_rejected', 'missing_scope_negative_rejected'))
            assert not receipt['physical_or_legal_result_claimed']
            scope = json.loads((folder / 'source-scope.json').read_text())
            preview = json.loads((folder / 'saved-preview.json').read_text())
            assert scope['case_suffix'] == case and scope['source_kind'] == 'synthetic_cpu'
            assert scope['coordinate_frame'] == 'authored_opendrive_xy'
            assert not scope['officer_identity_or_direction_verified']
            assert not scope['physical_success_claimed']
            for name, digest in scope['native_source_hashes'].items():
                assert sha(folder / name) == digest
            assert sha(folder / 'native-requests.jsonl') == sha(draft / 'native-requests.jsonl')
            assert sha(folder / 'synthetic-officer-visibility.jsonl') == sha(
                draft / 'synthetic-officer-visibility.jsonl')
            native = rows(folder / 'native-requests.jsonl')
            visible = rows(folder / 'synthetic-officer-visibility.jsonl')
            saved = rows(folder / 'actor-frames.jsonl')
            video = rows(folder / 'video_frames.jsonl')
            review = json.loads((folder / 'direction-review.json').read_text())
            assert review['source_sha256'] == sha(folder / 'officer_reference.source')
            assert len(native) == len(visible) == len(saved) == len(video) == \
                len(review['frames']) == 480
            cue = 0
            requested = 0
            for i, (n, v, s, f, a) in enumerate(zip(native, visible, saved, video,
                                                      review['frames'])):
                assert n['frame'] == v['frame'] == s['frame'] == f['native_frame'] == a['frame'] == i
                assert f['video_frame'] == s['video_frame'] == i
                assert n['time_s'] == v['time_s'] == s['time_s'] == f['time_s'] == round(i / 20, 4)
                assert s['subject']['x_m'] == n['subject_request']['x_m']
                assert s['subject']['y_m'] == -n['subject_request']['y_m']
                assert s['approach']['x_m'] == n['approach_request']['x_m']
                assert s['approach']['y_m'] == -n['approach_request']['y_m']
                assert s['direction_requested'] == n['officer_direction_request']['requested']
                assert s['direction_review'] == a
                assert a['cue_visible'] == v['direction_cue_in_frame']
                assert not a['identity_verified'] and not a['communication_verified']
                assert len(s['subject_body_xy_m']) == 4
                cue += a['cue_visible']
                requested += s['direction_requested']
            assert preview['case_suffix'] == case and preview['observed_frame_count'] == 480
            assert preview['synthetic_cue_frames'] == cue
            assert preview['physical_officer_identity_or_communication_verified'] is False
            assert preview['legal_exception_verdict'] is None
            assert (cue == requested == 0) if case == 'exception_1_1' else (cue > 0 and requested > 0)
            pair.append(saved)
        assert all(a['subject'] == b['subject'] and a['approach'] == b['approach']
                   and a['subject_body_xy_m'] == b['subject_body_xy_m']
                   for a, b in zip(*pair))
    return {'passed': True, 'audited_saved_case_candidates': len(seen),
            'saved_proof_sha256': sha(HERE / 'saved-proof.json'),
            'physical_or_legal_result_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
