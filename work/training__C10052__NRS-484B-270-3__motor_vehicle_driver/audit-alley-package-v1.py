"""Independently audit four exact unselected alley v1 positives and negatives."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0,str(REPO/'runtime/pipeline'))
from scenario_pipeline.worker_exchange.common import tree,digest


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    work_manifest = HERE/'draft-alley-execution-manifest.json'
    data = json.loads(work_manifest.read_text())
    entry = data['cases'][0]
    rows = []
    source_hashes = None
    decoded_sequences = None
    for ident in ('primary','fallback1','fallback2','fallback3'):
        summary = json.loads((HERE/('alley-package-'+ident+'-summary.json')).read_text())
        root = REPO/summary['source_root']
        positive = root/'positive'
        negative = root/'negative'
        expected = entry if ident == 'primary' else next(
            c for c in entry['candidates'] if c['id']==ident)
        assert summary['selected'] is False and summary['accepted'] is False
        assert summary['manifest_sha256'] == sha(work_manifest)
        assert sha(root/'package/draft-alley-execution-manifest.json') == sha(work_manifest)
        source = HERE/expected['construction']
        copied = root/'package'/expected['construction']
        assert sha(source) == sha(copied) == expected['construction_sha256']
        assert summary['construction_sha256'] == expected['construction_sha256']
        assert sha(positive/'compatibility.json') == summary['positive_receipt_sha256']
        receipt = json.loads((positive/'compatibility.json').read_text())
        assert receipt['format'] == 'worker-package-compatibility-v1'
        assert receipt['passed'] is True and receipt['case_id'] == entry['case_id']
        assert receipt['candidate_id'] == ident
        assert receipt['construction_sha256'] == expected['construction_sha256']
        assert receipt['runtime_manifest_sha256'] == data['runtime_manifest_sha256']
        assert {'actual_analysis','native_validation','mandatory_observations',
                'lean_decoder','render','final_decode','acquisition_unchanged'} <= set(receipt['checks'])
        assert sha(positive/'compatibility-analysis.log') == receipt['log_sha256']
        assert digest(tree(root/'fixture')) == receipt['fixture_sha256'] == summary['fixture_sha256']
        current_sources = {name:sha(root/'fixture'/name) for name in
            ('native_samples.jsonl','road_geometry.json','trace.jsonl',
             'capture/evidence.jsonl','alley-transition-sources.json')}
        if source_hashes is None: source_hashes = current_sources
        else: assert current_sources == source_hashes
        report = json.loads((positive/'analysis-report.json').read_text())
        value = report['measurements']['alley_transition_observation']['value']
        assert value['source_kind'] == 'synthetic_cpu_fixture'
        assert value['first_facility_entry_native_frame'] == 170
        assert value['first_alley_footprint_native_frame'] == 201
        assert value['simultaneous_moving_overlap_frames'] == 27
        result = json.loads((positive/'result.json').read_text())
        assert result['accepted'] is False and result['legal_verdict_claimed'] is False
        assert result['measured_values']['simultaneous_moving_overlap_frames'] == 27
        config = json.loads((positive/'config.json').read_text())
        sequences = []
        for index,camera in enumerate(config['cameras']):
            source_audit = json.loads((positive/f'source-{index}.json').read_text())
            assert source_audit['passed'] is True and source_audit['frames'] == 480
            assert source_audit['dimensions'] == [camera['width'],camera['height']]
            sequences.append(source_audit['rgb_sequence_sha256'])
        if decoded_sequences is None: decoded_sequences = sequences
        else: assert sequences == decoded_sequences
        final = json.loads((positive/'final-decode.json').read_text())
        assert final['passed'] is True and final['frames'] == 480
        assert summary['negative_exit_code'] != 0
        assert sha(root/'negative.log') == summary['negative_log_sha256']
        assert 'alley-transition-sources.json' in (root/'negative.log').read_text()
        assert not (negative/'alley-transition-sources.json').exists()
        assert not (negative/'result.json').exists()
        rows.append({'candidate_id':ident,'construction_sha256':expected['construction_sha256'],
                     'positive_receipt_sha256':summary['positive_receipt_sha256'],
                     'negative_log_sha256':summary['negative_log_sha256']})
    return {'format':'c10052-alley-independent-v1-audit','passed':True,
            'case_id':entry['case_id'],'positive_count':4,'negative_count':4,
            'held_source_hashes':source_hashes,
            'held_decoded_video_sequences':decoded_sequences,
            'rows':rows,'selected':False,'accepted':False}


if __name__=='__main__':
    print(json.dumps(audit(),indent=2))
