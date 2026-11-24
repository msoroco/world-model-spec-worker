"""Independent audit of the exact current-runtime saved-only diagnostic."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c102372-current-process-saved'
CASE = HERE.name + '__probe_1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit():
    primary = read(HERE / 'current-process-saved-primary-receipt.json')
    negative = read(HERE / 'current-process-saved-negative-receipt.json')
    manifest = HERE / 'draft-execution-manifest.json'
    construction = HERE / 'draft-candidates/probe_1/primary/construction.json'
    processing_path = SCRATCH / 'processed/v0001/processing.json'
    processing = read(processing_path)
    negative_feedback_path = SCRATCH / 'negative-processed/v0001/feedback.json'
    feedback = read(negative_feedback_path)
    stage = SCRATCH / 'processed/v0001/analysis'
    result = read(stage / 'result.json')
    expected_cameras = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')
    assert primary['case_id'] == negative['case_id'] == processing['case_id'] == CASE
    assert primary['manifest_sha256'] == negative['manifest_sha256'] == sha(manifest)
    assert processing['analysis_revision']['construction_sha256'] == sha(construction)
    assert primary['exit_code'] == 0 and primary['source_files_unchanged'] is True
    assert processing['passed'] is True and processing['recorded_only'] is True
    assert processing['missing_evidence'] is False and processing['originals_preserved'] is True
    assert processing['timestamp_joins'] == {'frames': 600, 'passed': True, 'missing_original_trace_or_map': False}
    assert result['video_references'] == list(expected_cameras)
    assert result['provenance_kind'] == 'synthetic_cpu' and result['accepted'] is False
    assert not (SCRATCH / 'attempt/channels').exists()
    for name in ('ego_body_pose', 'lead_body_pose', 'surface_gap_m', 'camera_frame_join'):
        channel = stage / 'channels' / (name + '.jsonl')
        assert channel.is_file() and len(channel.read_text().splitlines()) == 600
    assert (SCRATCH / 'processed/v0001/final-decode.json').is_file()
    assert negative['removed'] == 'native_samples.jsonl'
    assert negative['exit_code'] != 0 and negative['source_files_unchanged'] is True
    assert negative['rejected_as_incomplete'] is True
    assert feedback['native_replay_requested'] is False
    assert 'Missing required source: native_samples.jsonl' in feedback['error']
    assert not (SCRATCH / 'negative-attempt/native_samples.jsonl').exists()
    value = {'format': 'c102372-current-process-saved-independent-audit-v1',
             'case_id': CASE, 'manifest_sha256': sha(manifest),
             'construction_sha256': sha(construction), 'positive_processing_sha256': sha(processing_path),
             'negative_feedback_sha256': sha(negative_feedback_path),
             'primary_receipt_sha256': sha(HERE / 'current-process-saved-primary-receipt.json'),
             'negative_receipt_sha256': sha(HERE / 'current-process-saved-negative-receipt.json'),
             'frames': 600, 'four_camera_sources': True,
             'derived_channels_rebuilt_from_saved_sources': True,
             'source_unchanged': True, 'removed_source_rejected': True,
             'native_replay_requested': False, 'physical_observation_claimed': False,
             'selected_delivery_claimed': False}
    (HERE / 'current-process-saved-audit.json').write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps(value, sort_keys=True))


if __name__ == '__main__':
    audit()
