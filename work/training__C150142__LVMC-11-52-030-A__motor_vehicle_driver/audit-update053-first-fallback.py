"""Independently bind the first long fallback saved receipt to its selection."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = 'tour_bus_above'
CANDIDATE = 'fallback1'
FRAMES = 36122


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def audit():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest_sha = sha(manifest_path)
    case_id = ROOT.name + '__' + CASE
    entry = next(c for c in read(manifest_path)['cases'] if c['case_id'] == case_id)
    chosen = next(c for c in entry['candidates'] if c['id'] == CANDIDATE)
    attempt = REPO / '.runtime-work/c150142-selected-tour-bus-above-fallback1-native-v1'
    result = REPO / '.runtime-work/c150142-selected-tour-bus-above-fallback1-result-v1/v0001'
    summary = read(ROOT / 'update053-tour-bus-above-selected-fallback1-saved.log')
    selection = read(attempt / 'candidate-selection.json')
    processing = read(result / 'processing.json')
    final = read(result / 'final-decode.json')
    reuse_path = ROOT / 'update053-tour-bus-above-fallback1-composition-reuse.log'
    reuse = read(reuse_path)
    assert selection['case_id'] == case_id
    assert selection['candidate_id'] == CANDIDATE
    assert selection['manifest_sha256'] == manifest_sha
    assert selection['construction_sha256'] == chosen['construction_sha256']
    assert summary['case_id'] == processing['case_id'] == case_id
    assert summary['candidate_id'] == processing['candidate_id'] == CANDIDATE
    assert summary['passed'] is processing['passed'] is final['passed'] is True
    assert summary['frames'] == summary['final_decode_frames'] == FRAMES
    assert processing['timestamp_joins']['frames'] == final['frames'] == FRAMES
    assert summary['source_decodes'] == len(summary['source_decode_sha256']) == 4
    assert summary['originals_preserved'] is processing['originals_preserved'] is True
    assert summary['missing_evidence'] is processing['missing_evidence'] is False
    assert summary['physical_acceptance_claimed'] is processing['physical_acceptance_claimed'] is False
    assert summary['legal_acceptance_claimed'] is processing['legal_acceptance_claimed'] is False
    assert summary['processing_sha256'] == sha(result / 'processing.json')
    assert summary['final_decode_sha256'] == sha(result / 'final-decode.json')
    assert summary['composition_mode'] == 'checked_identical_reuse'
    assert summary['reused_composition_receipt_sha256'] == sha(reuse_path)
    assert reuse['frames'] == FRAMES and reuse['reused_identical_synthetic_sources'] is True
    for index in range(4):
        source = result / ('source-' + str(index) + '.json')
        assert summary['source_decode_sha256'][index] == sha(source)
        assert read(source)['passed'] is True and read(source)['frames'] == FRAMES
    return {'format': 'c150142-update053-first-fallback-audit-v1',
            'passed': True, 'case_id': case_id, 'candidate_id': CANDIDATE,
            'manifest_sha256': manifest_sha,
            'construction_sha256': chosen['construction_sha256'],
            'processing_sha256': summary['processing_sha256'],
            'frames': FRAMES, 'source_kind': 'synthetic_native_sample',
            'original_native_observed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
