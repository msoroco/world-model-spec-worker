"""Independent saved receipt, source and controlled-pair diagnostic audit."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
OUTPUT=HERE/'draft-measurements'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit():
    summary=json.loads((HERE/'saved-diagnostic-summary.json').read_text())
    assert summary['ready'] is False and len(summary['rows'])==2
    source_rows={}
    for entry in summary['rows']:
        suffix=entry['suffix'];folder=OUTPUT/suffix
        report=json.loads((folder/'saved-analysis-report.json').read_text())
        result=json.loads((folder/'saved-result.json').read_text())
        contract=json.loads((folder/'measurement-contract.json').read_text())
        samples=rows(folder/'native_samples.jsonl')
        source_rows[suffix]=samples
        assert len(samples)==480
        assert sha(folder/'saved-analysis-report.json')==entry['positive_report_sha256']
        assert sha(folder/'saved-result.json')==entry['result_sha256']
        assert entry['source_hashes']['native_samples.jsonl']==sha(folder/'native_samples.jsonl')
        assert entry['source_hashes']['road_geometry.json']==sha(folder/'road_geometry.json')
        assert report['original_joins']['frames']==480
        assert set(report['video_frames'].values())=={480}
        assert set(entry['source_videos'].values())=={480}
        assert not result['accepted'] and not result['legal_verdict_claimed']
        assert result['provenance_kind']=='synthetic_local_diagnostic'
        assert result['maneuver_completed'] is False and result['behavior_attempted'] is False
        assert result['setup_confirmed'] is False
        assert all(check['matched'] and check['physical_cause_confirmed'] is False
                   for check in result['target_checks'])
        assert contract['case_id']==result['case_id']
        assert {r['output_key'] for r in contract['requirements']}==set(report['measurements'])
        for measurement in report['measurements'].values():
            assert measurement['sources']=={
                'native_samples.jsonl':sha(folder/'native_samples.jsonl'),
                'road_geometry.json':sha(folder/'road_geometry.json')}
        assert 'Missing required source: native_samples.jsonl' in (folder/'missing-source.log').read_text()
        assert entry['missing_source_exit_code']!=0
        stop=-12 if suffix=='reference' else 0
        stationary=[r for r in samples if r['speed_mps']<=.1 and r['native_road_id']==1 and r['native_lane_id']==-1]
        assert len(stationary)>=40
        assert stationary[-1]['native_center_xy_m']==[stop,-2]
        # Independent axis-aligned body/corridor projection for these controlled fixtures.
        overlap=max(0,min(stop+2.6,3)-max(stop-2.6,-3))
        assert result['measured_values']['max_entrance_overlap_m']==round(overlap,6)
        assert report['measurements']['entrance_overlap_observation']['value']['max_entrance_overlap_m']==round(overlap,6)
    for a,b in zip(source_rows['reference'][:132],source_rows['contrast'][:132]):
        assert a==b
    result={'format':'c10014-independent-saved-pair-audit-v1',
            'cases':2,'shared_prefix_frames':132,
            'reference_overlap_m':0,'contrast_overlap_m':5.2,
            'original_video_frames_per_view':480,
            'physical_success_claimed':False,'legal_verdict_claimed':False,
            'selected':False}
    (HERE/'saved-comparison-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(audit(),indent=2))
