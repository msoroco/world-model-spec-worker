"""Bind every selected C125751 requirement to saved-source measurements."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SOURCE = {
    'path': 'inputs/' + AID + '/assignment.json',
    'sha256': hashlib.sha256((HERE.parents[1]/'inputs'/AID/'assignment.json').read_bytes()).hexdigest(),
}
REQUIREMENTS = (
    ('Survey the median-opening crossing and separate highway approaches',
     'crossing_context', 'measure_crossing_context', 'object', 'sourced_context',
     ['crossing-survey.json', 'source-manifest.json']),
    ('Measure both vehicles original full-body intersection entry times without a legal cutoff',
     'entry_time_difference_s', 'measure_entry_timing', 'number', 'measured',
     ['crossing-survey.json', 'original-trace.json', 'source-manifest.json']),
    ('Measure whether the ego yielded before entry or advanced before the other vehicle cleared',
     'observed_ego_response', 'measure_observed_response', 'text', 'measured',
     ['crossing-survey.json', 'original-trace.json', 'source-manifest.json']),
    ('Record the governing official traffic-control device states while preserving subsection 4 and 5 applicability questions',
     'governing_device_states', 'measure_governing_device', 'array', 'sourced_context',
     ['crossing-survey.json', 'original-trace.json', 'source-manifest.json']),
)


def build():
    plan_path = HERE/'case-plan.json'
    plan = json.loads(plan_path.read_text())
    cases = [row['case_id'] for row in plan['cases']]
    if len(cases) != 5:
        raise ValueError('Five exact timing cases required')
    plan['selected_branch'] = 'Measured crossing-entry timing at a median-opening intersection.'
    plan['requirement_dispositions'] = [
        {'requirement': row[0], 'source': SOURCE, 'status': 'selected_required',
         'case_ids': cases,
         'evidence_or_gap': 'Original Native survey and trace must establish this observation; frozen accepted metadata does not.'}
        for row in REQUIREMENTS]
    plan_path.write_text(json.dumps(plan, indent=2)+'\n')
    for case in cases:
        suffix = case.removeprefix(AID+'__')
        contract = {'format': 'worker-measurement-contract', 'case_id': case,
                    'requirements': [
                        {'disposition_index': index, 'requirement': row[0],
                         'source': SOURCE, 'output_key': row[1], 'method': row[2],
                         'value_type': row[3], 'kind': row[4], 'inputs': row[5]}
                        for index, row in enumerate(REQUIREMENTS)],
                    'negative': {'remove': ['crossing-survey.json'],
                                 'error_contains': 'Missing required source: crossing-survey.json'}}
        (HERE/('measurement-contract-'+suffix+'.json')).write_text(json.dumps(contract, indent=2)+'\n')
    print('bound four selected requirements to five exact measurement contracts')


if __name__ == '__main__':
    build()
