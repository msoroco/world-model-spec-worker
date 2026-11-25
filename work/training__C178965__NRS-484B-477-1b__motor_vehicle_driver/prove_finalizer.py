"""Exercise the exact saved analyzer without claiming a physical recording."""
import json
from pathlib import Path
import tempfile

from finalize_alley import finalize_package
from prove_saved import write_attempt


def main():
    here = Path(__file__).resolve().parent
    measurements = {}
    with tempfile.TemporaryDirectory(prefix='c178965-finalizer-') as directory:
        root = Path(directory)
        for suffix, width in (('controlled_1', 7.5),
                              ('controlled_at_10', 6.648), ('controlled_2', 6.0)):
            attempt = root / suffix
            attempt.mkdir()
            write_attempt(attempt, width)
            bundle = here / 'draft-alley' / suffix / 'primary' / 'construction.json'
            proposal = json.loads(bundle.read_text())
            config = next(item['content'] for item in proposal['files'] if item['path'] == 'config.json')
            (attempt / 'config.json').write_text(config)
            (attempt / 'acquisition-provenance.json').write_text(
                json.dumps({'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
            report = finalize_package(attempt, attempt / 'analysis-report.json')
            result = json.loads((attempt / 'result.json').read_text())
            value = report['measurements']['source_bound_alley_width']['value']
            measurements[suffix] = value['minimum_measured_halt_free_width_m']
            if result['setup_confirmed'] or result['maneuver_completed'] or result['accepted']:
                raise ValueError('Synthetic saved source claimed physical completion')
            if len(list((attempt / 'channels').glob('*.jsonl'))) != 2:
                raise ValueError('Declared source channels were not derived')
            if result['provenance_kind'] != 'synthetic_fixture' or result['legal_verdict_claimed']:
                raise ValueError('Synthetic provenance or legal status differs')
        if not measurements['controlled_1'] > 3.048 or not measurements['controlled_2'] < 3.048:
            raise ValueError('Selected saved contrast differs')
        if abs(measurements['controlled_at_10'] - 3.048) > 1e-9:
            raise ValueError('Exact boundary saved result differs')
    print(json.dumps({'passed': True, 'case_widths_m': measurements,
                      'synthetic_fixture_only': True, 'physical_completion_claimed': False,
                      'legal_verdict_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
