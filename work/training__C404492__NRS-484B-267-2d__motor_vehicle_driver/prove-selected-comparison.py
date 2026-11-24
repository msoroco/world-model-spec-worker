"""Bind the controlled comparison to selected current candidate and saved proofs."""
import hashlib
import json
from pathlib import Path
from audit_abreast_comparison import audit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ATTEMPTS = {'controlled_1': ROOT / '.runtime-work/c404492-current-primary-compat3',
            'controlled_2': ROOT / '.runtime-work/c404492-current-controlled2-primary-compat'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = read(manifest_path)
    if {c['case_id'].rsplit('__', 1)[-1] for c in manifest['cases']} != set(ATTEMPTS):
        raise ValueError('Selected comparison case set changed')
    sources = {}
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        attempt = ATTEMPTS[suffix]
        selected = read(attempt / 'candidate-selection.json')
        saved = read(HERE / entry['saved_processing']['receipt'])
        if (selected['case_id'] != entry['case_id'] or selected['candidate_id'] != 'primary'
                or selected['construction_sha256'] != entry['construction_sha256']
                or saved['case_id'] != entry['case_id'] or saved['candidate_id'] != 'primary'
                or saved['native_revision']['construction_sha256'] != entry['construction_sha256']
                or not saved['originals_preserved']):
            raise ValueError('Selected candidate or saved proof changed')
        for name in ('vehicle_poses.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                     'emergency_context.json'):
            if sha(attempt / name) != saved['original_source_hashes'].get(name):
                raise ValueError('Selected source changed: ' + name)
        sources[suffix] = {'case_id': entry['case_id'],
                           'construction_sha256': entry['construction_sha256'],
                           'saved_receipt_sha256': sha(HERE / entry['saved_processing']['receipt'])}
    comparison = audit(ATTEMPTS['controlled_1'], ATTEMPTS['controlled_2'])
    if not comparison['passed'] or comparison['physical_acceptance_claimed']:
        raise ValueError('Comparison audit failed or claimed physical completion')
    output = {'format': 'c404492-selected-comparison-proof-v1', 'passed': True,
              'manifest_sha256': sha(manifest_path), 'sources': sources,
              'comparison': comparison, 'diagnostic_only': True}
    target = HERE / 'current-selected-comparison-proof.json'
    target.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'passed': True, 'reference_overlap_frames':
                      comparison['reference_overlap_frames'], 'contrast_overlap_frames':
                      comparison['contrast_overlap_frames'], 'sha256': sha(target)}))


if __name__ == '__main__':
    main()
