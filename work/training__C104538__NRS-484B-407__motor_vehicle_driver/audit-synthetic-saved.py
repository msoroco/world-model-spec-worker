"""Independent retained synthetic finalizer diagnostic audit."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def audit():
    summary=json.loads((ROOT/'draft-saved-summary.json').read_text())
    assert summary['positive_count']==1 and summary['negative_count']==2
    assert summary['native_executed'] is False and summary['recording_accepted'] is False
    for row in summary['rows']:
        assert SHA(ROOT/row['log'])==row['log_sha256']
        assert (row['exit_code']==0)==(row['label']=='positive')
    positive=REPO/'.runtime-work/c104538/draft-saved-v4/positive'
    result=json.loads((positive/'result.json').read_text())
    report=json.loads((positive/'analysis-report.json').read_text())
    assert SHA(positive/'result.json')==summary['positive_result_sha256']
    assert SHA(positive/'analysis-report.json')==summary['positive_analysis_sha256']
    assert result['provenance_kind']=='synthetic'
    assert all(result[key] is False for key in ('setup_confirmed','accepted','legal_verdict_claimed'))
    assert result['target_checks'][0]['matched'] is False
    assert report['measurements']['sightline_boundary_and_pixels']['value']=={
        'original_pixel_visibility_proven':False,'actual_body_visibility_proven':False}
    assert set(report['video_frames'])=={'overview','reference_left','reference_right','ego'}
    assert set(report['video_frames'].values())=={3}
    for source_name,digest in result['measured_values']['source_sha256'].items():
        assert SHA(positive/source_name)==digest
    for row in summary['rows'][1:]:
        assert row['removed'] and not (REPO/'.runtime-work/c104538/draft-saved-v4'/row['label']/row['removed']).exists()
    return {'positive':1,'negatives':2,'source_hashes_verified':8,
            'actual_native_evidence_claimed':False,'recording_accepted':False}


if __name__=='__main__':print(json.dumps(audit()))
