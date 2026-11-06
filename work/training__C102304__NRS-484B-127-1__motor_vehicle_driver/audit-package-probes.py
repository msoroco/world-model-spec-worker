"""Independent eight-receipt/source/negative audit of unselected v1 probes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    manifest = json.loads((HERE/'draft-execution-manifest.json').read_text())
    records = []
    expected_checks = {'actual_analysis','native_validation','mandatory_observations',
                       'lean_decoder','render','final_decode','acquisition_unchanged'}
    for suffix,label in (('condition_a','a'),('condition_b','b')):
        case = next(item for item in manifest['cases'] if item['case_id'].endswith('__'+suffix))
        fixture_hash = None
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            log = ROOT/'work/_shared'/f'c102304-package-{label}-{candidate}.log'
            if candidate == 'primary' and label == 'a':
                log = ROOT/'work/_shared/c102304-package-primary.log'
            lines = log.read_text().splitlines()
            scratch = Path(lines[0].removeprefix('scratch '))
            assert scratch.is_relative_to(ROOT/'.runtime-work') and scratch.is_dir()
            row = json.loads(lines[-1])
            receipt = json.loads((scratch/'output/compatibility.json').read_text())
            assert row['positive'] == {k:v for k,v in receipt.items() if k != 'fixture_manifest'}
            assert receipt['format'] == 'worker-package-compatibility-v1'
            assert receipt['passed'] is True and set(receipt['checks']) == expected_checks
            assert receipt['case_id'] == case['case_id'] and receipt['candidate_id'] == candidate
            selected = case if candidate == 'primary' else next(
                x for x in case['candidates'] if x['id'] == candidate)
            assert receipt['construction_sha256'] == selected['construction_sha256']
            assert receipt['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256']
            output = scratch/'output'
            assert sha(output/'compatibility-analysis.log') == receipt['log_sha256']
            if fixture_hash is None:
                fixture_hash = receipt['fixture_sha256']
            assert receipt['fixture_sha256'] == fixture_hash
            assert row['negative']['removed'] == 'native_samples.jsonl'
            assert row['negative']['exit_code'] != 0
            negative = (scratch/'negative-analysis.log').read_text()
            assert row['negative']['error_contains'] in negative
            assert not (scratch/'negative/native_samples.jsonl').exists()
            result = json.loads((output/'result.json').read_text())
            assert result['accepted'] is False and result['legal_verdict_claimed'] is False
            assert result['provenance_kind'] == 'synthetic_local_diagnostic'
            assert all(result[k] is False for k in ('setup_confirmed','behavior_attempted','maneuver_completed'))
            assert result['measured_values']['median_bumper_gap_m'] == (10 if label=='a' else 25)
            assert json.loads((output/'analysis-report.json').read_text())['original_joins']['frames'] == 900
            for i in range(4):
                video = json.loads((output/f'source-{i}.json').read_text())
                assert video['passed'] is True and video['frames'] == 900
            final = json.loads((output/'final-decode.json').read_text())
            assert final['passed'] is True and final['frames'] == 900
            records.append({'case_id':case['case_id'],'candidate_id':candidate,
                            'positive_log':str(log.relative_to(ROOT)),
                            'positive_log_sha256':sha(log),
                            'compatibility_receipt_sha256':sha(output/'compatibility.json'),
                            'negative_log_sha256':sha(scratch/'negative-analysis.log'),
                            'fixture_sha256':fixture_hash,
                            'scope':'unselected v1 diagnostic; strict v2 not established'})
    assert len(records) == 8
    (HERE/'draft-package-probe-summary.json').write_text(json.dumps({
        'format':'c102304-unselected-v1-package-probe-summary',
        'runtime_manifest_sha256':manifest['runtime_manifest_sha256'],
        'records':records},indent=2)+'\n')
    print(json.dumps({'audit':'pass','exact_v1_positives':8,
                      'packaged_missing_source_negatives':8,
                      'source_videos_decoded':32,'selected_cases':0},sort_keys=True))


if __name__ == '__main__':
    main()
