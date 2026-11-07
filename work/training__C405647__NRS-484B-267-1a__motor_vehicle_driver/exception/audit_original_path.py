"""Independent receipt audit for the CPU mock of the original Native saved path."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    proof = json.loads((ROOT / 'original-path-proof.json').read_text())
    assert proof['format'] == 'c405647-original-path-cpu-mock-proof-v1'
    assert proof['processor_sha256'] == sha(ROOT / 'prepare_original.py')
    assert {p['case'] for p in proof['positive']} == {'exception_1_1', 'exception_1_2'}
    for positive in proof['positive']:
        result = positive['result']
        assert result['case_suffix'] == positive['case']
        assert result['source_kind'] == 'cpu_mock_original_path'
        assert result['frames'] == 480 and result['verified_communication_frames'] == 0
        assert result['approach_catchup_frame'] == 182
        assert result['cue_frames'] == (0 if positive['case'] == 'exception_1_1' else 60)
        assert result['cue_overlaps_request'] == (positive['case'] == 'exception_1_2')
        assert result['physical_success_claimed'] is False
        assert result['legal_exception_verdict'] is None
        assert set(result['source_hashes']) == {
            'observed-actors.jsonl', 'video_frames.jsonl',
            'officer-direction-review.json', 'officer_reference.mkv'}
        assert len(positive['saved_actor_sha256']) == 64
    assert {n['label'] for n in proof['negative']} == {
        'video-hash', 'frame-hash', 'reviewer', 'request-as-observation',
        'native-frame', 'mock-identity'}
    assert all(n['rejected'] for n in proof['negative'])
    assert proof['original_native_pixels_seen'] is False
    assert proof['physical_officer_signal_seen'] is False
    assert proof['legal_exception_verdict'] is None
    return {'passed': True, 'positive': 2, 'negative': 6,
            'proof_sha256': sha(ROOT / 'original-path-proof.json')}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
