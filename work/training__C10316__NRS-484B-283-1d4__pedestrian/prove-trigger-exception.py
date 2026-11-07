"""Synthetic CPU exercise of all three saved-source fallback conditions."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from engineering_exception import evaluate_fallbacks


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))


def main():
    records = json.loads((HERE / 'exception-summary.json').read_text())['records']
    root = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c10316-trigger-'))
    results = []
    for record in records:
        source = Path(record['retained_positive'])
        folder = root / record['case_suffix']
        shutil.copytree(source, folder)
        samples, context = folder / 'exception-samples.jsonl', folder / 'exception-context.json'
        measured = json.loads((folder / 'source-measurement.json').read_text())
        baseline = evaluate_fallbacks(samples, context)
        assert baseline['gates']['fallback1']['advance'] is True
        assert baseline['gates']['fallback1']['observed'] == .88
        cases = []
        for label, skew, legibility, expected in (
            ('clear', 10, .99, (False, False)),
            ('phase-skew', 30, .99, (True, False)),
            ('illegible', 10, .90, (False, True))):
            audit = folder / (label + '-pixel-audit.json')
            audit.write_text(json.dumps({'audit_kind': 'synthetic_diagnostic',
                'source_sha256': measured['source_sha256'],
                'phase_skew_ms': skew, 'display_legibility': legibility}, indent=2) + '\n')
            result = evaluate_fallbacks(samples, context, audit)
            assert tuple(result['gates'][key]['advance'] for key in ('fallback2', 'fallback3')) == expected
            assert result['physical_triggers_observed'] is False and result['legal_verdict_claimed'] is False
            cases.append({'label': label, 'audit': str(audit), 'result': result})
        bad = folder / 'wrong-source-pixel-audit.json'
        bad.write_text(json.dumps({'audit_kind': 'synthetic_diagnostic',
            'source_sha256': {}, 'phase_skew_ms': 30, 'display_legibility': .9}) + '\n')
        try:
            evaluate_fallbacks(samples, context, bad)
        except ValueError as error:
            assert 'source hashes differ' in str(error)
        else:
            raise AssertionError('Changed source accepted')
        forged = folder / 'forged-original-pixel-audit.json'
        forged.write_text(json.dumps({'audit_kind': 'independent_original_pixel_audit',
            'source_sha256': measured['source_sha256'], 'phase_skew_ms': 30,
            'display_legibility': .9}) + '\n')
        try:
            evaluate_fallbacks(samples, context, forged)
        except ValueError as error:
            assert 'needs Native source' in str(error)
        else:
            raise AssertionError('Synthetic source accepted as original-pixel evidence')
        altered = root / (record['case_suffix'] + '-more-clearance')
        shutil.copytree(source, altered)
        rows = [json.loads(line) for line in (altered / 'exception-samples.jsonl').read_text().splitlines()]
        rows[0]['pedestrian_xy_m'][0] -= 2
        for vertex in rows[0]['pedestrian_footprint_xy_m']:
            vertex[0] -= 2
        write_rows(altered / 'exception-samples.jsonl', rows)
        farther = evaluate_fallbacks(altered / 'exception-samples.jsonl',
                                     altered / 'exception-context.json')
        assert farther['gates']['fallback1']['observed'] == 2.88
        assert farther['gates']['fallback1']['advance'] is False
        results.append({'case_suffix': record['case_suffix'], 'source': str(folder),
                        'baseline': baseline, 'pixel_diagnostics': cases,
                        'more_clearance_source': str(altered), 'more_clearance': farther,
                        'changed_source_negative': 'Display audit source hashes differ',
                        'forged_original_pixel_negative': 'Original pixel audit needs Native source'})
    output = {'format': 'c10316-prior-entry-synthetic-trigger-proof-v1',
              'retained_root': str(root), 'records': results,
              'physical_triggers_observed': 0, 'accepted_recordings': 0}
    (HERE / 'exception-trigger-summary.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'cases': len(results), 'synthetic_trigger_decisions': 8,
                      'changed_source_rejections': 2, 'forged_original_pixel_rejections': 2,
                      'physical_triggers_observed': 0}))


if __name__ == '__main__':
    main()
