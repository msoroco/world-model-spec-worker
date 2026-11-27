"""Saved-only rail finalization with a separately sealed exception request.

The source packet records whether a context was requested and what supports it;
it does not decide necessity, authority, applicability or legal compliance.
"""

import argparse
import json
from pathlib import Path

from rail_exception_context import load_context, sha
from rail_finalize import run as finalize_rail
from rail_finalize import original_native_source_contract as rail_source_summary


def original_native_source_contract(packet, measured, behavior='park'):
    return rail_source_summary(packet, measured, behavior)


def sealed_exception_request_source_review(context, context_path):
    return {'branch': context['branch'],
            'requested_context_present': context['requested_context_present'],
            'source_kind': context['source_kind'],
            'source_names': sorted(context['sources']),
            'source_packet_sha256': sha(context_path),
            'diagnostic_fixture': context['source_kind'] == 'synthetic_cpu',
            'original_authority_or_necessity_reviewed': False,
            'legal_applicability_claimed': False}


def run(attempt, output):
    attempt, output = Path(attempt), Path(output)
    config = json.loads((attempt / 'config.json').read_text())
    context_path = attempt / 'exception-context.json'
    context = load_context(context_path, config['case_id'], attempt / 'capture-seal.json')
    report = finalize_rail(attempt, output)
    summary = sealed_exception_request_source_review(context, context_path)
    report['measurements']['exception_context'] = {
        'value': summary, 'method': 'sealed_exception_request_source_review',
        'sources': {'exception-context.json': sha(context_path),
                    'capture-seal.json': sha(attempt / 'capture-seal.json')}}
    output.write_text(json.dumps(report, indent=2) + '\n')
    result_path = attempt / 'result.json'
    result = json.loads(result_path.read_text())
    result['measured_values']['exception_context'] = summary
    evidence_path = attempt / 'channels' / 'exception-context.json'
    evidence_path.write_text(json.dumps({'exception_context': summary}, sort_keys=True) + '\n')
    result['recording_evidence'].append({
        'name': 'exception_context', 'unit': 'structured',
        'reference': 'channels/exception-context.json'})
    result_path.write_text(json.dumps(result, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.attempt, args.output), sort_keys=True))
