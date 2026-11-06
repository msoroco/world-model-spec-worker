"""Source-bound C102304 draft finalizer; no legal or physical success claim."""
from pathlib import Path

from measure_following import measure, sha


def moving_following_interval(folder):
    folder = Path(folder)
    return measure(folder/'native_samples.jsonl', folder/'following_context.json')


def analysis_report(folder, contract):
    folder = Path(folder)
    values = {}
    for row in contract['requirements']:
        if row['method'] != 'moving_following_interval':
            raise ValueError('Unrecognized C102304 measurement method')
        value = moving_following_interval(folder)
        values[row['output_key']] = {
            'method': row['method'], 'value': value,
            'sources': {name: sha(folder/name) for name in row['inputs']}}
    return {'format': 'worker-analysis-report-v1', 'case_id': contract['case_id'],
            'measurements': values, 'scope': 'synthetic_draft_only'}
