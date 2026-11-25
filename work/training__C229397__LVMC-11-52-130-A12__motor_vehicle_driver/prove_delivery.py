"""CPU test of the saved finalizer output protocol and missing-source rejection."""
import json
from pathlib import Path
import tempfile

from finalize_delivery import finalize
from prove_saved import write_attempt


def main():
    here = Path(__file__).resolve().parent
    construction = json.loads((here / 'draft-crosswalk/controlled_2/primary/construction.json').read_text())
    config = next(json.loads(item['content']) for item in construction['files']
                  if item['path'] == 'config.json')
    with tempfile.TemporaryDirectory(prefix='c229397-delivery-') as temporary:
        good = Path(temporary) / 'good'
        good.mkdir()
        write_attempt(good)
        (good / 'config.json').write_text(json.dumps(config) + '\n')
        report = finalize(good, good / 'analysis-report.json')
        result = json.loads((good / 'result.json').read_text())
        if report['case_id'] != config['case_id'] or result['case_id'] != config['case_id']:
            raise ValueError('Exact case result identity differs')
        if result['target_checks'][0]['measured'] != 3 or report['measurements']['crosswalk_position']['value']['minimum_body_gap_m'] != 3:
            raise ValueError('Saved body gap differs')
        if result['maneuver_completed'] or result['legal_verdict_claimed'] or report['physical_acceptance_claimed']:
            raise ValueError('Fixture asserted physical or legal acceptance')
        expected_channels = {c['name'] for c in config['recording_description']['channels'] +
                             config['recording_description']['context_inputs']}
        if set(item['name'] for item in result['recording_evidence']) != expected_channels:
            raise ValueError('Derived channel inventory differs')
        try:
            finalize(good, good / 'analysis-report.json')
        except ValueError as exc:
            if str(exc) != 'Retain prior analysis report or result':
                raise
        else:
            raise ValueError('Repeated finalization accepted')
        bad = Path(temporary) / 'bad'
        bad.mkdir()
        write_attempt(bad)
        (bad / 'config.json').write_text(json.dumps(config) + '\n')
        (bad / 'control-intent.jsonl').unlink()
        try:
            finalize(bad, bad / 'analysis-report.json')
        except ValueError as exc:
            if str(exc) != 'Missing required source: control-intent.jsonl':
                raise
        else:
            raise ValueError('Missing original control source accepted')
    print(json.dumps({'passed': True, 'case_id': config['case_id'],
                      'synthetic_body_gap_m': 3,
                      'checks': ['result writer protocol', 'derived channels',
                                 'retained-result rejection', 'missing control-source rejection'],
                      'physical_acceptance_claimed': False, 'legal_verdict_claimed': False},
                     sort_keys=True))


if __name__ == '__main__':
    main()
