"""Exercise factual finalization from 600 joined rows and rejected permit source."""
import json
import os
import tempfile
from pathlib import Path

from finalize import finalize
from prove_source_contract import build, CASE

HERE = Path(__file__).resolve().parent


def prepare(folder):
    build(folder)
    (folder / 'config.json').write_text((HERE / 'config.json').read_text())
    with (folder / 'trace.jsonl').open('w') as stream:
        for index in range(600):
            stream.write(json.dumps({'frame': index+100, 'time_s': index/20,
                                     'position_m': [index/10, 0, 0]})+'\n')
    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        (folder / (name+'.mkv')).write_bytes(b'synthetic finalizer fixture placeholder')


def main():
    root = Path(os.environ.get('TMPDIR', '.runtime-work'))
    with tempfile.TemporaryDirectory(dir=root, prefix='c394566-finalizer-proof-') as temp:
        folder = Path(temp)
        prepare(folder)
        report = finalize(folder, folder/'analysis-report.json')
        assert report['case_id'] == CASE and len(report['measurements']) == 6
        result = json.loads((folder/'result.json').read_text())
        assert result['legal_verdict_claimed'] is False
        assert result['physical_acceptance_claimed'] is False
        assert all((folder / item['reference']).is_file() for item in result['recording_evidence'])
        for key in report['measurements']:
            assert len(report['measurements'][key]['sources']) == 9
    with tempfile.TemporaryDirectory(dir=root, prefix='c394566-finalizer-negative-') as temp:
        folder = Path(temp)
        prepare(folder)
        (folder/'permit.source.json').unlink()
        try:
            finalize(folder, folder/'analysis-report.json')
        except ValueError as error:
            assert 'Missing required source: permit.source.json' in str(error)
            print(json.dumps({'positive_measurements': 6, 'positive_frames': 600,
                              'missing_permit_source_rejected': str(error),
                              'physical_or_legal_acceptance_claimed': False}, sort_keys=True))
        else:
            raise AssertionError('Missing permit authority source was accepted')


if __name__ == '__main__':
    main()
