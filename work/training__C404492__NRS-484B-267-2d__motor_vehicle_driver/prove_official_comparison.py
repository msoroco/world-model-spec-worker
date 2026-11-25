"""Exercise regulatory moving comparison and source mutation rejections."""
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from audit_official_comparison import audit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCES = HERE / 'current-fixture'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rejects(reference, contrast, message):
    try:
        audit(reference, contrast)
    except ValueError as exc:
        if message not in str(exc):
            raise AssertionError(f'Wrong rejection: {exc}') from exc
        return str(exc)
    raise AssertionError('Mutation was accepted: ' + message)


def main():
    reference = SOURCES / 'official_1'
    contrast = SOURCES / 'official_2'
    positive = audit(reference, contrast)
    scratch = ROOT / '.runtime-work'
    scratch.mkdir(exist_ok=True)
    negatives = []
    with tempfile.TemporaryDirectory(dir=scratch, prefix='c404492-official-comparison-') as name:
        changed = Path(name) / 'official_2'
        shutil.copytree(contrast, changed)
        context = changed / 'emergency_context.json'
        original_context = context.read_text()
        value = json.loads(original_context)
        value['official_regulatory_vehicle'] = False
        context.write_text(json.dumps(value) + '\n')
        negatives.append(rejects(reference, changed, 'regulatory'))
        context.write_text(original_context)
        value = json.loads(original_context)
        value['regulatory_agency_vehicle_source'] = None
        context.write_text(json.dumps(value) + '\n')
        negatives.append(rejects(reference, changed, 'Missing statutory context source'))
        context.write_text(original_context)
        poses = changed / 'vehicle_poses.jsonl'
        source_rows = poses.read_text().splitlines()
        changed_rows = list(source_rows)
        row = json.loads(changed_rows[100])
        row['emergency']['x_m'] += 0.25
        changed_rows[100] = json.dumps(row)
        poses.write_text('\n'.join(changed_rows) + '\n')
        negatives.append(rejects(reference, changed, 'Regulatory vehicle trajectory'))
        poses.write_text('\n'.join(source_rows) + '\n')
        value = json.loads(original_context)
        value['officer_directed_otherwise'] = True
        context.write_text(json.dumps(value) + '\n')
        negatives.append(rejects(reference, changed, 'regulatory'))
    proof = {'format': 'c404492-official-comparison-cpu-proof',
             'status': 'source_shaped_diagnostic_only',
             'comparison': positive, 'negative_rejections': negatives,
             'audit_sha256': sha(HERE / 'audit_official_comparison.py'),
             'physical_acceptance_claimed': False}
    target = HERE / 'current-official-comparison-proof.json'
    target.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed': True, 'overlap_frames': [positive['reference_overlap_frames'],
        positive['contrast_overlap_frames']], 'negatives': len(negatives),
        'proof_sha256': sha(target)}, sort_keys=True))


if __name__ == '__main__':
    main()
