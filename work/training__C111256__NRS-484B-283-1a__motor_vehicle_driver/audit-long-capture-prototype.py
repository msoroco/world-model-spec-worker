"""Independently check the 600-frame unselected current-runtime migration receipts."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DRAFT = HERE / 'long-capture-prototype'
COMPAT = ROOT / '.runtime-work/c111256-long-capture-compat3/compatibility.json'
SAVED = ROOT / '.runtime-work/c111256-long-capture-saved/v0001/processing.json'
OFFLINE = ROOT / '.runtime-work/c111256-long-capture-offline2/offline.log'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / 'long-capture-prototype-manifest.json').read_text())
    entry = manifest['cases'][0]
    construction = DRAFT / 'construction.json'
    recipe = DRAFT / 'diagnostic-recipe.json'
    generator = json.loads((DRAFT / 'diagnostic-generator.json').read_text())
    compat = json.loads(COMPAT.read_text())
    saved = json.loads(SAVED.read_text())
    assert len(manifest['cases']) == 1 and manifest['status'].startswith('unselected_')
    assert entry['construction_sha256'] == sha(construction)
    assert len(generator['graphs']) == 600
    assert all(video['frames'] == 600 and video['fps'] == 20 for video in generator['videos'])
    assert {video['path'] for video in generator['videos']} == {
        'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'}
    assert compat['passed'] and compat['construction_sha256'] == sha(construction)
    assert compat['negative_removed'] == 'road_geometry.json'
    assert saved['passed'] and saved['timestamp_joins'] == {
        'frames': 600, 'passed': True, 'missing_original_trace_or_map': False}
    assert saved['originals_preserved'] and not saved['missing_evidence']
    assert saved['final_video_checks']['passed']
    assert 'offline_passed' in (DRAFT / 'offline.log').read_text()
    receipt = {
        'format': 'c111256-unselected-30-second-current-runtime-proof-v1',
        'case_id': entry['case_id'], 'status': 'partial_unselected_prototype',
        'rate_hz': 20, 'frames': 600, 'camera_count': 4,
        'offline_passed': True, 'compatibility_passed': True,
        'missing_source_rejected': 'road_geometry.json',
        'saved_processing_passed': True, 'originals_preserved': True,
        'physical_claim': False, 'legal_verdict': None,
        'source_sha256': {
            'construction': sha(construction), 'manifest': sha(HERE / 'long-capture-prototype-manifest.json'),
            'diagnostic_recipe': sha(recipe), 'diagnostic_generator': sha(DRAFT / 'diagnostic-generator.json'),
            'offline_log': sha(OFFLINE), 'compatibility_receipt': sha(COMPAT),
            'saved_receipt': sha(SAVED),
            'compatibility_command_log': sha(DRAFT / 'public-command.log'),
            'saved_command_log': sha(DRAFT / 'process-saved-command.log')},
        'remaining': ['Selected 24-second manifest and all 16 old receipts require a 30-second rebuild',
                      'Other selected cases and all branch probes need current 600-frame saved-processing proofs',
                      'Original Native motion and pixels need independent local review']}
    path = DRAFT / 'audit.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'frames': 600, 'receipt_sha256': sha(path)}))

if __name__ == '__main__':
    main()
