"""Independent checks of eight unselected, synthetic exact-package diagnostics."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = json.loads((HERE / 'draft-execution-manifest.json').read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def main():
    records = []
    controlled = {}
    for suffix in ('reference', 'contrast'):
        case = next(x for x in MANIFEST['cases'] if x['case_id'].endswith('__' + suffix))
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            log = HERE / f'package-{suffix}-{candidate}.log'
            statement = json.loads(log.read_text().splitlines()[-1])
            root = Path(statement['scratch'])
            output = root / 'output'
            receipt = json.loads((output / 'compatibility.json').read_text())
            selected = case if candidate == 'primary' else next(x for x in case['candidates'] if x['id'] == candidate)
            construction = HERE / selected['construction']
            assert receipt['format'] == 'worker-package-compatibility-v1' and receipt['passed'] is True
            assert receipt['runtime_manifest_sha256'] == MANIFEST['runtime_manifest_sha256']
            assert receipt['construction_sha256'] == selected['construction_sha256'] == sha(construction)
            assert receipt['case_id'] == case['case_id'] and receipt['candidate_id'] == candidate
            assert receipt['analysis_sha256'] == sha(output / 'finalize.py')
            assert receipt['log_sha256'] == sha(output / 'compatibility-analysis.log')
            assert statement['negative']['exit_code'] != 0
            negative_log = (root / 'negative-analysis.log').read_text()
            assert statement['negative']['error_contains'] in negative_log
            result = json.loads((output / 'result.json').read_text())
            assert result['accepted'] is False and result['setup_confirmed'] is False
            assert result['behavior_attempted'] is False and result['maneuver_completed'] is False
            assert result['legal_verdict_claimed'] is False
            assert result['provenance_kind'] == 'synthetic_local_diagnostic'
            scenes = json.loads((output / 'converted/trace.json').read_text())['scenes']
            assert len(scenes) == 240
            crosswalk_ids = {r['id'] for r in scenes[0]['structures'] if r['kind'] == 'crosswalk'}
            assert len(crosswalk_ids) == 1
            crosswalk_id = next(iter(crosswalk_ids))
            occupancy = sum([107, crosswalk_id] in s['occupies'] for s in scenes)
            assert occupancy == 126
            assert all(any(u['track'] == 107 and 'pedestrian' in u['classes'] for u in s['users']) for s in scenes)
            assert json.loads((output / 'final-decode.json').read_text())['passed'] is True
            assert len(rows(output / 'capture/evidence.jsonl')) == 240
            assert len(rows(output / 'native_samples.jsonl')) == 240
            if candidate == 'primary':
                controlled[suffix] = scenes
            records.append({'suffix': suffix, 'candidate': candidate, 'core_frames': 240,
                            'crosswalk_overlap_frames': occupancy,
                            'positive_receipt_sha256': sha(output / 'compatibility.json'),
                            'negative_log_sha256': sha(root / 'negative-analysis.log'),
                            'command_log_sha256': sha(log)})
    reference, contrast = controlled['reference'], controlled['contrast']
    for a, b in zip(reference, contrast):
        assert a['t'] == b['t'] and a['structures'] == b['structures']
        left = next(u for u in a['users'] if u['track'] == 107)['kin']
        right = next(u for u in b['users'] if u['track'] == 107)['kin']
        assert abs(left['position'][0] - right['position'][0]) < 1e-9
        assert abs(left['position'][1] - right['position'][1] - 1.3) < 1e-9
        assert left['heading'] == right['heading']
    summary = {'format': 'c10316-synthetic-exact-package-audit-v1', 'records': records,
               'controlled_core_lateral_shift_m': 1.3,
               'scope': 'v1 software diagnostics only; no selected case, Native observation or acceptance'}
    (HERE / 'draft-package-crosswalk-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'exact_v1_positives': len(records), 'missing_source_negatives': len(records),
                      'crosswalk_overlap_frames_per_capture': 126, 'selected_cases': 0,
                      'accepted_recordings': 0}))


if __name__ == '__main__':
    main()
