"""Exercise the saved bridge on every synthetic officer exception request."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from build import CASES, CANDIDATES
from prepare_saved import prepare
from measure_saved import measure

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def run():
    receipts = []
    for case in CASES:
        for candidate in CANDIDATES:
            draft = HERE / 'drafts' / case / candidate
            scratch = Path(tempfile.mkdtemp(dir=REPO / '.runtime-work',
                                            prefix='c405647-exception-saved-'))
            source = scratch / 'source'
            source.mkdir()
            for name in ('native-requests.jsonl', 'synthetic-officer-visibility.jsonl'):
                shutil.copyfile(draft / name, source / name)
            native = [json.loads(x) for x in (source / 'native-requests.jsonl').read_text().splitlines()]
            visibility = [json.loads(x) for x in
                          (source / 'synthetic-officer-visibility.jsonl').read_text().splitlines()]
            (source / 'officer_reference.source').write_text(
                'synthetic CPU cue source; no original pixels or officer identity\n')
            (source / 'video_frames.jsonl').write_text(''.join(json.dumps({
                'video_frame': i, 'native_frame': i, 'carla_frame': i,
                'time_s': row['time_s']},
                sort_keys=True) + '\n' for i, row in enumerate(native)))
            annotations = [{'frame': i,
                            'cue_visible': bool(v['direction_cue_in_frame']),
                            'content': ('remain_in_inner_lane' if v['direction_cue_in_frame'] else None),
                            'recipient': ('subject_driver' if v['direction_cue_in_frame'] else None),
                            'identity_verified': False,
                            'communication_verified': False}
                           for i, v in enumerate(visibility)]
            write(source / 'direction-review.json', {
                'source_kind': 'synthetic_cpu',
                'source_sha256': sha(source / 'officer_reference.source'),
                'frames': annotations})
            saved = HERE / 'saved-fixtures' / case / candidate
            if saved.exists():
                shutil.rmtree(saved)
            positive = prepare(source, saved, case)
            assert measure(saved) == positive
            # Each negative independently corrupts the source bound join.
            bad_hash = scratch / 'bad-hash'
            shutil.copytree(source, bad_hash)
            (bad_hash / 'officer_reference.source').write_text('changed source\n')
            try:
                prepare(bad_hash, scratch / 'bad-hash-output', case)
            except ValueError as error:
                assert str(error) == 'Direction review source hash or provenance differs'
            else:
                raise AssertionError('Changed direction source accepted')
            bad_join = scratch / 'bad-join'
            shutil.copytree(source, bad_join)
            review = json.loads((bad_join / 'direction-review.json').read_text())
            review['frames'][42]['cue_visible'] = not review['frames'][42]['cue_visible']
            write(bad_join / 'direction-review.json', review)
            try:
                prepare(bad_join, scratch / 'bad-join-output', case)
            except ValueError as error:
                assert str(error) == 'Direction cue annotation differs from source'
            else:
                raise AssertionError('Changed direction cue join accepted')
            missing = scratch / 'missing-scope'
            shutil.copytree(saved, missing)
            (missing / 'source-scope.json').unlink()
            try:
                measure(missing)
            except ValueError as error:
                assert str(error) == 'Missing required source: source-scope.json'
            else:
                raise AssertionError('Missing source scope accepted')
            receipts.append({'case_suffix': case, 'candidate_id': candidate,
                             'saved_scope_sha256': sha(saved / 'source-scope.json'),
                             'saved_frames_sha256': sha(saved / 'actor-frames.jsonl'),
                             'saved_preview_sha256': sha(saved / 'saved-preview.json'),
                             'source_hash_negative_rejected': True,
                             'frame_join_negative_rejected': True,
                             'missing_scope_negative_rejected': True,
                             'physical_or_legal_result_claimed': False})
            print(case, candidate, positive['synthetic_cue_frames'], flush=True)
    summary = {'format': 'c405647-exception-synthetic-saved-v1',
               'receipts': receipts, 'physical_or_legal_result_claimed': False}
    write(HERE / 'saved-proof.json', summary)
    return {'passed': True, 'receipts': len(receipts),
            'proof_sha256': sha(HERE / 'saved-proof.json')}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
