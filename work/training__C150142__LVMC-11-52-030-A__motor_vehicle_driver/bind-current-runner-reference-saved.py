"""Retain the pinned current-runner reference saved-processing proof."""

import hashlib
import json
import os
from pathlib import Path
import tempfile


WORK = Path(__file__).resolve().parent
REPO = WORK.parents[1]
SCRATCH = REPO / '.runtime-work/owner150142/current-runner-reference-saved-v1'
MANIFEST = WORK / 'current-runtime-runner-reference-bound-manifest.json'
DEST = WORK / 'current-runtime-runner-saved/reference/primary'
TEMP = REPO / '.runtime-work/owner150142/reference-saved-binding-tmp'
CASE = WORK.name + '__reference'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def retain(source, destination):
    if not source.is_file() or source.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Missing or oversized saved receipt: ' + str(source))
    data = source.read_bytes()
    if destination.is_file():
        if sha(source) != sha(destination):
            raise ValueError('Saved receipt changed: ' + str(destination))
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    TEMP.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='wb', dir=TEMP, delete=False) as out:
        out.write(data)
        temporary = Path(out.name)
    os.replace(temporary, destination)


def run():
    manifest = json.loads(MANIFEST.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    selection_file = SCRATCH / 'attempt/candidate-selection.json'
    processing_file = SCRATCH / 'result/v0001/processing.json'
    selection = json.loads(selection_file.read_text())
    processing = json.loads(processing_file.read_text())
    if selection != {
        'format': 'worker-candidate-selection',
        'case_id': CASE,
        'candidate_id': 'primary',
        'construction_sha256': entry['construction_sha256'],
        'manifest_sha256': sha(MANIFEST),
    }:
        raise ValueError('Saved selection is not bound to the exact current-runner draft')
    required = {
        'format': 'worker-saved-processing', 'case_id': CASE,
        'candidate_id': 'primary', 'passed': True, 'recorded_only': True,
        'originals_preserved': True, 'missing_evidence': False,
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
    }
    if any(processing.get(key) != value for key, value in required.items()):
        raise ValueError('Saved processing did not pass recorded-only proof')
    if (processing['analysis_revision']['construction_sha256'] !=
            entry['construction_sha256'] or
            processing['analysis_revision']['runtime_manifest_sha256'] !=
            manifest['runtime_manifest_sha256'] or
            processing['timestamp_joins'].get('frames') != 240 or
            processing['timestamp_joins'].get('passed') is not True or
            processing['final_video_checks'].get('frames') != 240 or
            processing['final_video_checks'].get('passed') is not True):
        raise ValueError('Saved processing lost the selected source or frame joins')
    source_files = {
        'candidate-selection.json': selection_file,
        'processing.json': processing_file,
        'analysis.log': SCRATCH / 'result/v0001/analysis.log',
        'final-decode.json': SCRATCH / 'result/v0001/final-decode.json',
        'prepare.log': REPO / '.runtime-work/owner150142/current-runner-reference-saved-prepare-v1.log',
        'process.log': REPO / '.runtime-work/owner150142/current-runner-reference-saved-process-v1.log',
    }
    for index in range(4):
        source_files[f'source-{index}.json'] = SCRATCH / f'result/v0001/source-{index}.json'
    if sha(source_files['analysis.log']) != processing['analysis_log_sha256']:
        raise ValueError('Saved analysis log changed')
    for index in range(4):
        source = json.loads(source_files[f'source-{index}.json'].read_text())
        if source.get('passed') is not True or source.get('frames') != 240:
            raise ValueError('Saved source decode failed')
    final = json.loads(source_files['final-decode.json'].read_text())
    if final.get('passed') is not True or final.get('frames') != 240:
        raise ValueError('Saved final decode failed')
    for name, source in source_files.items():
        retain(source, DEST / name)
    evidence = {
        'format': 'c150142-current-runner-reference-saved-proof-v1',
        'case_id': CASE, 'candidate_id': 'primary', 'passed': True,
        'recorded_only': True, 'delivery_ready': False,
        'draft_manifest_sha256': sha(MANIFEST),
        'construction_sha256': entry['construction_sha256'],
        'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
        'joined_frames': 240,
        'receipts': {name: sha(DEST / name) for name in sorted(source_files)},
    }
    TEMP.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=TEMP,
                                     delete=False) as out:
        json.dump(evidence, out, sort_keys=True, indent=2)
        out.write('\n')
        temporary = Path(out.name)
    os.replace(temporary, DEST / 'binding.json')
    return evidence


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
