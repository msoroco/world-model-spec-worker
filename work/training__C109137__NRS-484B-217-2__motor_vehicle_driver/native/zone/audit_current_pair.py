"""Independent readback of the retained synthetic crossing pair and source negatives."""
import hashlib
import json
from pathlib import Path
import tempfile

from saved import process

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / '.runtime-work' / 'c109137-current-pair-sources'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def main():
    proof_path = HERE / 'current-pair-source-proof.json'
    proof = json.loads(proof_path.read_text())
    checks = []
    for suffix, record in zip(('probe_1', 'probe_2'), proof['records']):
        folder = OUT / suffix
        bundle = HERE / 'drafts' / suffix / 'primary'
        source = {name: folder / name for name in record['sources']}
        if any(sha(path) != record['sources'][name] for name, path in source.items()):
            raise AssertionError('Retained source hash changed')
        raw = rows(source['native-raw-actors.jsonl'])
        video = rows(source['video_frames.jsonl'])
        req = rows(bundle / 'requested-tracks.jsonl')
        if len(raw) != len(video) or len(raw) != len(req) or len(raw) != 600:
            raise AssertionError('Source join count changed')
        stripe = []
        adjoining = []
        signal = []
        for index, (actor, frame, request) in enumerate(zip(raw, video, req)):
            if (actor['frame'] != index or frame['video_frame'] != index or
                    actor['native_frame'] != frame['native_frame'] or
                    actor['requested_ego_xy_m'] != request['requested_ego_xy_m']):
                raise AssertionError('Retained source index/request mismatch')
            body = actor['ego']['body_native_xyz_m']
            stripe.append(min(p[1] for p in body) <= 0 <= max(p[1] for p in body)
                          and max(p[0] for p in body) >= 0 and min(p[0] for p in body) <= 55)
            adjoining.append(actor['observed_road_id'] == 218 and actor['observed_lane_id'] == -1)
            signal.append(actor['observed_left_indicator'])
        measured = record['measurement']
        first = lambda flags: next((i for i, flag in enumerate(flags) if flag), None)
        if (sum(stripe) != measured['observed_stripe_body_frames'] or
                first(stripe) != measured['first_observed_stripe_frame'] or
                first(adjoining) != measured['first_adjoining_lane_frame'] or
                first(signal) != measured['first_observed_signal_frame']):
            raise AssertionError('Saved measurements do not reproduce from sources')
        with tempfile.TemporaryDirectory(dir=OUT) as temp:
            temporary = Path(temp)
            altered = temporary / 'native-raw-actors.jsonl'
            changed = list(raw)
            changed[172] = dict(changed[172], observed_road_id=999)
            altered.write_text(''.join(json.dumps(row) + '\n' for row in changed))
            try:
                process(bundle, altered, source['video_frames.jsonl'],
                        source['review.json'], synthetic=True)
            except ValueError as error:
                if 'hash' not in str(error).lower():
                    raise AssertionError('Unexpected tamper rejection') from error
            else:
                raise AssertionError('Source relocation/tamper was accepted')
            absent = temporary / 'missing.jsonl'
            try:
                process(bundle, absent, source['video_frames.jsonl'],
                        source['review.json'], synthetic=True)
            except FileNotFoundError:
                pass
            else:
                raise AssertionError('Missing source accepted')
        checks.append({'case_suffix': suffix, 'source_hashes_verified': True,
                       'native_video_request_joins': 600,
                       'crossing_frames': sum(stripe),
                       'first_crossing_frame': first(stripe),
                       'first_adjoining_frame': first(adjoining),
                       'first_signal_frame': first(signal),
                       'altered_source_rejected': True,
                       'missing_source_rejected': True})
    receipt = {'format': 'c109137-independent-source-pair-audit-v1',
               'pair_receipt_sha256': sha(proof_path), 'checks': checks,
               'passed': True, 'scope': 'synthetic CPU only; no original road or legal finding'}
    target = HERE / 'current-pair-independent-audit.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'audit_sha256': sha(target)}))


if __name__ == '__main__':
    main()
