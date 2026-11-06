"""Independently audit the pinned synthetic saved-processing handoff."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0,str(REPO/'runtime/pipeline'))
from scenario_pipeline.worker_exchange.common import tree


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    summary=json.loads((HERE/'alley-saved-processing-summary.json').read_text())
    root=REPO/summary['source_root']
    attempt=root/'attempt'
    version=Path(summary['processing_version'])
    assert version == root/'processed/v0001'
    seal=json.loads((attempt/'capture-seal.json').read_text())
    assert seal['format']=='worker-sealed-capture-v2'
    assert seal['diagnostic_fixture'] is True
    assert seal['frames']==480
    assert seal['events']==['capture_finished','encoders_closed','restoration_verified']
    assert seal['restoration']=={'restored':True,'synthetic_diagnostic':True}
    assert all(sha(attempt/name)==digest for name,digest in seal['sources'].items())
    exit_receipt=json.loads((attempt/'native-exit.json').read_text())
    assert exit_receipt['capture_seal_sha256']==sha(attempt/'capture-seal.json')
    processing=json.loads((version/'processing.json').read_text())
    assert processing['format']=='worker-saved-processing-v2'
    assert processing['recorded_only'] is True
    assert processing['originals_preserved'] is True
    assert processing['missing_evidence'] is False
    assert processing['timestamp_joins']=={'frames':480,'passed':True,
                                           'missing_original_trace_or_map':False}
    assert processing['physical_acceptance_claimed'] is False
    assert processing['legal_acceptance_claimed'] is False
    assert all(sha(attempt/name)==digest for name,digest in
               processing['original_source_hashes'].items())
    stage=version/'analysis'
    assert (stage/'channels').is_dir()
    for source in (attempt/'source_channels').glob('*.jsonl'):
        assert sha(source)==sha(stage/'channels'/source.name)
    report=json.loads((stage/'analysis-report.json').read_text())
    result=json.loads((stage/'result.json').read_text())
    measured=report['measurements']['alley_transition_observation']['value']
    assert measured['source_kind']=='synthetic_cpu_fixture'
    assert measured['simultaneous_moving_overlap_frames']==27
    assert result['accepted'] is False and result['legal_verdict_claimed'] is False
    assert result['case_id']==summary['case_id']
    decoded=json.loads((version/'final-decode.json').read_text())
    assert decoded['passed'] is True and decoded['frames']==480
    assert processing['final_video_checks']['video_sha256']==decoded['video_sha256']
    assert summary['analysis_complete'] and summary['final_video_passed']
    assert summary['selected'] is False and summary['accepted'] is False
    return {'passed':True,'frames':480,'source_channels':len(list((attempt/'source_channels').glob('*.jsonl'))),
            'saved_version':'v0001','selected':False,'accepted':False}


if __name__=='__main__':
    print(json.dumps(audit(),indent=2))
