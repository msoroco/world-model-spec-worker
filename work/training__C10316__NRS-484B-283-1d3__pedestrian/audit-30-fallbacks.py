"""Independent source and receipt audit for the current draft fallback pair."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    proof = json.loads((HERE / 'fallback-30-proof.json').read_text())
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    assert proof['manifest_sha256'] == sha(HERE / 'draft-execution-manifest.json')
    assert proof['selected'] is False and proof['physical_signal_observed'] is False
    by_case = {entry['case_id']: entry for entry in manifest['cases']}
    seen = set()
    audited = []
    for record in proof['records']:
        key = (record['case_id'], record['candidate'])
        assert key not in seen
        seen.add(key)
        case = by_case[record['case_id']]
        candidate = next(x for x in case['candidates'] if x['id'] == record['candidate'])
        assert record['construction_sha256'] == candidate['construction_sha256']
        assert sha(HERE / candidate['construction']) == candidate['construction_sha256']
        assert sha(ROOT / case['fixture_recipe']) == json.loads(
            (ROOT / record['compatibility_receipt']).read_text())['fixture_recipe_sha256']
        assert sha(HERE / record['compatibility_log']) == record['compatibility_log_sha256']
        assert sha(HERE / record['saved_log']) == record['saved_log_sha256']
        compatibility_path = ROOT / record['compatibility_receipt']
        saved_path = ROOT / record['saved_receipt']
        assert sha(compatibility_path) == record['compatibility_receipt_sha256']
        assert sha(saved_path) == record['saved_receipt_sha256']
        compatibility = json.loads(compatibility_path.read_text())
        saved = json.loads(saved_path.read_text())
        assert compatibility['passed'] is True
        assert compatibility['case_id'] == case['case_id']
        assert compatibility['candidate_id'] == candidate['id']
        assert compatibility['construction_sha256'] == candidate['construction_sha256']
        assert compatibility['negative_removed'] == 'no-countdown-samples.jsonl'
        negative = compatibility_path.parent / 'negative-analysis.log'
        assert sha(negative) == compatibility['negative_log_sha256'] == record['negative_log_sha256']
        assert compatibility['negative_error_contains'] in negative.read_text()
        analysis = json.loads((compatibility_path.parent / 'analysis-report.json').read_text())
        measured = analysis['measurements']['no_countdown_entry_and_clearance']['value']
        assert measured['original_frames'] == 600
        assert measured['source_kind'] == 'synthetic_scene_request'
        assert measured['governing_device_observed'] is False
        expected = 'walk' if case['case_id'].endswith('controlled_1') else 'dont_walk_flashing'
        assert measured['entry_indication'] == expected
        assert measured['first_entry']['first_frame'] == 118
        assert measured['steady_start']['first_frame'] == 280
        assert saved['passed'] is True and saved['recorded_only'] is True
        assert saved['case_id'] == case['case_id'] and saved['candidate_id'] == candidate['id']
        assert saved['timestamp_joins']['frames'] == 600
        assert saved['final_video_checks']['frames'] == 600
        assert saved['physical_acceptance_claimed'] is False
        assert saved['legal_acceptance_claimed'] is False
        audited.append({'case_id': case['case_id'], 'candidate': candidate['id'],
                        'compatibility_receipt_sha256': sha(compatibility_path),
                        'saved_receipt_sha256': sha(saved_path)})
    assert seen == {(case_id, candidate) for case_id in by_case
                    for candidate in ('fallback1', 'fallback2', 'fallback3')}
    result = {'format': 'c10316-current-30-second-fallback-independent-audit',
              'passed': True, 'selected': False, 'physical_signal_observed': False,
              'records': audited}
    path = HERE / 'fallback-30-audit.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'audited': len(audited), 'receipt_sha256': sha(path)}))


if __name__ == '__main__':
    main()
