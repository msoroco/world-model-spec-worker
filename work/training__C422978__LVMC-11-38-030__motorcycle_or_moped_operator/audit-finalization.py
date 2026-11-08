"""Independent audit of exact bundled synthetic finalization evidence."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    manifest_path = HERE / 'draft-execution-manifest.json'
    proof_path = HERE / 'exact-finalization-proof.json'
    manifest, proof = read(manifest_path), read(proof_path)
    assert proof['manifest_sha256'] == sha(manifest_path)
    assert len(proof['results']) == 8 and not proof['core_video_or_original_native_claimed']
    audited = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            ref = entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate)
            construction = read(HERE / ref['construction'])
            files = {row['path']: row['content'] for row in construction['files']}
            assert ref['construction_sha256'] == sha(HERE / ref['construction'])
            assert files['finalize.py'] == (HERE / 'native/finalize.py').read_text()
            assert files['measure_saved.py'] == (HERE / 'native/measure_saved.py').read_text()
            assert files['measure_context.py'] == (HERE / 'native/measure_context.py').read_text()
            row = next(row for row in proof['results'] if row['case_id'] == entry['case_id']
                       and row['candidate_id'] == candidate)
            assert row['construction_sha256'] == ref['construction_sha256']
            folder = HERE / 'draft-candidates' / suffix / candidate
            analysis_path, result_path = folder / 'finalization-analysis.json', folder / 'finalization-result.json'
            assert row['analysis_sha256'] == sha(analysis_path)
            assert row['result_sha256'] == sha(result_path)
            assert row['negative_log_sha256'] == sha(folder / 'finalization-negative.log')
            assert row['context_negative_log_sha256'] == sha(folder / 'finalization-context-negative.log')
            assert row['measurement_contract_sha256'] == sha(HERE / 'native/measurement-contract.json')
            assert 'Missing required source: native-observed.jsonl' in (folder / 'finalization-negative.log').read_text()
            assert 'Missing required source: city-context.json' in (folder / 'finalization-context-negative.log').read_text()
            analysis, result = read(analysis_path), read(result_path)
            source = HERE / 'native/saved-fixtures' / suffix / candidate
            measured = read(source / 'analysis-report.json')
            context = read(HERE / 'native/context-fixtures' / suffix / candidate / 'context-measurement.json')
            expected = dict(measured)
            expected['spatial_context'] = context
            expected['source_hashes'] = dict(measured['source_hashes'],
                **{'city-context.json': sha(HERE / 'native/context-fixtures' / suffix / candidate / 'city-context.json')})
            assert analysis['measurements']['motorcycle_sidewalk_occupancy']['value'] == expected
            assert analysis['measurements']['motorcycle_sidewalk_occupancy']['sources'] == expected['source_hashes']
            assert context['city_authority_reviewed'] is False and context['legal_verdict'] is None
            assert analysis['selected'] is False and analysis['draft_only'] is True
            assert result['case_id'] == entry['case_id'] and result['accepted'] is False
            assert result['provenance_kind'] == 'synthetic_local_diagnostic'
            assert result['target_checks'][0]['matched'] is True
            assert result['target_checks'][0]['requested'] == (suffix == 'witness_2')
            assert result['target_checks'][0]['measured'] == bool(measured['moving_sidewalk_overlap_frames'])
            assert len(lines(source / 'native-observed.jsonl')) == 480
            assert len(lines(source / 'video_frames.jsonl')) == 480
            audited.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                            'analysis_sha256': row['analysis_sha256'],
                            'result_sha256': row['result_sha256']})
    output = {'format': 'c422978-independent-finalization-audit-v1',
              'manifest_sha256': sha(manifest_path), 'proof_sha256': sha(proof_path),
              'audited': audited, 'original_native_or_delivery_acceptance_claimed': False}
    (HERE / 'exact-finalization-audit.json').write_text(json.dumps(output, indent=2) + '\n')
    return output


if __name__ == '__main__':
    print(json.dumps({'audited': len(audit()['audited'])}))
