"""Audit retained synthetic alley Core/Lean/video integration outputs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    summary = json.loads((HERE/'alley-core-summary.json').read_text())
    attempt = REPO/summary['source_root']/'attempt'
    assert summary['selected'] is False and summary['accepted'] is False
    assert summary['converted']['converted'] is True
    assert summary['converted']['decoder_checked'] is True
    assert summary['converted']['acceptance_claimed'] is False
    assert summary['rendered_frames'] == 480 and summary['final_decode_passed'] is True
    assert sha(attempt/'analysis-report.json') == summary['analysis_report_sha256']
    assert sha(attempt/'road.xodr') == summary['road_sha256']
    report = json.loads((attempt/'analysis-report.json').read_text())
    result = json.loads((attempt/'result.json').read_text())
    assert report['case_id'] == summary['case_id'] == result['case_id']
    assert report['candidate_id'] == summary['candidate_id'] == 'primary'
    assert report['measurements']['alley_transition_observation']['value']['source_kind'] == 'synthetic_cpu_fixture'
    assert result['accepted'] is False and result['legal_verdict_claimed'] is False
    assert len((attempt/'trace.jsonl').read_text().splitlines()) == 480
    assert len((attempt/'capture/native/frames.jsonl').read_text().splitlines()) == 480
    assert len((attempt/'event_review_frames.jsonl').read_text().splitlines()) == 480
    decoder = json.loads((attempt/'converted/adapter_report.json').read_text())
    assert decoder
    decoded = json.loads((attempt/'final-decode.json').read_text())
    assert decoded['passed'] is True and decoded['frames'] == 480
    assert sha(attempt/'event_review.webm') == decoded['video_sha256']
    assert sha(attempt/'event_review_frames.jsonl') == decoded['mapping_sha256']
    return {'passed':True,'frames':480,'core_decoder_checked':True,
            'final_video_sha256':decoded['video_sha256'],
            'selected':False,'accepted':False}


if __name__=='__main__':
    print(json.dumps(audit(),indent=2))
