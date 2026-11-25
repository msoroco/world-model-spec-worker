"""Exercise fixed-source officer comparison and four adverse mutations."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from audit_officer_comparison import audit

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejected(call):
    try:
        call()
    except ValueError:
        return True
    return False


def main():
    source = HERE / 'current-fixture' / 'controlled_2'
    with tempfile.TemporaryDirectory(prefix='c404492-officer-compare-',
                                     dir=REPO / '.runtime-work') as scratch:
        a, b = Path(scratch) / 'undirected', Path(scratch) / 'directed'
        a.mkdir()
        b.mkdir()
        for name in ('vehicle_poses.jsonl', 'video_frames.jsonl', 'trace.jsonl'):
            shutil.copy2(source / name, a / name)
            shutil.copy2(source / name, b / name)
        context = json.loads((source / 'emergency_context.json').read_text())
        (a / 'emergency_context.json').write_text(json.dumps(context) + '\n')
        directed = dict(context, case_id=AID + '__officer_directed',
                        officer_directed_otherwise=True,
                        officer_instruction_sources={
                            key: 'synthetic-fixture:' + key for key in (
                                'officer_instruction_source', 'officer_identity_source',
                                'officer_instruction_text', 'officer_instruction_recipient',
                                'officer_instruction_timing_source',
                                'officer_instruction_reviewer')})
        target = b / 'emergency_context.json'
        target.write_text(json.dumps(directed) + '\n')
        positive = audit(a, b)
        bad = dict(directed, officer_directed_otherwise=False)
        target.write_text(json.dumps(bad) + '\n')
        checks = [rejected(lambda: audit(a, b))]
        bad = dict(directed, emergency_vehicle_authorized=False)
        target.write_text(json.dumps(bad) + '\n')
        checks.append(rejected(lambda: audit(a, b)))
        bad = dict(directed, officer_instruction_sources={})
        target.write_text(json.dumps(bad) + '\n')
        checks.append(rejected(lambda: audit(a, b)))
        target.write_text(json.dumps(directed) + '\n')
        poses = (b / 'vehicle_poses.jsonl').read_text().splitlines()
        row = json.loads(poses[100]); row['ego']['x_m'] += 1
        poses[100] = json.dumps(row)
        (b / 'vehicle_poses.jsonl').write_text('\n'.join(poses) + '\n')
        checks.append(rejected(lambda: audit(a, b)))
        if checks != [True] * 4:
            raise ValueError('Officer comparison negative escaped')
    proof = {'format': 'c404492-officer-comparison-cpu-proof-v1',
             'audit_sha256': sha(HERE / 'audit_officer_comparison.py'),
             'controlled_pose_source_sha256': sha(source / 'vehicle_poses.jsonl'),
             'controlled_frame_source_sha256': sha(source / 'video_frames.jsonl'),
             'draft_manifest_sha256': sha(HERE / 'draft-officer-manifest.json'),
             'positive': positive, 'mutation_rejections': 4,
             'original_native_comparison_claimed': False}
    path = HERE / 'current-officer-comparison-proof.json'
    path.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'proof_sha256': sha(path), 'mutation_rejections': 4}))


if __name__ == '__main__':
    main()
