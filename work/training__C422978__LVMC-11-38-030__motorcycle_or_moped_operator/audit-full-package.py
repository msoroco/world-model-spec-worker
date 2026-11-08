"""Independent exact C422978 synthetic Core/Lean/video receipt audit."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUIRED = {'actual_analysis', 'native_validation', 'mandatory_observations',
            'lean_decoder', 'render', 'final_decode', 'acquisition_unchanged'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit():
    manifest_path = HERE / 'draft-execution-manifest.json'
    manifest, summary = read(manifest_path), read(HERE / 'full-package-summary.json')
    proposals = read(HERE / 'proposals/cases.json')
    assert summary['manifest_sha256'] == sha(manifest_path)
    assert len(summary['results']) == 8
    assert summary['original_native_or_delivery_acceptance_claimed'] is False
    assert proposals['status'] == 'unselected_cpu_draft'
    assert {case['case_id'] for case in proposals['cases']} == {
        case['case_id'] for case in manifest['cases']}
    indexed = {(r['case_id'], r['candidate_id']): r for r in summary['results']}
    assert len(indexed) == 8
    audited = []
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            row = indexed[(entry['case_id'], candidate)]
            ref = entry if candidate == 'primary' else next(
                r for r in entry['candidates'] if r['id'] == candidate)
            construction_path = HERE / ref['construction']
            assert ref['construction_sha256'] == row['construction_sha256'] == sha(construction_path)
            construction = read(construction_path)
            proposal = next(p for p in proposals['cases'] if p['case_id'] == entry['case_id'])
            assert proposal['recording_description'] == construction['recording_description']
            files = {p['path']: p['content'] for p in construction['files']}
            assert files['authored-road.xodr'] == (HERE / 'native/road.xodr').read_text()
            assert files['finalize.py'] == (HERE / 'native/finalize.py').read_text()
            folder = HERE / 'draft-candidates' / case / candidate
            assert row == read(folder / 'full-package-proof.json')
            assert row['compatibility_sha256'] == sha(folder / 'full-compatibility.json')
            assert row['final_decode_sha256'] == sha(folder / 'full-final-decode.json')
            assert row['negative_log_sha256'] == sha(folder / 'full-negative.log')
            assert row['negative_error'] in (folder / 'full-negative.log').read_text()
            receipt = read(folder / 'full-compatibility.json')
            assert receipt['format'] == 'worker-package-compatibility-v1'
            assert receipt['passed'] is True and REQUIRED <= set(receipt['checks'])
            assert receipt['checks'] == row['positive_checks']
            assert receipt['case_id'] == entry['case_id']
            assert receipt['candidate_id'] == candidate
            assert receipt['construction_sha256'] == ref['construction_sha256']
            assert receipt['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256']
            assert receipt['analysis_sha256'] == hashlib.sha256(files['finalize.py'].encode()).hexdigest()
            assert receipt['scope'] == 'diagnostic software compatibility only'
            decode = read(folder / 'full-final-decode.json')
            assert decode['passed'] is True and decode['frames'] == 480
            log = (folder / 'full-package-command.log').read_text().splitlines()
            scratch_lines = [line for line in log if line.startswith('scratch ')]
            assert len(scratch_lines) == 1
            scratch = Path(scratch_lines[0].removeprefix('scratch '))
            result = read(scratch / 'output/result.json')
            assert result['case_id'] == entry['case_id']
            assert result['provenance_kind'] == 'synthetic_local_diagnostic'
            assert result['accepted'] is False and result['setup_confirmed'] is False
            assert result['target_checks'][0]['physical_cause_confirmed'] is False
            assert sha(scratch / 'output/compatibility-analysis.log') == receipt['log_sha256']
            assert (scratch / 'output/converted/atom_contract.json').is_file()
            assert (scratch / 'output/converted/trace.json').is_file()
            measured = read(scratch / 'output/analysis-report.json')['measurements']['motorcycle_sidewalk_occupancy']['value']
            assert bool(measured['moving_sidewalk_overlap_frames']) == (case == 'witness_2')
            audited.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                            'construction_sha256': ref['construction_sha256'],
                            'compatibility_sha256': row['compatibility_sha256']})
    result = {'format': 'c422978-independent-full-package-audit-v1',
              'manifest_sha256': sha(manifest_path),
              'summary_sha256': sha(HERE / 'full-package-summary.json'),
              'positive_count': len(audited), 'negative_count': len(audited),
              'audited': audited, 'original_native_or_delivery_acceptance_claimed': False}
    (HERE / 'full-package-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps({'audited': len(audit()['audited'])}))
