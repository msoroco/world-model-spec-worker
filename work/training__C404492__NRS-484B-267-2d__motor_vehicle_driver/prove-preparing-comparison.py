"""Bind the preparation comparison to exact selected saved source receipts."""
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from audit_preparing_comparison import audit


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ATTEMPTS = {
    'controlled_1': ROOT / '.runtime-work/c404492-capture-final/controlled_1-primary',
    'preparing_movement': ROOT / '.runtime-work/c404492-check/preparing-public-primary-v3',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = read(manifest_path)
    sources = {}
    for suffix, attempt in ATTEMPTS.items():
        entry = next((item for item in manifest['cases']
                      if item['case_id'].endswith('__' + suffix)), None)
        if entry is None:
            raise ValueError('Comparison case is not selected: ' + suffix)
        selected = read(attempt / 'candidate-selection.json')
        saved_path = HERE / entry['saved_processing']['receipt']
        saved = read(saved_path)
        if (selected['case_id'] != entry['case_id'] or
                selected['candidate_id'] != 'primary' or
                selected['construction_sha256'] != entry['construction_sha256'] or
                saved['case_id'] != entry['case_id'] or
                saved['candidate_id'] != 'primary' or
                saved['native_revision']['construction_sha256'] != entry['construction_sha256'] or
                not saved['originals_preserved']):
            raise ValueError('Selected comparison proof changed: ' + suffix)
        for name in ('vehicle_poses.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                     'emergency_context.json'):
            if sha(attempt / name) != saved['original_source_hashes'].get(name):
                raise ValueError('Saved original source changed: ' + suffix + '/' + name)
        sources[suffix] = {'case_id': entry['case_id'],
                           'construction_sha256': entry['construction_sha256'],
                           'saved_receipt_sha256': sha(saved_path)}
    result = audit(ATTEMPTS['controlled_1'], ATTEMPTS['preparing_movement'])
    if not result['passed'] or result['physical_acceptance_claimed']:
        raise ValueError('Preparation comparison incomplete')
    negatives = []
    temporary_root = ROOT / '.runtime-work/c404492-preparing-comparison-negative'
    temporary_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temporary_root) as temporary:
        bad = Path(temporary)
        for name in ('vehicle_poses.jsonl', 'video_frames.jsonl', 'emergency_context.json'):
            shutil.copy2(ATTEMPTS['preparing_movement'] / name, bad / name)
        for name in ('missing_visible_movement', 'changed_authority', 'changed_lane',
                     'changed_camera_frame'):
            poses = [json.loads(line) for line in
                     (ATTEMPTS['preparing_movement'] / 'vehicle_poses.jsonl').read_text().splitlines()]
            frames = [json.loads(line) for line in
                      (ATTEMPTS['preparing_movement'] / 'video_frames.jsonl').read_text().splitlines()]
            context = read(ATTEMPTS['preparing_movement'] / 'emergency_context.json')
            if name == 'missing_visible_movement':
                for row in poses:
                    row['emergency']['visible_vehicle_movement'] = False
            elif name == 'changed_authority':
                context['emergency_vehicle_authorized'] = False
            elif name == 'changed_lane':
                poses[80]['ego']['y_m'] += 1
            else:
                frames[80]['camera_native_frames']['overview'] = -1
            (bad / 'vehicle_poses.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in poses))
            (bad / 'video_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in frames))
            (bad / 'emergency_context.json').write_text(json.dumps(context) + '\n')
            try:
                audit(ATTEMPTS['controlled_1'], bad)
            except ValueError:
                negatives.append(name)
            else:
                raise AssertionError('Comparison accepted altered source: ' + name)
    output = {'format': 'c404492-selected-preparing-comparison-proof-v1',
              'passed': True, 'manifest_sha256': sha(manifest_path),
              'sources': sources, 'comparison': result,
              'rejected_source_mutations': negatives, 'diagnostic_only': True}
    target = HERE / 'current-preparing-comparison-proof.json'
    target.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'passed': True, 'visible_preparation_frames':
                      result['visible_preparation_frames'], 'sha256': sha(target)}))


if __name__ == '__main__':
    main()
