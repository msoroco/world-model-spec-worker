"""Check source-bound software receipts for the unselected motion fallbacks."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def files(bundle):
    return {f['path']: f['content'] for f in bundle['files']}


def main():
    manifest = read(HERE / 'current-diagnostic-manifest.json')
    records = []
    for condition, expected_gap in (('condition_a', 10.0), ('condition_b', 25.0)):
        entry = next(c for c in manifest['cases'] if c['case_id'].endswith(condition))
        primary_path = HERE / entry['construction']
        primary = read(primary_path)
        assert sha(primary_path) == entry['construction_sha256']
        pf = files(primary)
        for candidate_id in ('fallback1', 'fallback2'):
            candidate = next(c for c in entry['candidates'] if c['id'] == candidate_id)
            construction_path = HERE / candidate['construction']
            construction = read(construction_path)
            assert candidate['construction_sha256'] == sha(construction_path)
            assert construction['case_id'] == primary['case_id'] == entry['case_id']
            cf = files(construction)
            for name in ('runner.py', 'geometry.py', 'engineering.py',
                         'measure_following.py', 'finalize.py'):
                assert pf[name] == cf[name]
            pconfig, cconfig = json.loads(pf['config.json']), json.loads(cf['config.json'])
            assert {k for k in pconfig if pconfig[k] != cconfig[k]} == {'candidate_id'}
            assert pconfig['candidate_id'] == 'primary'
            assert cconfig['candidate_id'] == candidate_id
            suffix = condition[-1]
            base = ROOT / f'.runtime-work/c102304-owner204-compat-{suffix}-{candidate_id}'
            saved = ROOT / f'.runtime-work/c102304-owner204-saved-{suffix}-{candidate_id}/v0001'
            compat, processing = read(base / 'compatibility.json'), read(saved / 'processing.json')
            assert compat['passed'] is True and compat['case_id'] == entry['case_id']
            assert compat['candidate_id'] == candidate_id
            assert compat['construction_sha256'] == sha(construction_path)
            assert compat['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256']
            assert compat['fixture_recipe_sha256'] == sha(ROOT / candidate['fixture_recipe'])
            assert compat['negative_removed'] == 'native_samples.jsonl'
            assert compat['negative_log_sha256'] == sha(base / 'negative-analysis.log')
            assert compat['negative_error_contains'] in (base / 'negative-analysis.log').read_text()
            assert processing['passed'] is True and processing['recorded_only'] is True
            assert processing['case_id'] == entry['case_id']
            assert processing['candidate_id'] == candidate_id
            assert processing['analysis_revision']['construction_sha256'] == sha(construction_path)
            assert processing['timestamp_joins']['passed'] is True
            assert processing['timestamp_joins']['frames'] == 900
            assert processing['final_video_checks']['passed'] is True
            assert processing['final_video_checks']['frames'] == 900
            assert processing['originals_preserved'] is True
            assert processing['physical_acceptance_claimed'] is False
            assert processing['legal_acceptance_claimed'] is False
            measured = read(base / 'analysis-report.json')['measurements']['moving_following_interval']['value']
            assert measured['median_bumper_gap_m'] == expected_gap
            records.append({
                'condition': condition, 'candidate_id': candidate_id,
                'construction_sha256': sha(construction_path),
                'recipe_sha256': sha(ROOT / candidate['fixture_recipe']),
                'compatibility_sha256': sha(base / 'compatibility.json'),
                'negative_log_sha256': sha(base / 'negative-analysis.log'),
                'process_saved_sha256': sha(saved / 'processing.json'),
                'median_bumper_gap_m': expected_gap,
            })
    result = {
        'format': 'c102304-current-motion-fallback-audit-v1',
        'passed': True, 'manifest_sha256': sha(HERE / 'current-diagnostic-manifest.json'),
        'records': records, 'fixture_scope': 'synthetic software diagnostics',
        'native_motion_claimed': False, 'legal_outcome_claimed': False,
    }
    target = HERE / 'current-motion-fallback-audit.json'
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'records': len(records), 'receipt_sha256': sha(target)}))


if __name__ == '__main__':
    main()
