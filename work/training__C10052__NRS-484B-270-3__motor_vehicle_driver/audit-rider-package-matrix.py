"""Independent source and package audit for 24 synthetic rider v1 probes."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
RIDERS=('bicycle','electric_bicycle','electric_scooter')
CANDIDATES=('primary','fallback1','fallback2','fallback3')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):return json.loads(Path(path).read_text())


def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def crosses(body,box):
    xs=[p[0] for p in body];ys=[p[1] for p in body]
    return min(xs)<box[2] and max(xs)>box[0] and min(ys)<box[3] and max(ys)>box[1]


def audit():
    summary_path=HERE/'rider-package-matrix-summary.json'
    summary=read(summary_path)
    manifest=read(HERE/'draft-rider-execution-manifest.json')
    assert summary['passed'] is True and len(summary['results'])==24
    assert summary['manifest_sha256']==sha(HERE/'draft-rider-execution-manifest.json')
    assert summary['selected'] is summary['accepted'] is summary['original_native_capture_executed'] is False
    evidence={}
    for item in summary['results']:
        case=item['case_id'];candidate=item['candidate_id']
        assert candidate in CANDIDATES
        suffix=case.rsplit('__',1)[-1]
        rider_type,response=suffix.removeprefix('rider_').rsplit('_',1)
        assert rider_type in RIDERS and response in ('clear','conflict')
        entry=next(e for e in manifest['cases'] if e['case_id']==case)
        ref=entry if candidate=='primary' else next(c for c in entry['candidates'] if c['id']==candidate)
        assert item['construction_sha256']==ref['construction_sha256']==sha(HERE/ref['construction'])
        source=ROOT/item['fixture'];output=ROOT/item['positive']
        assert source.is_dir() and output.is_dir()
        assert item['fixture_rider_rows_sha256']==sha(source/'rider_native_samples.jsonl')
        for name,key in (('compatibility.json','positive_receipt_sha256'),
                         ('analysis-report.json','analysis_report_sha256'),
                         ('result.json','result_sha256')):
            assert sha(output/name)==item[key]
        receipt=read(output/'compatibility.json')
        report=read(output/'analysis-report.json')
        result=read(output/'result.json')
        assert receipt['format']=='worker-package-compatibility-v1' and receipt['passed'] is True
        assert {'actual_analysis','native_validation','mandatory_observations',
                'lean_decoder','render','final_decode','acquisition_unchanged'}<=set(receipt['checks'])
        assert receipt['construction_sha256']==ref['construction_sha256']
        assert report['source_scope']=='synthetic_native_shaped_diagnostic'
        assert result['accepted'] is False and result['legal_verdict_claimed'] is False
        assert item['negative_log_sha256']==sha(ROOT/item['negative_log'])
        assert 'Changed original source bytes' in (ROOT/item['negative_log']).read_text()
        assert not (output/'native-capture-report.json').exists()
        manifest_source=read(source/'rider-source-manifest.json')
        geometry=read(source/'rider_geometry.json')
        assert manifest_source['source_kind']=='synthetic_native_shaped_diagnostic'
        assert manifest_source['samples_sha256']==sha(source/'rider_native_samples.jsonl')
        assert manifest_source['geometry_sha256']==sha(source/'rider_geometry.json')
        samples=rows(source/'rider_native_samples.jsonl')
        ego=rows(source/'native_samples.jsonl')
        mapping=rows(source/'video_frames.jsonl')
        assert len(samples)==len(ego)==len(mapping)==480
        assert all(s['native_frame']==e['native_frame']==m['native_frame'] and
                   s['time_s']==e['time_s']==m['time_s'] and
                   s['ego_body_xy']==e['native_body_xy_m'] and
                   s['ego_native_road_id']==e['native_road_id'] and
                   s['rider_type']==rider_type for s,e,m in zip(samples,ego,mapping))
        box=geometry['conflict_native_xy_bounds_m']
        rider_hits=[i for i,s in enumerate(samples) if crosses(s['rider_body_xy'],box)]
        ego_hits=[i for i,s in enumerate(samples) if crosses(s['ego_body_xy'],box)]
        assert rider_hits and ego_hits
        measured=report['measurements']['rider_conflict_observation']['value']
        assert measured['last_rider_frame']==samples[rider_hits[-1]]['native_frame']==item['last_rider_frame']
        assert measured['first_ego_frame']==samples[ego_hits[0]]['native_frame']==item['first_ego_frame']
        assert measured['simultaneous_conflict_frames']==len(set(rider_hits)&set(ego_hits))==item['simultaneous_conflict_frames']
        assert measured['ego_entered_after_rider_cleared']==(ego_hits[0]>rider_hits[-1])==(response=='clear')
        evidence[(rider_type,response,candidate)]={
            'rider_trace':[(s['rider_body_xy'],s['rider_speed_mps']) for s in samples],
            'ego_trace':[(s['ego_body_xy'],s['ego_speed_mps']) for s in samples],
            'rider_last_index':rider_hits[-1],
            'ego_first_index':ego_hits[0]}
    assert len(evidence)==24
    for rider_type in RIDERS:
        for candidate in CANDIDATES:
            clear=evidence[(rider_type,'clear',candidate)]
            conflict=evidence[(rider_type,'conflict',candidate)]
            assert clear['rider_trace']==conflict['rider_trace']
            assert clear['rider_last_index']==conflict['rider_last_index']==217
            assert clear['ego_first_index']==262 and conflict['ego_first_index']==187
            assert clear['ego_trace']!=conflict['ego_trace']
    retained_path=HERE/'rider-package-saved-receipts.json'
    retained=read(retained_path)
    assert retained['passed'] is True and retained['matrix_sha256']==sha(summary_path)
    assert len(retained['rows'])==24
    for row in retained['rows']:
        suffix=row['case_id'].rsplit('__',1)[-1]
        folder=HERE/'draft-rider-cases'/suffix/row['candidate_id']
        item=next(x for x in summary['results']
                  if x['case_id']==row['case_id'] and x['candidate_id']==row['candidate_id'])
        assert row['construction_sha256']==item['construction_sha256']
        assert all(sha(folder/name)==digest for name,digest in row['retained'].items())
        assert row['retained']['package-receipt.json']==item['positive_receipt_sha256']
        assert row['retained']['package-negative.log']==item['negative_log_sha256']
    result={'format':'c10052-rider-package-matrix-independent-audit-v1',
        'passed':True,'cases':6,'candidates':24,'controlled_pairs':12,
        'matrix_sha256':sha(summary_path),'retained_receipts_sha256':sha(retained_path),
        'manifest_sha256':sha(HERE/'draft-rider-execution-manifest.json'),
        'source_scope':'synthetic v1 software compatibility only',
        'original_native_capture_executed':False,'selected':False,'accepted':False}
    (HERE/'rider-package-matrix-independent-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(audit(),indent=2))
