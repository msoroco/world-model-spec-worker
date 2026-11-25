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
SELECTED = {suffix: ROOT / '.runtime-work' / 'c404492-official-public' / (suffix + '-primary-v2')
            for suffix in ('official_1', 'official_2')}


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
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    selected_sources = {}
    for suffix, attempt in SELECTED.items():
        case_id = HERE.name + '__' + suffix
        entry = next((case for case in manifest['cases'] if case['case_id'] == case_id), None)
        if entry is None:
            raise ValueError('Official comparison case not selected: ' + suffix)
        choice = json.loads((attempt / 'candidate-selection.json').read_text())
        saved_path = HERE / entry['saved_processing']['receipt']
        saved = json.loads(saved_path.read_text())
        if (choice['case_id'] != case_id or choice['candidate_id'] != 'primary' or
                choice['construction_sha256'] != entry['construction_sha256'] or
                saved['case_id'] != case_id or saved['candidate_id'] != 'primary' or
                saved['native_revision']['construction_sha256'] != entry['construction_sha256'] or
                saved['originals_preserved'] is not True):
            raise ValueError('Official selected candidate or saved proof changed')
        for source in ('vehicle_poses.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                       'emergency_context.json'):
            if sha(attempt / source) != saved['original_source_hashes'].get(source):
                raise ValueError('Official selected source changed: ' + source)
        selected_sources[suffix] = {
            'case_id': case_id, 'construction_sha256': entry['construction_sha256'],
            'saved_receipt_sha256': sha(saved_path)}
    positive = audit(SELECTED['official_1'], SELECTED['official_2'])
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
             'selected_manifest_sha256': sha(manifest_path),
             'selected_sources': selected_sources,
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
